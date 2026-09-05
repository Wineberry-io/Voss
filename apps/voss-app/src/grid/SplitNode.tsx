import { Switch, Match, Show, createSignal } from 'solid-js';
import { produce, type SetStoreFunction, type Store } from 'solid-js/store';
import type { GridStore, TreeNode, PaneLeaf, SplitNode } from './tree';
import { focusByClick } from './focus';
import PaneComponent from '../pane/PaneComponent';
import type { AgentConfig } from '../pane/pty-ipc';
import { budgetByPaneId } from '../pane/budgetRegistry';
import { procByPaneId } from '../pane/procRegistry';
import { isKnownAgentCli } from '../pane/agentDetect';
import DragHandle, { type Dims } from './DragHandle';
import PaneHeader from './PaneHeader';
import DotMenu from './DotMenu';
import CloseConfirmBanner, { requestCloseGated } from './CloseConfirmBanner';
import RestoreBanner from './RestoreBanner';
import type { PaneDragController } from './paneDrag';

/**
 * A3-05 close gate injection (A2 D-07 black box). A2's `PaneComponent` does
 * not surface its foreground signal yet, so `isFg` defaults to "idle" ⇒ ⌘W
 * and "Close pane" close immediately (unchanged from A3-04). A3-06/A8 wires
 * the real per-pane A2 fg signal here.
 */
export interface CloseUI {
  isFg: (paneId: string) => boolean;
  fgName: (paneId: string) => string;
}

/** V15-03 (VLIVE-04): native server session backing a structured pane. */
export interface NativeSessionRecord {
  sessionId: string;
  sidecarId: string;
}

/**
 * Recursive binary-split renderer (GRD-01). `H` = flex row (side-by-side),
 * `V` = flex column (stacked); each leaf wraps the A2 `PaneComponent` (a
 * black box — A2 owns its xterm sizing via its own ResizeObserver, so sizing
 * THIS wrapper drives the fit; A2's PaneProps has no focused/size prop so the
 * focus visual lives on the wrapper per A3-UI-SPEC).
 *
 * Focus (GRD-07): the focused leaf wrapper carries exactly the inset focus
 * shadow `shadow-[inset_0_0_0_1px_var(--focus)]` INSIDE the 1px split border
 * (A3-UI-SPEC forbids any boundary stroke/colour change). Instant repaint,
 * no CSS animation (Variant B perf budget).
 */
function mapCliToRoleColor(cliBinary?: string): string {
  if (!cliBinary) return '--role-user';
  switch (cliBinary) {
    case 'claude': return '--role-planner';
    case 'codex': return '--role-executor';
    case 'gemini': return '--role-reviewer';
    case 'opencode': return '--role-watcher';
    case 'aider': return '--role-executor';
    case 'voss': return '--role-planner';
    default: return '--role-user';
  }
}

