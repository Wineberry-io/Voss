import { onMount, onCleanup, createSignal, createEffect } from 'solid-js';
import { produce, createStore } from 'solid-js/store';
import {
  collectLeaves,
  createGridStore,
  type GridStore,
  type PaneLeaf,
  type TreeNode,
} from './tree';
import { dispatchKey } from './keymap';
import { splitFocused, equalizeAll } from './operations';
import { focusByIndex, cycleFocus, focusByDirection } from './focus';
import { resizeByKeyboard } from './resize';
import {
  applyPresetFromLeaves,
  nextPreset,
  type ActiveLayout,
  type LayoutPreset,
} from './layoutPresets';
import { markStructuralChange } from './sync';
import {
  destroyPaneSession,
  reapOrphanPaneSessions,
} from '../pane/paneSessionRegistry';
import { applyLoadedLayout } from './layoutCommands';
import { applySessionFile } from './sessionCommands';
import type { LayoutFile } from './layoutStorage';
import type { SessionFileV1 } from './sessionStorage';
import SplitNodeView, {
  type CloseUI,
  type NativeSessionRecord,
} from './SplitNode';
import type { AgentConfig } from '../pane/pty-ipc';
import { requestCloseGated } from './CloseConfirmBanner';
import type { Dims } from './DragHandle';
import { createPaneDrag } from './paneDrag';
import PaneDragLayer from './PaneDragLayer';

/**
 * Grid container (GRD-01) + global keymap host + GRD-05 window-shrink floor.
 *
 * Integration contract (verified in A3-06, NOT here — A1 owns App.tsx):
 * App.tsx renders `<GridRoot />` in the body slot below the A1 titlebar.
 * `onCloseRequest` defaults to `closeFocused` so ⌘W works pre-A3-05; A3-05
 * passes the foreground-detection-gated variant.
 *
 * A4-02: GridRoot is the layout-state bridge. App.tsx owns the
 * `activeLayout` signal and passes a getter through `activeLayout`; on
 * `Cmd+G` GridRoot reads it, computes `nextPreset`, applies the transform
 * inside `setStore(produce(...))`, and reports the new preset back through
 * `onLayoutChange`. Manual structural edits (split/close/equalize/resize)
 * route through `onStructuralEdit` and flip `activeLayout` back to
 * `custom` so the titlebar switcher reflects the off-cycle state.
 *
 * `--bg-0` shows only mid-drag / mid-close (never steady state). When the OS
 * container is too small to honor 20×5 for every pane, the inner grid is tiled
 * at `minGridSize` (≥ container) and clipped by `overflow-hidden` — panes keep
 * the floor, `--bg-0` is never sub-floored (GRD-05 shrink stop).
 */

const HEADER_PX = 22;
const FLOOR_COLS = 20;
const FLOOR_ROWS = 5;
// TODO(A3-06): read live xterm cell metrics from the A2 pane (A2 owns the
// value; PaneComponent does not yet expose it). A2 xterm = 13px / lineHeight
// 1.5 → ~8×20px cell; used only for the floor math, not layout.
const DEFAULT_CW = 8;
const DEFAULT_CH = 20;

/**
 * Smallest window px at which EVERY leaf still gets ≥ 20 cols × 5 rows given
 * the current ratios (pure — used for the GRD-05 shrink clamp).
 */
export function minGridSize(
  root: TreeNode,
  cw: number,
  ch: number,
): { w: number; h: number } {
  let needW = 0;
  let needH = 0;
  const walk = (n: TreeNode, wf: number, hf: number) => {
    if (n.kind === 'pane') {
      needW = Math.max(needW, (FLOOR_COLS * cw) / wf);
      needH = Math.max(needH, (FLOOR_ROWS * ch + HEADER_PX) / hf);
      return;
    }
    if (n.orientation === 'H') {
      walk(n.left, wf * n.ratio, hf);
      walk(n.right, wf * (1 - n.ratio), hf);
    } else {
      walk(n.left, wf, hf * n.ratio);
      walk(n.right, wf, hf * (1 - n.ratio));
    }
  };
  walk(root, 1, 1);
  return { w: Math.ceil(needW), h: Math.ceil(needH) };
}

/**
 * Imperative controller exposed via `controllerRef` so App.tsx can apply a
 * preset in response to a titlebar click without lifting the store. The
 * grid still owns the store; the controller is a thin handle.
 */
