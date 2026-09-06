import { For, Show, createEffect, createSignal, onCleanup, onMount } from 'solid-js';
import { createStore, produce, unwrap } from 'solid-js/store';
import './canvas.css';
import PaneComponent from '../pane/PaneComponent';
import type { AgentConfig } from '../pane/pty-ipc';
import { budgetByPaneId } from '../pane/budgetRegistry';
import { procByPaneId } from '../pane/procRegistry';
import { isKnownAgentCli } from '../pane/agentDetect';
import { destroyPaneSession, reapOrphanPaneSessions } from '../pane/paneSessionRegistry';
import type { NativeSessionRecord } from '../grid/SplitNode';
import type { LayoutFile } from '../grid/layoutStorage';
import type { SessionFile } from '../grid/sessionStorage';
import { nextPreset, type ActiveLayout, type LayoutPreset } from '../grid/layoutPresets';
import NodeFrame from './NodeFrame';
import { applyArrangement, type Arrangement } from './arrange';
import { boundsOf, centerOn, fitToBounds, screenToWorld, zoomAt } from './geometry';
import {
  createCanvasState,
  findNode,
  orderedNodes,
  recomputeIndices,
  type CanvasState,
  type CanvasView,
} from './model';
import { applyLayoutToCanvas, applySessionFile, cloneCanvas } from './session';
import {
  cycleFocus,
  focusByDirection,
  focusByIndex,
  focusNode,
  placeAdjacent,
  removeNode,
  resizeFocusedByStep,
  resizeNode,
  setView,
  type Direction,
} from './store';
import { markCanvasChange, markCanvasDragMove, markCanvasDragSettled, resetCanvasDrag } from './sync';

export interface CloseUI {
  isFg: (paneId: string) => boolean;
  fgName: (paneId: string) => string;
}

/** Imperative handle App composes with. Superset of the old GridController. */
export type CanvasController = {
  applyPreset: (preset: LayoutPreset) => void;
  applyLoadedLayout: (file: LayoutFile) => void;
  applySession: (session: SessionFile) => void;
  splitFocused: (orientation: 'H' | 'V') => void;
  closeFocused: () => void;
  equalizePanes: () => void;
  cycleLayout: () => void;
  focusNext: () => void;
  focusPrev: () => void;
  focusIndex: (n: number) => void;
  focusDirection: (dir: Direction) => void;
  focusPaneById: (paneId: string) => void;
  resizeDirection: (dir: Direction) => void;
  zoomReset: () => void;
  zoomFit: () => void;
  zoomToFocused: () => void;
  setView: (view: CanvasView) => void;
  snapshot: () => CanvasState;
};

export type GridController = CanvasController;

const VIEW_PERSIST_MS = 250;
const WHEEL_ZOOM_SENSITIVITY = 0.0015;

function mapCliToRoleColor(cliBinary?: string): string {
  switch (cliBinary) {
    case 'claude':
    case 'voss':
      return '--role-planner';
    case 'codex':
    case 'aider':
      return '--role-executor';
    case 'gemini':
      return '--role-reviewer';
    case 'opencode':
      return '--role-watcher';
    default:
      return '--role-user';
  }
}

