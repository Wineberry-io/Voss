// V24-06/07 + V24 redesign — radial swarm surface.
//
// Data source (re-based onto the V25 server-native swarm plane): when a live
// swarm is discovered from the agent registry, the graph derives from GET
// /swarm/{id} (roster + tasks) + the swarm.* SSE live store (assignments/gates/
// operator). Otherwise it falls back to the legacy board-derived graph. Either
// way every node/edge traces to a real signal (honest-signal contract); nodes
// render as rich chip cards via SVG <foreignObject> inside the panned/zoomed <g>.
// runData is proxy-stripped before the pure legacy derive (Pitfall 3).

import {
  type Component,
  createEffect,
  createMemo,
  createResource,
  createSignal,
  For,
  onCleanup,
  onMount,
  Show,
} from 'solid-js';
import './swarmMap.css';
import { runData, loading, loadError } from '../../org/orgStore';
import { attentionQueue } from '../../org/attention/attentionQueue';
import { liveGraphPatches } from '../../org/live/sseClient';
import { liveServer } from '../../org/live/liveServer';
import { discoverActiveSwarmId } from '../../org/live/swarmDiscovery';
import { fetchSwarm } from '../../org/live/swarmClient';
import {
  swarmAssignments,
  swarmGates,
  swarmOperatorNeeds,
  swarmLiveEdges,
  swarmEventSeq,
  activeSwarmId,
} from '../../org/live/swarmLive';
import { paneIdForCard } from '../../org/model/bridge';
import { requestOpenInGrid, requestOpenInReview } from '../../org/selection';
import { deriveSwarmGraph, type SwarmNode, type SwarmEdge } from './swarmMapDerive';
import { deriveSwarmPlane } from './swarmPlaneDerive';
import { layoutSwarm } from './swarmLayout';
import { useNow } from './clock';
import SwarmChip from './SwarmChip';
import SwarmCommandBar from './SwarmCommandBar';
import SwarmLaunch from './SwarmLaunch';
import SwarmLaunchWizard from './SwarmLaunchWizard';
import SwarmMapLegend from './SwarmMapLegend';
import EventTraceList from './EventTraceList';
import ReplayScrubber from './ReplayScrubber';

const EDGE_COLOR: Record<string, string> = {
  delegation: 'var(--focus)',
  message: 'var(--accent-blue)',
  'tool-call': 'var(--accent-magenta)',
  'file-edit': 'var(--accent-green)',
  review: 'var(--accent-amber)',
  blocker: 'var(--accent-red)',
};

const ZOOM_MIN = 0.4;
const ZOOM_MAX = 2.0;
const clampZoom = (z: number) => Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));

/** Work-node deep-link: strip the `work:` prefix back to the real card id. */
function openNode(node: SwarmNode): void {
  if (node.type !== 'work') return;
  const cardId = node.id.slice('work:'.length);
  const paneId = paneIdForCard(cardId);
  if (paneId) requestOpenInGrid(paneId);
  else requestOpenInReview(cardId);
}