export default function SplitNodeView(props: {
  node: TreeNode;
  store: Store<GridStore>;
  setStore: SetStoreFunction<GridStore>;
  path: string;
  dims: () => Dims;
  closeUI?: CloseUI;
  /** A6: per-pane restored scrollback keyed by saved pane id. */
  restoredScrollbackByPaneId?: Record<string, string[]>;
  /** A6: called once when user types into a restored pane. */
  onPaneFirstInput?: (paneId: string) => void;
  /** A7: tmux prefix indicator active on focused pane. */
  prefixActive?: boolean;
  /** A7: reserve prefix indicator width (tmux profile). */
  prefixReserved?: boolean;
  agentConfigByPaneId?: Record<string, AgentConfig>;
  /** V15-03: per-pane native session — leaf renders ProtocolPane when set. */
  nativeSessionByPaneId?: Record<string, NativeSessionRecord>;
  workspacePath?: string;
  paneDrag?: PaneDragController;
}) {
  const asSplit = () => props.node as SplitNode;
  const asLeaf = () => props.node as PaneLeaf;

  // Per-leaf chrome state (inert on split nodes).
  const [menuOpen, setMenuOpen] = createSignal(false);
  const [banner, setBanner] = createSignal<string | null>(null);
  const isFg = (id: string) => props.closeUI?.isFg(id) ?? false;
  const fgName = (id: string) => props.closeUI?.fgName(id) ?? 'process';

  // Single close entry (T-A3-13): idle ⇒ closeFocused now; fg ⇒ banner.
  const requestClose = () =>
    props.setStore(
      produce((s) =>
        requestCloseGated(s, asLeaf().id, () => isFg(asLeaf().id), () =>
          setBanner(fgName(asLeaf().id)),
        ),
      ),
    );

  const isFocused = () =>
    props.node.kind === 'pane' && asLeaf().id === props.store.focusedId;

  const focus = () =>
    props.setStore(produce((s) => focusByClick(s, asLeaf().id)));

  // Drag-handle hover brightens the divider (150ms border-color transition).
  const [hot, setHot] = createSignal(false);
  const [dragActive, setDragActive] = createSignal(false);
  let wrap: HTMLDivElement | undefined;

  return (
    <Switch>
      <Match when={props.node.kind === 'pane'}>
        <div
          data-pane-id={asLeaf().id}
          classList={{
            'grid-pane-leaf relative w-full h-full bg-bg-0': true,
            'grid-pane-leaf--focused': isFocused(),
          }}
          style={{ display: 'flex', 'flex-direction': 'column' }}
          onClick={focus}
        >
          <PaneHeader
            index={asLeaf().index}
            focused={isFocused()}
            cwd={asLeaf().cwd}
            shell={asLeaf().shell}
            process={procByPaneId()[asLeaf().id]}
            prefixActive={isFocused() && props.prefixActive}
            prefixReserved={props.prefixReserved}
            onToggleMenu={() => setMenuOpen((v) => !v)}
            onDragPointerDown={(e) =>
              props.paneDrag?.onHeaderPointerDown(e, asLeaf().id)
            }
            isAgent={!!props.agentConfigByPaneId?.[asLeaf().id] && isKnownAgentCli(props.agentConfigByPaneId[asLeaf().id].cliBinary)}
            roleColor={mapCliToRoleColor(props.agentConfigByPaneId?.[asLeaf().id]?.cliBinary)}
            isStreaming={(() => { const b = budgetByPaneId()[asLeaf().id]; return b ? Date.now() - b.lastSeenMs < 3000 : false; })()}
            costUsd={budgetByPaneId()[asLeaf().id]?.cost_usd}
          />
          <Show when={menuOpen()}>
            <DotMenu
              store={props.store}
              setStore={props.setStore}
              onDismiss={() => setMenuOpen(false)}
              onRequestClose={requestClose}
            />
          </Show>
          <Show when={banner() !== null}>
            <CloseConfirmBanner
              store={props.store}
              setStore={props.setStore}
              process={banner() as string}
              onKeepOpen={() => setBanner(null)}
            />
          </Show>
          <Show when={props.restoredScrollbackByPaneId?.[asLeaf().id]}>
            <RestoreBanner
              lineCount={props.restoredScrollbackByPaneId![asLeaf().id].length}
            />
          </Show>
          <div style={{ flex: 1, 'min-height': 0, position: 'relative' }}>
            <Show when={asLeaf().id} keyed>
              {(paneId) => (
                <PaneComponent
                  id={paneId}
                  cwd={asLeaf().cwd}
                  shell={asLeaf().shell}
                  index={asLeaf().index}
                  embeddedInGrid
                  restoredScrollback={
                    props.restoredScrollbackByPaneId?.[asLeaf().id]
                  }
                  onFirstInput={() => props.onPaneFirstInput?.(asLeaf().id)}
                  agentConfig={props.agentConfigByPaneId?.[asLeaf().id]}
                  workspacePath={props.workspacePath}
                  nativeSessionId={
                    props.nativeSessionByPaneId?.[asLeaf().id]?.sessionId
                  }
                  nativeSidecarId={
                    props.nativeSessionByPaneId?.[asLeaf().id]?.sidecarId
                  }
                />
              )}
            </Show>
          </div>
        </div>
      </Match>

      <Match when={props.node.kind === 'split'}>
        <div
          ref={wrap}
          class="grid-split-wrap"
          data-drag-active={dragActive() ? '' : undefined}
          style={{
            position: 'relative',
            display: 'flex',
            'flex-direction':
              asSplit().orientation === 'H' ? 'row' : 'column',
            width: '100%',
            height: '100%',
            overflow: 'hidden',
          }}
        >
          <div
            classList={{
              'grid-split-child': true,
              'grid-split-child--h': asSplit().orientation === 'H',
              'grid-split-child--v': asSplit().orientation === 'V',
              'grid-split-child--divider-hot': hot(),
            }}
            style={
              asSplit().orientation === 'H'
                ? {
                    width: `${asSplit().ratio * 100}%`,
                    height: '100%',
                  }
                : {
                    width: '100%',
                    height: `${asSplit().ratio * 100}%`,
                  }
            }
          >
            <SplitNodeView
              node={asSplit().left}
              store={props.store}
              setStore={props.setStore}
              path={`${props.path}L`}
              dims={props.dims}
              restoredScrollbackByPaneId={props.restoredScrollbackByPaneId}
              onPaneFirstInput={props.onPaneFirstInput}
              prefixActive={props.prefixActive}
              prefixReserved={props.prefixReserved}
              agentConfigByPaneId={props.agentConfigByPaneId}
              nativeSessionByPaneId={props.nativeSessionByPaneId}
              workspacePath={props.workspacePath}
              paneDrag={props.paneDrag}
            />
            <DragHandle
              store={props.store}
              setStore={props.setStore}
              path={props.path}
              orientation={asSplit().orientation}
              spanRect={() => wrap?.getBoundingClientRect()}
              dims={props.dims}
              onHover={setHot}
              onDragActive={setDragActive}
            />
          </div>
          <div
            class="grid-split-child"
            style={
              asSplit().orientation === 'H'
                ? { width: `${(1 - asSplit().ratio) * 100}%`, height: '100%' }
                : { width: '100%', height: `${(1 - asSplit().ratio) * 100}%` }
            }
          >
            <SplitNodeView
              node={asSplit().right}
              store={props.store}
              setStore={props.setStore}
              path={`${props.path}R`}
              dims={props.dims}
              restoredScrollbackByPaneId={props.restoredScrollbackByPaneId}
              onPaneFirstInput={props.onPaneFirstInput}
              prefixActive={props.prefixActive}
              prefixReserved={props.prefixReserved}
              agentConfigByPaneId={props.agentConfigByPaneId}
              nativeSessionByPaneId={props.nativeSessionByPaneId}
              workspacePath={props.workspacePath}
              paneDrag={props.paneDrag}
            />
          </div>
        </div>
      </Match>
    </Switch>
  );
}
