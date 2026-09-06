import { For, Show, createEffect, createSignal, onCleanup, onMount } from 'solid-js';
import { createStore, produce, unwrap } from 'solid-js/store';
import './canvas.css';
import PaneComponent from '../pane/PaneComponent';
import type { AgentConfig } from '../pane/pty-ipc';
import { budgetByPaneId } from '../pane/budgetRegistry';
import { procByPaneId } from '../pane/procRegistry';
import { isKnownAgentCli } from '../pane/agentDetect';
import { destroyPaneSession, reapOrphanPaneSessions } from '../pane/paneSessionRegistry';
import type { LayoutFile } from '../grid/layoutStorage';
import type { SessionFile } from '../grid/sessionStorage';
import NodeFrame from './NodeFrame';
import { applyArrangement, nextPreset, type ActiveLayout, type Arrangement, type LayoutPreset } from './arrange';
import { animateView, prefersReducedMotion } from './camera';
import { boundsOf, centerOn, fitToBounds, nodesIntersecting, panToReveal, rectFromPoints, screenToWorld, zoomAt, type Rect } from './geometry';
import { snapRect, type Guide } from './snap';
import {
  DEFAULT_NODE_H,
  DEFAULT_NODE_W,
  createCanvasState,
  findNode,
  makeNode,
  orderedNodes,
  recomputeIndices,
  type CanvasState,
  type CanvasView,
  type NodeKind,
} from './model';
import { applyLayoutToCanvas, applySessionFile, cloneCanvas } from './session';
import {
  addNode,
  cycleFocus,
  focusByDirection,
  focusByIndex,
  focusNode,
  placeAdjacent,
  removeNode,
  resizeFocusedByStep,
  resizeFromHandle,
  setRect,
  setView,
  type Direction,
  type ResizeHandle,
} from './store';
import { markCanvasChange, markCanvasDragMove, markCanvasDragSettled, resetCanvasDrag } from './sync';

export interface CloseUI {
  isFg: (paneId: string) => boolean;
  fgName: (paneId: string) => string;
}

/** Native server session backing a structured (non-PTY) pane. */
export interface NativeSessionRecord {
  sessionId: string;
  sidecarId: string;
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
  /** Enter placement: a ghost follows the cursor, click places, Esc cancels. */
  placeNode: (kind: NodeKind) => void;
  cancelPlacement: () => void;
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
  moveMode?: boolean;
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
  const [selectedIds, setSelectedIds] = createSignal<ReadonlySet<string>>(new Set());
  const [guides, setGuides] = createSignal<Guide[]>([]);
  const [marquee, setMarquee] = createSignal<Rect | null>(null);
  const [placement, setPlacement] = createSignal<{ kind: NodeKind; x: number; y: number; w: number; h: number } | null>(null);

  const isSelected = (id: string) => selectedIds().has(id);
  const toggleSelected = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const clearSelection = () => {
    if (selectedIds().size > 0) setSelectedIds(new Set<string>());
  };

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
  let cancelCamera: (() => void) | null = null;
  const commitView = (view: CanvasView) => {
    cancelCamera?.();
    cancelCamera = null;
    setStore(produce((s) => setView(s, view)));
    if (viewTimer != null) clearTimeout(viewTimer);
    viewTimer = setTimeout(changed, VIEW_PERSIST_MS);
  };

  /** Camera move: ≤ 200 ms tween, instant under reduced motion. */
  const flyTo = (view: CanvasView) => {
    cancelCamera?.();
    if (prefersReducedMotion()) {
      cancelCamera = null;
      commitView(view);
      return;
    }
    const from = { ...store.view };
    cancelCamera = animateView(
      from,
      view,
      (v) => setStore(produce((s) => setView(s, v))),
      () => {
        cancelCamera = null;
        commitView(view);
      },
    );
  };