export type GridController = {
  applyPreset: (preset: LayoutPreset) => void;
  /** Apply a loaded LayoutFile to the live store — never destroys panes (A4-04). */
  applyLoadedLayout: (file: LayoutFile) => void;
  /** Apply a restored session to the live store (A6 runtime apply). */
  applySession: (session: SessionFileV1) => void;
  splitFocused: (orientation: 'H' | 'V') => void;
  closeFocused: () => void;
  equalizePanes: () => void;
  cycleLayout: () => void;
  focusNext: () => void;
  focusPrev: () => void;
  focusIndex: (n: number) => void;
  focusDirection: (dir: 'left' | 'right' | 'up' | 'down') => void;
  focusPaneById: (paneId: string) => void;
  resizeDirection: (dir: 'left' | 'right' | 'up' | 'down') => void;
  /** Plain-JS snapshot of the grid state for serialization (A4-04 D-07). */
  snapshot: () => { root: TreeNode; focusedId: string };
};

export default function GridRoot(props: {
  onCloseRequest?: (store: GridStore) => void;
  closeUI?: CloseUI;
  activeLayout?: () => ActiveLayout;
  onLayoutChange?: (next: ActiveLayout) => void;
  controllerRef?: (ctrl: GridController) => void;
  projectCwd?: string;
  /** A6: pre-resolved session to initialize from — avoids throwaway default pane. */
  initialSession?: SessionFileV1;
  /** A7: App owns registry key routing when this is true. */
  externalKeymap?: boolean;
  /** A7: tmux prefix indicator active on focused pane. */
  prefixActive?: boolean;
  /** A7: reserve prefix indicator width under tmux profile. */
  prefixReserved?: boolean;
  /**
   * A8: when this returns false, ignore global keydown (multi-workspace mount).
   * Omitted or true preserves single-grid behavior. Resize listener stays live.
   */
  active?: () => boolean;
  agentConfigByPaneId?: Record<string, AgentConfig>;
  /** V15-03: per-pane native session map — leaves render ProtocolPane. */
  nativeSessionByPaneId?: Record<string, NativeSessionRecord>;
  workspacePath?: string;
  onFocusChange?: (paneId: string) => void;
  onLeafCountChange?: (count: number) => void;
}) {
  let gridRootEl!: HTMLDivElement;
  let resizeObserver: ResizeObserver | null = null;

  // A6: initialize from restored session when available so no throwaway PTY spawns.
  const initResult = props.initialSession
    ? applySessionFile(props.initialSession)
    : null;

  const [store, setStore] = initResult
    ? createStore<GridStore>({
        root: initResult.root,
        focusedId: initResult.focusedId,
      })
    : createGridStore({ cwd: props.projectCwd });

  // A6: restored scrollback map — keyed by saved pane id, cleared on first input.
  const [restoredScrollbackByPaneId, setRestoredScrollbackByPaneId] =
    createSignal<Record<string, string[]>>(
      initResult
        ? Object.fromEntries(initResult.restoredScrollbackByPaneId)
        : {},
    );
  createEffect(() => {
    props.onFocusChange?.(store.focusedId);
  });
  createEffect(() => {
    props.onLeafCountChange?.(collectLeaves(store.root).length);
  });

  const [win, setWin] = createSignal({
    w: window.innerWidth,
    h: window.innerHeight,
  });

  const readContainerSize = () => {
    const rect = gridRootEl?.getBoundingClientRect();
    const w = Math.floor(rect?.width ?? 0);
    const h = Math.floor(rect?.height ?? 0);
    setWin({
      w: w > 0 ? w : window.innerWidth,
      h: h > 0 ? h : window.innerHeight,
    });
  };

  const grid = () => {
    const m = minGridSize(store.root, DEFAULT_CW, DEFAULT_CH);
    return { w: Math.max(win().w, m.w), h: Math.max(win().h, m.h) };
  };

  const dims = (): Dims => ({
    winW: grid().w,
    winH: grid().h,
    cw: DEFAULT_CW,
    ch: DEFAULT_CH,
  });

  // Successful drag-rearrange is a manual structural edit — flips the
  // titlebar layout switcher to `custom`, same as split/close/resize.
  const paneDrag = createPaneDrag(store, setStore, dims, () =>
    props.onLayoutChange?.('custom'),
  );

  const geom = () => ({
    winW: grid().w,
    winH: grid().h,
    cw: DEFAULT_CW,
    ch: DEFAULT_CH,
  });

  /**
   * Apply a preset to the live store. Leaves are spread-cloned into plain
   * `PaneLeaf` objects before passing to `applyPresetFromLeaves` so the
   * resulting tree contains no Solid draft proxies (memory:
   * voss-app-solid-produce-no-structuredclone).
   */
  const applyPresetToStore = (preset: LayoutPreset) => {
    const before = collectLeaves(store.root).map((l) => l.id);
    setStore(
      produce((s) => {
        const leaves: PaneLeaf[] = collectLeaves(s.root).map(
          (l) => ({ ...l }) as PaneLeaf,
        );
        s.root = applyPresetFromLeaves(leaves, preset);
      }),
    );
    // Pane ids preserved; mirror the new geometry to the Rust side once.
    // Root replacement remounts panes — sessions survive via adoption; reap
    // any id the new tree dropped (defensive: presets preserve all ids).
    reapOrphanPaneSessions(before, collectLeaves(store.root).map((l) => l.id));
    markStructuralChange(store);
    props.onLayoutChange?.(preset);
  };

  /**
   * Apply a loaded LayoutFile to the live store. Spread-clones existing
   * leaves first so `applyLoadedLayout` operates on plain JS, never a
   * draft proxy (memory: voss-app-solid-produce-no-structuredclone). The
   * function may spawn new panes (saved > current) or spill extras
   * (saved < current); A4-04 guarantees no pane id is dropped.
   */
  const applyLoadedLayoutToStore = (file: LayoutFile) => {
    let nextActive: ActiveLayout = 'custom';
    const before = collectLeaves(store.root).map((l) => l.id);
    setStore(
      produce((s) => {
        const leaves: PaneLeaf[] = collectLeaves(s.root).map(
          (l) => ({ ...l }) as PaneLeaf,
        );
        const result = applyLoadedLayout(leaves, file);
        s.root = result.root;
        s.focusedId = result.focusedId;
        nextActive = result.activeLayout;
      }),
    );
    // Root replacement — reap sessions whose pane id left the tree (A4-04
    // guarantees none today; this keeps any future remap leak-proof).
    reapOrphanPaneSessions(before, collectLeaves(store.root).map((l) => l.id));
    markStructuralChange(store);
    props.onLayoutChange?.(nextActive);
  };

  /**
   * Apply a restored session to the live store at runtime (e.g., switching
   * from project-less to project mode). Uses layout remap since live panes
   * already exist. Scrollback from the session is set for newly matched panes.
   */
  const applySessionToStore = (session: SessionFileV1) => {
    const layoutFile: LayoutFile = {
      version: 1,
      activePreset: session.activePreset,
      grid: session.grid,
    };
    applyLoadedLayoutToStore(layoutFile);
    // Set scrollback map for any matching pane ids after remap.
    const result = applySessionFile(session);
    setRestoredScrollbackByPaneId(
      Object.fromEntries(result.restoredScrollbackByPaneId),
    );
  };

  /** Plain-JS snapshot for `serializeLayout`. */
  const snapshot = (): { root: TreeNode; focusedId: string } => ({
    // JSON-clone strips Solid proxies and any non-canonical runtime fields
    // (D-07: PTY ids / scrollback / processName MUST NOT leak into the
    // serialized layout).
    root: JSON.parse(JSON.stringify(store.root)) as TreeNode,
    focusedId: store.focusedId,
  });

  const requestClose = (s: GridStore) =>
    (props.onCloseRequest ??
      ((s) =>
        requestCloseGated(
          s,
          s.focusedId,
          () => props.closeUI?.isFg(s.focusedId) ?? false,
          () => {
            /* ⌘W cross-pane banner is A3-06 (A2 fg not surfaced yet) */
          },
        )))(s);

  const markCustom = () => props.onLayoutChange?.('custom');

  const splitFocusedFromController = (orientation: 'H' | 'V') => {
    setStore(
      produce((s) => {
        markCustom();
        splitFocused(s, orientation, geom());
      }),
    );
  };

  const closeFocusedFromController = () => {
    setStore(
      produce((s) => {
        markCustom();
        requestClose(s);
      }),
    );
  };

  const equalizePanesFromController = () => {
    setStore(
      produce((s) => {
        markCustom();
        equalizeAll(s);
      }),
    );
  };

  const cycleLayoutFromController = () => {
    const cur = props.activeLayout?.() ?? 'custom';
    applyPresetToStore(nextPreset(cur));
  };

  const focusNextFromController = () => {
    setStore(produce((s) => cycleFocus(s, 'next')));
  };

  const focusPrevFromController = () => {
    setStore(produce((s) => cycleFocus(s, 'prev')));
  };

  const focusIndexFromController = (n: number) => {
    setStore(produce((s) => focusByIndex(s, n)));
  };

  const focusDirectionFromController = (
    dir: 'left' | 'right' | 'up' | 'down',
  ) => {
    setStore(produce((s) => focusByDirection(s, dir, win().w, win().h)));
  };

  const focusPaneByIdFromController = (paneId: string) => {
    const leaves = collectLeaves(store.root);
    const target = leaves.find((l) => l.id === paneId);
    if (!target) return;
    setStore(produce((s) => { s.focusedId = paneId; }));
    props.onFocusChange?.(paneId);
  };

  const resizeDirectionFromController = (
    dir: 'left' | 'right' | 'up' | 'down',
  ) => {
    setStore(
      produce((s) => {
        markCustom();
        resizeByKeyboard(s, dir, win().w, win().h, DEFAULT_CW, DEFAULT_CH);
      }),
    );
  };

  const onKey = (e: KeyboardEvent) => {
    if (props.active && !props.active()) return;
    if (props.externalKeymap) return;
    if (!e.metaKey) return; // every A3 chord needs ⌘ — let the PTY have it
    // Cmd+G must run OUTSIDE the dispatch produce because
    // `applyPresetToStore` owns its own `setStore` call; nesting setStore
    // calls inside a draft is fragile. Capture the cycle request via a
    // flag and execute after the produce closes.
    let cycleRequested = false;
    setStore(
      produce((s) => {
        dispatchKey(
          s,
          e,
          win().w,
          win().h,
          DEFAULT_CW,
          DEFAULT_CH,
          props.onCloseRequest ??
            requestClose,
          // onCycleLayout: defer to after-produce execution.
          () => {
            cycleRequested = true;
          },
          // onStructuralEdit: any A3 structural mutation flips the layout
          // back to `custom`. Called before the op so the order of events
          // (custom-state-change, then geometry update) matches A4-UI-SPEC.
          () => {
            props.onLayoutChange?.('custom');
          },
        );
      }),
    );
    if (cycleRequested) {
      const cur = props.activeLayout?.() ?? 'custom';
      applyPresetToStore(nextPreset(cur));
    }
  };
  const onResize = () => readContainerSize();

  onMount(() => {
    readContainerSize();
    resizeObserver =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => readContainerSize());
    resizeObserver?.observe(gridRootEl);
    window.addEventListener('keydown', onKey);
    window.addEventListener('resize', onResize);
    props.controllerRef?.({
      applyPreset: applyPresetToStore,
      applyLoadedLayout: applyLoadedLayoutToStore,
      applySession: applySessionToStore,
      splitFocused: splitFocusedFromController,
      closeFocused: closeFocusedFromController,
      equalizePanes: equalizePanesFromController,
      cycleLayout: cycleLayoutFromController,
      focusNext: focusNextFromController,
      focusPrev: focusPrevFromController,
      focusIndex: focusIndexFromController,
      focusDirection: focusDirectionFromController,
      focusPaneById: focusPaneByIdFromController,
      resizeDirection: resizeDirectionFromController,
      snapshot,
    });
    // A6: report restored activeLayout after mount so App.tsx signal updates.
    if (initResult) {
      props.onLayoutChange?.(initResult.activeLayout);
    }
  });
  onCleanup(() => {
    window.removeEventListener('keydown', onKey);
    window.removeEventListener('resize', onResize);
    resizeObserver?.disconnect();
    resizeObserver = null;
    // True workspace teardown (tab SWITCH is display:none and never disposes
    // this component — D-01): kill every live pane session this grid owns.
    for (const leaf of collectLeaves(store.root)) {
      destroyPaneSession(leaf.id);
    }
  });

  return (
    <div
      ref={gridRootEl}
      class="grid-root bg-bg-0 w-full h-full overflow-hidden"
    >
      <div style={{ width: `${grid().w}px`, height: `${grid().h}px` }}>
        <SplitNodeView
          node={store.root}
          store={store}
          setStore={setStore}
          path=""
          dims={dims}
          closeUI={props.closeUI}
          restoredScrollbackByPaneId={restoredScrollbackByPaneId()}
          onPaneFirstInput={(paneId) => {
            setRestoredScrollbackByPaneId((prev) => {
              const next = { ...prev };
              delete next[paneId];
              return next;
            });
          }}
          prefixActive={props.prefixActive}
          prefixReserved={props.prefixReserved}
          agentConfigByPaneId={props.agentConfigByPaneId}
          nativeSessionByPaneId={props.nativeSessionByPaneId}
          workspacePath={props.workspacePath}
          paneDrag={paneDrag}
        />
      </div>
      <PaneDragLayer drag={paneDrag} />
    </div>
  );
}