export default function CanvasRoot(props: {
  closeUI?: CloseUI;
  activeLayout?: () => ActiveLayout;
  onLayoutChange?: (next: ActiveLayout) => void;
  controllerRef?: (ctrl: CanvasController) => void;
  projectCwd?: string;
  initialSession?: SessionFile;
  externalKeymap?: boolean;
  prefixActive?: boolean;
  prefixReserved?: boolean;
  active?: () => boolean;
  agentConfigByPaneId?: Record<string, AgentConfig>;
  nativeSessionByPaneId?: Record<string, NativeSessionRecord>;
  workspacePath?: string;
  onFocusChange?: (paneId: string) => void;
  onLeafCountChange?: (count: number) => void;
}) {
  let rootEl!: HTMLDivElement;
  let resizeObserver: ResizeObserver | null = null;

  const initResult = props.initialSession ? applySessionFile(props.initialSession) : null;
  const [store, setStore] = createStore<CanvasState>(
    initResult ? initResult.canvas : createCanvasState({ cwd: props.projectCwd }),
  );
  const [restoredScrollbackByPaneId, setRestoredScrollbackByPaneId] = createSignal<
    Record<string, string[]>
  >(initResult ? Object.fromEntries(initResult.restoredScrollbackByPaneId) : {});
  const [viewport, setViewport] = createSignal({ w: window.innerWidth, h: window.innerHeight });
  const [panning, setPanning] = createSignal(false);
  const [draggingId, setDraggingId] = createSignal<string | null>(null);
  const [closeBanner, setCloseBanner] = createSignal<Record<string, string>>({});

  createEffect(() => props.onFocusChange?.(store.focusedId));
  createEffect(() => props.onLeafCountChange?.(store.nodes.length));

  const plain = (): CanvasState => cloneCanvas(unwrap(store));
  const changed = () => markCanvasChange(plain());
  const markCustom = () => props.onLayoutChange?.('custom');

  const readViewport = () => {
    const rect = rootEl?.getBoundingClientRect();
    const w = Math.floor(rect?.width ?? 0);
    const h = Math.floor(rect?.height ?? 0);
    setViewport({ w: w > 0 ? w : window.innerWidth, h: h > 0 ? h : window.innerHeight });
  };

  let viewTimer: ReturnType<typeof setTimeout> | undefined;
  const commitView = (view: CanvasView) => {
    setStore(produce((s) => setView(s, view)));
    if (viewTimer != null) clearTimeout(viewTimer);
    viewTimer = setTimeout(changed, VIEW_PERSIST_MS);
  };

  /** World box the viewport currently shows; arrangements fill it. */
  const visibleBox = () => {
    const vp = viewport();
    const tl = screenToWorld(store.view, 0, 0);
    return { x: tl.x, y: tl.y, w: vp.w / store.view.zoom, h: vp.h / store.view.zoom };
  };

  const arrange = (arrangement: Arrangement, next: ActiveLayout) => {
    const box = visibleBox();
    setStore(
      produce((s) => {
        const ordered = orderedNodes(s);
        applyArrangement(ordered, arrangement, { w: box.w, h: box.h });
        for (const n of ordered) {
          n.x += box.x;
          n.y += box.y;
        }
        recomputeIndices(s.nodes);
      }),
    );
    changed();
    props.onLayoutChange?.(next);
  };

  const split = (side: 'right' | 'below') => {
    markCustom();
    setStore(produce((s) => void placeAdjacent(s, side, { cwd: props.projectCwd }, changed)));
  };

  const closeNow = (id: string) => {
    markCustom();
    setStore(produce((s) => void removeNode(s, id, changed)));
    destroyPaneSession(id);
    setCloseBanner((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const requestClose = (id: string) => {
    if (props.closeUI?.isFg(id)) {
      setCloseBanner((prev) => ({ ...prev, [id]: props.closeUI?.fgName(id) ?? 'process' }));
      return;
    }
    closeNow(id);
  };

  const focus = (id: string) => {
    if (store.focusedId === id) return;
    setStore(produce((s) => focusNode(s, id, changed)));
  };

  const controller: CanvasController = {
    applyPreset: (preset) => arrange(preset, preset),
    applyLoadedLayout: (file) => {
      const before = store.nodes.map((n) => n.id);
      const result = applyLayoutToCanvas(plain(), file);
      setStore(produce((s) => {
        s.nodes = result.canvas.nodes;
        s.view = result.canvas.view;
        s.focusedId = result.canvas.focusedId;
      }));
      reapOrphanPaneSessions(before, store.nodes.map((n) => n.id));
      changed();
      props.onLayoutChange?.(result.activeLayout);
    },
    applySession: (session) => {
      const before = store.nodes.map((n) => n.id);
      const result = applySessionFile(session);
      const remapped = applyLayoutToCanvas(plain(), {
        version: 1,
        activePreset: session.activePreset,
        grid: { root: { kind: 'pane', id: result.canvas.focusedId, cwd: '', shell: '', index: 1 }, focusedId: result.canvas.focusedId },
        nodes: result.canvas.nodes,
        view: result.canvas.view,
      });
      setStore(produce((s) => {
        s.nodes = remapped.canvas.nodes;
        s.view = remapped.canvas.view;
        s.focusedId = remapped.canvas.focusedId;
      }));
      reapOrphanPaneSessions(before, store.nodes.map((n) => n.id));
      setRestoredScrollbackByPaneId(Object.fromEntries(result.restoredScrollbackByPaneId));
      changed();
      props.onLayoutChange?.(result.activeLayout);
    },
    splitFocused: (orientation) => split(orientation === 'V' ? 'below' : 'right'),
    closeFocused: () => requestClose(store.focusedId),
    equalizePanes: () => arrange('grid', 'custom'),
    cycleLayout: () => {
      const next = nextPreset(props.activeLayout?.() ?? 'custom');
      arrange(next, next);
    },
    focusNext: () => setStore(produce((s) => cycleFocus(s, 'next', changed))),
    focusPrev: () => setStore(produce((s) => cycleFocus(s, 'prev', changed))),
    focusIndex: (n) => setStore(produce((s) => focusByIndex(s, n, changed))),
    focusDirection: (dir) => setStore(produce((s) => focusByDirection(s, dir, changed))),
    focusPaneById: (paneId) => {
      if (!findNode(store, paneId)) return;
      setStore(produce((s) => focusNode(s, paneId, changed)));
      props.onFocusChange?.(paneId);
    },
    resizeDirection: (dir) => {
      markCustom();
      setStore(produce((s) => resizeFocusedByStep(s, dir, changed)));
    },
    zoomReset: () => commitView({ x: store.view.x, y: store.view.y, zoom: 1 }),
    zoomFit: () => {
      const b = boundsOf(store.nodes);
      if (b) commitView(fitToBounds(b, viewport()));
    },
    zoomToFocused: () => {
      const n = findNode(store, store.focusedId);
      if (n) commitView(centerOn(n, viewport()));
    },
    setView: commitView,
    snapshot: plain,
  };

  /**
   * One pointer gesture at a time. `end` runs on pointerup, pointercancel,
   * or unmount, so listeners and the drag flag never outlive the gesture.
   */
  let endActiveGesture: (() => void) | null = null;
  const beginGesture = (move: (ev: PointerEvent) => void, settle: () => void) => {
    endActiveGesture?.();
    const end = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
      endActiveGesture = null;
      settle();
    };
    endActiveGesture = end;
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
  };

  // --- pointer: pan on empty plane ------------------------------------------
  const onRootPointerDown = (e: PointerEvent) => {
    const onBackground = e.target === rootEl || (e.target as HTMLElement).classList?.contains('canvas-plane');
    const forcePan = e.button === 1 || e.button === 2;
    if (!onBackground && !forcePan) return;
    if (!onBackground && (e.target as HTMLElement).closest?.('[data-resize-handle]')) return;
    e.preventDefault();
    const start = { x: e.clientX, y: e.clientY, vx: store.view.x, vy: store.view.y };
    setPanning(true);
    beginGesture(
      (ev) => {
        setStore(produce((s) => {
          s.view.x = start.vx + (ev.clientX - start.x);
          s.view.y = start.vy + (ev.clientY - start.y);
        }));
      },
      () => {
        setPanning(false);
        commitView(store.view);
      },
    );
  };

  const onWheel = (e: WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const rect = rootEl.getBoundingClientRect();
      const factor = Math.exp(-e.deltaY * WHEEL_ZOOM_SENSITIVITY);
      commitView(zoomAt(store.view, store.view.zoom * factor, e.clientX - rect.left, e.clientY - rect.top));
      return;
    }
    const insideNode = (e.target as HTMLElement).closest?.('.canvas-node');
    if (insideNode) return;
    e.preventDefault();
    commitView({ x: store.view.x - e.deltaX, y: store.view.y - e.deltaY, zoom: store.view.zoom });
  };

  // --- pointer: drag a node by its header -----------------------------------
  const beginNodeDrag = (e: PointerEvent, id: string) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest?.('button')) return;
    const node = findNode(store, id);
    if (!node) return;
    e.preventDefault();
    focus(id);
    const start = { x: e.clientX, y: e.clientY, nx: node.x, ny: node.y };
    setDraggingId(id);
    beginGesture(
      (ev) => {
        const z = store.view.zoom;
        setStore(produce((s) => {
          const n = findNode(s, id);
          if (!n) return;
          n.x = Math.round(start.nx + (ev.clientX - start.x) / z);
          n.y = Math.round(start.ny + (ev.clientY - start.y) / z);
        }));
        markCanvasDragMove();
      },
      () => {
        setDraggingId(null);
        markCustom();
        setStore(produce((s) => recomputeIndices(s.nodes)));
        markCanvasDragSettled(plain());
      },
    );
  };

  const beginNodeResize = (e: PointerEvent, id: string) => {
    if (e.button !== 0) return;
    const node = findNode(store, id);
    if (!node) return;
    e.preventDefault();
    focus(id);
    const start = { x: e.clientX, y: e.clientY, w: node.w, h: node.h };
    beginGesture(
      (ev) => {
        const z = store.view.zoom;
        setStore(produce((s) =>
          resizeNode(s, id, start.w + (ev.clientX - start.x) / z, start.h + (ev.clientY - start.y) / z),
        ));
        markCanvasDragMove();
      },
      () => {
        markCustom();
        markCanvasDragSettled(plain());
      },
    );
  };

  onMount(() => {
    readViewport();
    resizeObserver =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => readViewport());
    resizeObserver?.observe(rootEl);
    window.addEventListener('resize', readViewport);
    rootEl.addEventListener('wheel', onWheel, { passive: false });
    props.controllerRef?.(controller);
    if (initResult) props.onLayoutChange?.(initResult.activeLayout);
    changed();
  });
  onCleanup(() => {
    endActiveGesture?.();
    resetCanvasDrag();
    window.removeEventListener('resize', readViewport);
    rootEl?.removeEventListener('wheel', onWheel);
    resizeObserver?.disconnect();
    resizeObserver = null;
    if (viewTimer != null) clearTimeout(viewTimer);
    for (const n of store.nodes) destroyPaneSession(n.id);
  });

  return (
    <div
      ref={rootEl}
      class="canvas-root"
      data-panning={panning() ? '' : undefined}
      data-zoom={store.view.zoom.toFixed(2)}
      onPointerDown={onRootPointerDown}
      onContextMenu={(e) => {
        if (panning()) e.preventDefault();
      }}
    >
      <div
        class="canvas-plane"
        style={{ transform: `translate(${store.view.x}px, ${store.view.y}px) scale(${store.view.zoom})` }}
      >
        <For each={store.nodes}>
          {(node) => {
            const cfg = () => props.agentConfigByPaneId?.[node.id];
            const budget = () => budgetByPaneId()[node.id];
            return (
              <NodeFrame
                node={node}
                focused={node.id === store.focusedId}
                dragging={draggingId() === node.id}
                process={procByPaneId()[node.id]}
                prefixActive={props.prefixActive}
                prefixReserved={props.prefixReserved}
                isAgent={!!cfg() && isKnownAgentCli(cfg()!.cliBinary)}
                roleColor={mapCliToRoleColor(cfg()?.cliBinary)}
                isStreaming={budget() ? Date.now() - budget()!.lastSeenMs < 3000 : false}
                costUsd={budget()?.cost_usd}
                restoredLineCount={restoredScrollbackByPaneId()[node.id]?.length}
                closeBanner={closeBanner()[node.id] ?? null}
                onFocus={() => focus(node.id)}
                onHeaderPointerDown={(e) => beginNodeDrag(e, node.id)}
                onResizePointerDown={(e) => beginNodeResize(e, node.id)}
                onFork={() => {
                  focus(node.id);
                  split('right');
                }}
                onSplitRight={() => {
                  focus(node.id);
                  split('right');
                }}
                onSplitBelow={() => {
                  focus(node.id);
                  split('below');
                }}
                onRequestClose={() => requestClose(node.id)}
                onConfirmClose={() => closeNow(node.id)}
                onKeepOpen={() =>
                  setCloseBanner((prev) => {
                    const next = { ...prev };
                    delete next[node.id];
                    return next;
                  })
                }
              >
                <Show when={node.id} keyed>
                  {(paneId) => (
                    <PaneComponent
                      id={paneId}
                      cwd={node.cwd}
                      shell={node.shell}
                      index={node.index}
                      embeddedInGrid
                      restoredScrollback={restoredScrollbackByPaneId()[paneId]}
                      onFirstInput={() =>
                        setRestoredScrollbackByPaneId((prev) => {
                          const next = { ...prev };
                          delete next[paneId];
                          return next;
                        })
                      }
                      agentConfig={cfg()}
                      workspacePath={props.workspacePath}
                      nativeSessionId={props.nativeSessionByPaneId?.[paneId]?.sessionId}
                      nativeSidecarId={props.nativeSessionByPaneId?.[paneId]?.sidecarId}
                    />
                  )}
                </Show>
              </NodeFrame>
            );
          }}
        </For>
      </div>
    </div>
  );
}