  const reveal = (id: string) => {
    const n = findNode(store, id);
    if (!n) return;
    const next = panToReveal(store.view, n, viewport());
    if (next !== store.view) flyTo(next);
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

  const onNodePointerDown = (e: PointerEvent, id: string) => {
    if (e.shiftKey) toggleSelected(id);
    else if (!isSelected(id)) clearSelection();
    focus(id);
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
        version: 2,
        activePreset: session.activePreset,
        nodes: result.canvas.nodes,
        view: result.canvas.view,
        focusedId: result.canvas.focusedId,
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
    focusDirection: (dir) => {
      setStore(produce((s) => focusByDirection(s, dir, changed)));
      reveal(store.focusedId);
    },
    focusPaneById: (paneId) => {
      if (!findNode(store, paneId)) return;
      setStore(produce((s) => focusNode(s, paneId, changed)));
      props.onFocusChange?.(paneId);
    },
    resizeDirection: (dir) => {
      markCustom();
      setStore(produce((s) => resizeFocusedByStep(s, dir, changed)));
    },
    zoomReset: () => flyTo({ x: store.view.x, y: store.view.y, zoom: 1 }),
    zoomFit: () => {
      const b = boundsOf(store.nodes);
      if (b) flyTo(fitToBounds(b, viewport()));
    },
    zoomToFocused: () => {
      const n = findNode(store, store.focusedId);
      if (n) flyTo(centerOn(n, viewport()));
    },
    placeNode: (kind) => {
      const from = findNode(store, store.focusedId);
      const w = from?.w ?? DEFAULT_NODE_W;
      const h = from?.h ?? DEFAULT_NODE_H;
      const vp = viewport();
      const centre = screenToWorld(store.view, vp.w / 2, vp.h / 2);
      setPlacement({ kind, x: Math.round(centre.x - w / 2), y: Math.round(centre.y - h / 2), w, h });
    },
    cancelPlacement: () => setPlacement(null),
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

  const rootPoint = (e: { clientX: number; clientY: number }) => {
    const rect = rootEl.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  // --- placement mode ---------------------------------------------------------
  const onPlacementMove = (e: PointerEvent) => {
    const p = placement();
    if (!p) return;
    const sp = rootPoint(e);
    const wp = screenToWorld(store.view, sp.x, sp.y);
    setPlacement({ ...p, x: Math.round(wp.x - p.w / 2), y: Math.round(wp.y - p.h / 2) });
  };
  const confirmPlacement = () => {
    const p = placement();
    if (!p) return;
    setPlacement(null);
    markCustom();
    setStore(produce((s) => {
      const from = findNode(s, s.focusedId);
      void addNode(s, makeNode({ kind: p.kind, x: p.x, y: p.y, w: p.w, h: p.h, cwd: props.projectCwd ?? from?.cwd, shell: from?.shell }), changed);
    }));
  };
  const onPlacementKey = (e: KeyboardEvent) => {
    if (!placement()) return;
    if (e.key === 'Escape') {
      setPlacement(null);
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  };

  // --- pointer: shift-drag marquee on the empty plane ------------------------
  const beginMarquee = (e: PointerEvent) => {
    const origin = rootPoint(e);
    const base = new Set(selectedIds());
    setMarquee({ x: origin.x, y: origin.y, w: 0, h: 0 });
    beginGesture(
      (ev) => {
        const box = rectFromPoints(origin, rootPoint(ev));
        setMarquee(box);
        const tl = screenToWorld(store.view, box.x, box.y);
        const world = { x: tl.x, y: tl.y, w: box.w / store.view.zoom, h: box.h / store.view.zoom };
        const next = new Set(base);
        for (const n of nodesIntersecting(store.nodes, world)) next.add(n.id);
        setSelectedIds(next);
      },
      () => setMarquee(null),
    );
  };

  // --- pointer: pan on empty plane ------------------------------------------
  const onRootPointerDown = (e: PointerEvent) => {
    if (placement()) {
      e.preventDefault();
      e.stopPropagation();
      if (e.button === 0) confirmPlacement();
      else setPlacement(null);
      return;
    }
    const onBackground = e.target === rootEl || (e.target as HTMLElement).classList?.contains('canvas-plane');
    const forcePan = e.button === 1 || e.button === 2;
    if (!onBackground && !forcePan) return;
    if (!onBackground && (e.target as HTMLElement).closest?.('[data-resize-handle]')) return;
    e.preventDefault();
    if (onBackground && e.button === 0) {
      if (e.shiftKey) {
        beginMarquee(e);
        return;
      }
      clearSelection();
    }
    cancelCamera?.();
    cancelCamera = null;
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

  // --- pointer: drag a node (or the selection) by its header ----------------
  const beginNodeDrag = (e: PointerEvent, id: string) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest?.('button')) return;
    const node = findNode(store, id);
    if (!node) return;
    e.preventDefault();
    if (e.shiftKey) return;
    const group = isSelected(id) ? [...selectedIds()] : [id];
    const origins = new Map(
      group.flatMap((gid) => {
        const n = findNode(store, gid);
        return n ? [[gid, { x: n.x, y: n.y }] as const] : [];
      }),
    );
    const others = store.nodes.filter((n) => !origins.has(n.id)).map((n) => ({ x: n.x, y: n.y, w: n.w, h: n.h }));
    const start = { x: e.clientX, y: e.clientY };
    setDraggingId(id);
    beginGesture(
      (ev) => {
        const z = store.view.zoom;
        let dx = (ev.clientX - start.x) / z;
        let dy = (ev.clientY - start.y) / z;
        const origin = origins.get(id)!;
        if (ev.altKey) {
          setGuides([]);
        } else {
          const snapped = snapRect({ x: origin.x + dx, y: origin.y + dy, w: node.w, h: node.h }, others);
          dx = snapped.x - origin.x;
          dy = snapped.y - origin.y;
          setGuides(snapped.guides);
        }
        setStore(produce((s) => {
          for (const [gid, o] of origins) {
            const n = findNode(s, gid);
            if (!n) continue;
            n.x = Math.round(o.x + dx);
            n.y = Math.round(o.y + dy);
          }
        }));
        markCanvasDragMove();
      },
      () => {
        setDraggingId(null);
        setGuides([]);
        markCustom();
        setStore(produce((s) => recomputeIndices(s.nodes)));
        markCanvasDragSettled(plain());
      },
    );
  };

  const beginNodeResize = (e: PointerEvent, id: string, handle: ResizeHandle) => {
    if (e.button !== 0) return;
    const node = findNode(store, id);
    if (!node) return;
    e.preventDefault();
    focus(id);
    const start = { x: e.clientX, y: e.clientY, rect: { x: node.x, y: node.y, w: node.w, h: node.h } };
    beginGesture(
      (ev) => {
        const z = store.view.zoom;
        const next = resizeFromHandle(start.rect, handle, (ev.clientX - start.x) / z, (ev.clientY - start.y) / z);
        setStore(produce((s) => setRect(s, id, next)));
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
    rootEl.addEventListener('pointermove', onPlacementMove);
    window.addEventListener('keydown', onPlacementKey, true);
    props.controllerRef?.(controller);
    if (initResult) props.onLayoutChange?.(initResult.activeLayout);
    changed();
  });
  onCleanup(() => {
    endActiveGesture?.();
    resetCanvasDrag();
    cancelCamera?.();
    cancelCamera = null;
    window.removeEventListener('resize', readViewport);
    window.removeEventListener('keydown', onPlacementKey, true);
    rootEl?.removeEventListener('wheel', onWheel);
    rootEl?.removeEventListener('pointermove', onPlacementMove);
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
      data-placing={placement() ? '' : undefined}
      data-move-mode={props.moveMode ? '' : undefined}
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
                selected={isSelected(node.id)}
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
                onFocus={(e) => onNodePointerDown(e, node.id)}
                onHeaderPointerDown={(e) => beginNodeDrag(e, node.id)}
                onResizePointerDown={(e, handle) => beginNodeResize(e, node.id, handle)}
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
        <Show when={placement()}>
          {(p) => (
            <div
              class="canvas-ghost"
              data-placement-ghost={p().kind}
              style={{ transform: `translate(${p().x}px, ${p().y}px)`, width: `${p().w}px`, height: `${p().h}px` }}
            />
          )}
        </Show>
        <For each={guides()}>
          {(g) => (
            <div
              class={`canvas-guide canvas-guide--${g.axis}`}
              data-guide={g.axis}
              style={g.axis === 'x' ? { left: `${g.at}px` } : { top: `${g.at}px` }}
            />
          )}
        </For>
      </div>
      <Show when={props.moveMode}>
        <div class="canvas-mode-badge" data-mode-badge="move">move · hjkl / wasd · esc</div>
      </Show>
      <Show when={placement()}>
        <div class="canvas-mode-badge" data-mode-badge="place">click to place · esc</div>
      </Show>
      <Show when={marquee()}>
        {(m) => (
          <div
            class="canvas-marquee"
            data-marquee=""
            style={{ left: `${m().x}px`, top: `${m().y}px`, width: `${m().w}px`, height: `${m().h}px` }}
          />
        )}
      </Show>
    </div>
  );
}