const SwarmMap: Component = () => {
  const [selected, setSelected] = createSignal<SwarmNode | null>(null);
  const [pan, setPan] = createSignal({ x: 480, y: 340 });
  const [zoom, setZoom] = createSignal(1);
  const [launchOpen, setLaunchOpen] = createSignal(false);
  let canvasRef: SVGSVGElement | undefined;
  const now = useNow();

  // --- V25 swarm plane: discover + fetch snapshot, refetch on each swarm event ---
  const [swarmData] = createResource(
    () => {
      const srv = liveServer();
      if (!srv) return null;
      // Refetch triggers: a new swarm.* event (monotonic seq — NOT the live-edge
      // ring length, which plateaus at MAX_LIVE_EDGES and would freeze refetch
      // once saturated), or a freshly-launched swarm id → re-pull the
      // authoritative roster/task-state snapshot.
      return { srv, tick: swarmEventSeq(), id: activeSwarmId() };
    },
    async (k: {
      srv: NonNullable<ReturnType<typeof liveServer>>;
      tick: number;
      id: string | null;
    }) => {
      // Prefer an app-launched swarm id; else discover one from the registry.
      const id = activeSwarmId() ?? (await discoverActiveSwarmId(k.srv.cwd ?? null));
      if (!id) return null;
      try {
        return await fetchSwarm(k.srv.sidecarId, id);
      } catch {
        return null;
      }
    },
  );
  const snapshot = () => swarmData.latest ?? null;

  // Proxy-strip before the legacy pure derive (MANDATORY — Pitfall 3).
  const plainRunData = () => {
    const rd = runData();
    return rd ? JSON.parse(JSON.stringify(rd)) : null;
  };

  // Prefer the real V25 swarm plane; fall back to the legacy board-derive.
  const graph = createMemo(() => {
    const snap = snapshot();
    if (snap) {
      return deriveSwarmPlane({
        snapshot: snap,
        assignments: swarmAssignments(),
        gates: swarmGates(),
        operatorNeeds: swarmOperatorNeeds(),
      });
    }
    const rd = plainRunData();
    const runs = rd ? [{ runData: rd, liveOverlay: {} }] : [];
    return deriveSwarmGraph(runs, attentionQueue());
  });
  const onPlane = () => snapshot() != null;

  const positioned = createMemo(() => layoutSwarm(graph().nodes));
  const posById = () => {
    const map = new Map<string, { x: number; y: number }>();
    for (const n of positioned()) map.set(n.id, { x: n.x, y: n.y });
    return map;
  };

  // Returns board state and reflects on snapshot to ensure context isn't clipped
  // Reduced-motion: OS preference OR the html.reduced-motion class (A8).
  const [reduced, setReduced] = createSignal(false);
  onMount(() => {
    const mql =
      typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : null;
    const compute = () =>
      setReduced(
        document.documentElement.classList.contains('reduced-motion') ||
          (mql?.matches ?? false),
      );
    compute();
    mql?.addEventListener?.('change', compute);
    onCleanup(() => mql?.removeEventListener?.('change', compute));
  });

  // Legacy live edges merged from the SSE patch stream (board path only).
  const liveEdges = (): SwarmEdge[] => {
    if (onPlane()) return [];
    const nodes = positioned();
    const obj = nodes.find((n) => n.type === 'objective');
    if (!obj) return [];
    const out: SwarmEdge[] = [];
    liveGraphPatches().forEach((p, i) => {
      const to = nodes.find(
        (n) => n.id === `work:${p.toNodeId}` || n.id.endsWith(`:${p.toNodeId}`),
      );
      if (!to) return;
      out.push({
        id: `live:${i}:${p.timestamp}`,
        from: obj.id,
        to: to.id,
        type: p.edgeType,
        source: p.source,
      });
    });
    return out;
  };
  const allEdges = () => [...graph().edges, ...liveEdges()];

  // Pulse: legacy = live-edge targets; plane = nodes bound to a swarm event in the
  // last 2.5s (sessionId match), windowed by the 1s clock. Guarded by !reduced().
  const pulsedIds = createMemo(() => {
    if (onPlane()) {
      const recent = swarmLiveEdges().filter((e) => now() - e.timestamp < 2500);
      const ids = new Set<string>();
      for (const n of positioned()) {
        if (n.sessionId && recent.some((e) => e.sessionId === n.sessionId)) {
          ids.add(n.id);
        }
      }
      return ids;
    }
    return new Set(liveEdges().map((e) => e.to));
  });

  // Pause-hook for the guarded animations: toggle `swarm-paused` when tab hides.
  createEffect(() => {
    const el = canvasRef;
    if (!el) return;
    const onVis = () => el.classList.toggle('swarm-paused', document.hidden);
    document.addEventListener('visibilitychange', onVis);
    onCleanup(() => document.removeEventListener('visibilitychange', onVis));
  });

  // Background drag-to-pan (only the bare canvas, never a chip).
  let dragging = false;
  let last = { x: 0, y: 0 };
  const onDown = (e: PointerEvent) => {
    if (e.target !== canvasRef) return;
    dragging = true;
    last = { x: e.clientX, y: e.clientY };
  };
  const onMove = (e: PointerEvent) => {
    if (!dragging) return;
    const dx = e.clientX - last.x;
    const dy = e.clientY - last.y;
    last = { x: e.clientX, y: e.clientY };
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
  };
  const onUp = () => {
    dragging = false;
  };

  // Cmd/Ctrl + wheel zoom, anchored at the cursor.
  const onWheel = (e: WheelEvent) => {
    if (!(e.ctrlKey || e.metaKey) || !canvasRef) return;
    e.preventDefault();
    const rect = canvasRef.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const old = zoom();
    const next = clampZoom(old * (e.deltaY < 0 ? 1.1 : 1 / 1.1));
    if (next === old) return;
    setPan((p) => ({
      x: cx - ((cx - p.x) / old) * next,
      y: cy - ((cy - p.y) / old) * next,
    }));
    setZoom(next);
  };
  const stepZoom = (factor: number) => setZoom((z) => clampZoom(z * factor));
  const fitToContent = () => {
    const nodes = positioned();
    if (nodes.length === 0 || !canvasRef) return;
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const minX = Math.min(...xs) - 120;
    const maxX = Math.max(...xs) + 120;
    const minY = Math.min(...ys) - 80;
    const maxY = Math.max(...ys) + 80;
    const rect = canvasRef.getBoundingClientRect();
    const z = clampZoom(
      Math.min(rect.width / (maxX - minX), rect.height / (maxY - minY)),
    );
    setZoom(z);
    setPan({
      x: rect.width / 2 - ((minX + maxX) / 2) * z,
      y: rect.height / 2 - ((minY + maxY) / 2) * z,
    });
  };

  // A real swarm to render: the live V25 plane, or a legacy run graph with
  // actual structure (work / agent / artifact nodes). A lone objective or
  // placeholder from an idle focused run is NOT a swarm — fall through to the
  // launch wizard instead of rendering a phantom "CONTROLLER" node.
  const hasSwarm = () =>
    onPlane() ||
    graph().nodes.some(
      (n) => n.type === 'work' || n.type === 'agent' || n.type === 'artifact',
    );

  return (
    <div class="surface swarm-map" role="tabpanel" aria-label="Orchestra">
      <div class="swarm-map__body">
        <div class="swarm-grid" aria-hidden="true" />
        <div class="swarm-watermark" aria-hidden="true" />
        <div class="swarm-map__header" role="toolbar" aria-label="Orchestra actions">
          <button
            type="button"
            class="swarm-map__new"
            aria-label="New orchestra"
            onClick={() => setLaunchOpen(true)}
          >
            + New
          </button>
        </div>
        <Show
          when={!loading()}
          fallback={
            <div class="org-spinner">
              <span class="org-spinner__glyph">⟳</span>
            </div>
          }
        >
          <Show
            when={!loadError()}
            fallback={
              <div class="org-error-state">
                <p class="org-error-state__heading">Couldn't load Orchestra.</p>
                <p class="org-error-state__body">Check that Voss is running.</p>
              </div>
            }
          >
            <Show
              when={hasSwarm()}
              fallback={
                <Show when={!launchOpen()}>
                  <div class="swarm-empty swarm-empty--wizard">
                    <SwarmLaunchWizard />
                  </div>
                </Show>
              }
            >
              <svg
                ref={canvasRef}
                class="swarm-canvas"
                width="100%"
                height="100%"
                onPointerDown={onDown}
                onPointerMove={onMove}
                onPointerUp={onUp}
                onPointerLeave={onUp}
                onWheel={onWheel}
              >
                <g transform={`translate(${pan().x},${pan().y}) scale(${zoom()})`}>
                  {/* edges first, under the chips (derived + legacy live, all sourced) */}
                  <For each={allEdges()}>
                    {(edge) => {
                      const a = posById().get(edge.from);
                      const b = posById().get(edge.to);
                      return (
                        <Show when={a && b}>
                          <line
                            class={`swarm-edge${edge.type === 'blocker' ? ' swarm-edge--blocker' : ''}`}
                            data-edge-type={edge.type}
                            data-edge-source={edge.source}
                            x1={a!.x}
                            y1={a!.y}
                            x2={b!.x}
                            y2={b!.y}
                            stroke={EDGE_COLOR[edge.type] ?? 'var(--border)'}
                          />
                        </Show>
                      );
                    }}
                  </For>

                  {/* Traveling dots on freshly-patched legacy live edges (motion). */}
                  <Show when={!reduced()}>
                    <For each={liveEdges()}>
                      {(edge) => {
                        const a = posById().get(edge.from);
                        const b = posById().get(edge.to);
                        return (
                          <Show when={a && b}>
                            <circle
                              class="swarm-traveling-dot"
                              style={{
                                'offset-path': `path("M ${a!.x} ${a!.y} L ${b!.x} ${b!.y}")`,
                              }}
                            />
                          </Show>
                        );
                      }}
                    </For>
                  </Show>

                  <For each={positioned()}>
                    {(node) => (
                      <g
                        class={`swarm-node${!reduced() && pulsedIds().has(node.id) ? ' swarm-node-pulse' : ''}`}
                        data-node-type={node.type}
                        data-x={node.x}
                        data-y={node.y}
                        transform={`translate(${node.x},${node.y})`}
                        onClick={() => setSelected(node)}
                        onDblClick={() => openNode(node)}
                      >
                        <foreignObject x="-90" y="-34" width="180" height="68">
                          <SwarmChip node={node} selected={selected()?.id === node.id} />
                        </foreignObject>
                      </g>
                    )}
                  </For>
                </g>
              </svg>

              {/* Zoom controls (bottom-left overlay; siblings of the canvas). */}
              <div class="swarm-zoom" role="group" aria-label="Zoom controls">
                <button
                  type="button"
                  class="swarm-zoom__btn"
                  aria-label="Zoom out"
                  onClick={() => stepZoom(1 / 1.1)}
                >
                  −
                </button>
                <span class="swarm-zoom__pct" aria-live="polite">
                  {Math.round(zoom() * 100)}%
                </span>
                <button
                  type="button"
                  class="swarm-zoom__btn"
                  aria-label="Zoom in"
                  onClick={() => stepZoom(1.1)}
                >
                  +
                </button>
                <button
                  type="button"
                  class="swarm-zoom__btn"
                  aria-label="Fit to content"
                  onClick={fitToContent}
                >
                  ⤢
                </button>
              </div>

              {/* Orchestra command bar + quick actions (live swarm only). */}
              <Show when={onPlane()}>
                <SwarmCommandBar />
              </Show>
            </Show>
          </Show>
        </Show>
        <Show when={launchOpen()}>
          <div class="swarm-launch-modal">
            <div
              class="swarm-launch-modal__panel"
              role="dialog"
              aria-modal="true"
              aria-label="New orchestra"
              onKeyDown={(e) => {
                if (e.key === 'Escape') setLaunchOpen(false);
              }}
            >
              <div class="swarm-launch-modal__head">
                <span>New orchestra</span>
                <button
                  type="button"
                  class="swarm-launch-modal__close"
                  aria-label="Close"
                  onClick={() => setLaunchOpen(false)}
                >
                  ×
                </button>
              </div>
              <SwarmLaunch compact onClose={() => setLaunchOpen(false)} />
            </div>
          </div>
        </Show>
        {/* Replay scrubber — bottom strip, only for completed legacy runs. */}
        <Show when={!onPlane() && !loading() && !loadError() && runData()?.run_final}>
          <ReplayScrubber data={runData()!} />
        </Show>
      </div>
      <div class="swarm-side">
        <SwarmMapLegend node={selected()} onOpen={openNode} />
        <EventTraceList expanded={reduced()} />
      </div>
    </div>
  );
};

export default SwarmMap;
