// VCKP-06 live SSE consumer (GATED on V13.1, best-effort). The FIRST SSE consumer
// in the org view. Consumes the Rust-forwarded sidecar event stream and routes
// each event into two sinks:
//   1. ingestEvent (attentionQueue) — surfaces permission/budget/gate/etc rows.
//   2. the module-level live overlay signal — latest budget/status/confidence/
//      gate per session, keyed by the event's session correlation key.
//
// Pitfall 4: the webview CANNOT start `voss serve` (the V13.1 launcher imports
// node:child_process — Node-only). This module ONLY consumes a stream; it never
// imports the launcher. When no live server/stream is available the cockpit
// degrades to snapshot + manual refresh — this never blocks the phase.
//
// liveLabel: a module-level 'live' | 'snapshot' signal. Set to 'live' while a
// stream is actively connected for the selected run; reset to 'snapshot' on
// end / abort / error / absence (the default).
//
// Mirrors budgetRegistry.ts / bridge.ts: module-level createSignal + IMMUTABLE
// spread updates (NO produce / NO structuredClone — Pitfall 5).

import { createSignal } from 'solid-js';

import { ingestEvent } from '../attention/attentionQueue';
import { ingestSwarmEvent } from './swarmLive';
import type { AgentEvent } from '../../../../../sdk/typescript/src/client/sse';
import { subscribeSidecarEvents } from './sidecarClient';

// --- Live overlay (session-keyed) --------------------------------------------

/**
 * The live-plane overlay the SSE stream drives, keyed by the session correlation
 * key. Mirrors the snapshot `Card` budget shape but is updated reactively from
 * the stream WITHOUT any manual snapshot refresh.
 */
export interface LiveOverlayEntry {
  budget?: { spent: number; remaining: number; limit: number; unit: string };
  status?: string;
  confidence?: number;
  gate?: { gate: string; decision: string };
}

const [liveOverlay, setLiveOverlay] = createSignal<Record<string, LiveOverlayEntry>>(
  {},
);

/** Immutable merge of one field-set into the overlay entry for `key`. */
function mergeOverlay(key: string, patch: LiveOverlayEntry): void {
  setLiveOverlay((prev) => ({
    ...prev,
    [key]: { ...prev[key], ...patch },
  }));
}

// --- Live graph patches (V24-07, VADE2-07) -----------------------------------

/**
 * A live edge the swarm surface merges onto its derived graph. The honest-signal
 * contract extends to the live path: EVERY patch carries a real, non-empty
 * `source` of the form "sse_event:<type>". SwarmMap never renders a live edge
 * without one (Pitfall 2 on the live plane).
 */
export interface GraphPatchEvent {
  edgeType: 'message' | 'tool-call' | 'blocker';
  fromNodeId: string;
  toNodeId: string;
  source: string; // REQUIRED — "sse_event:<type>"
  timestamp: number;
}

// Bounded ring: a high-rate stream cannot grow the array unboundedly (T-V24-07-D).
const MAX_GRAPH_PATCHES = 200;
const [liveGraphPatches, setLiveGraphPatches] = createSignal<GraphPatchEvent[]>([]);

function pushGraphPatch(patch: GraphPatchEvent): void {
  setLiveGraphPatches((prev) => {
    const next = [...prev, patch];
    return next.length > MAX_GRAPH_PATCHES
      ? next.slice(next.length - MAX_GRAPH_PATCHES)
      : next;
  });
}

const BLOCKING_GATE_DECISIONS = new Set([
  'block',
  'blocked',
  'fail',
  'deny',
  'reject',
]);

/**
 * Emit a source-tagged GraphPatchEvent for events that represent live agent
 * communication. permission.updated → tool-call, budget.updated (limit
 * exceeded) → message, gate.updated (blocking decision) → blocker. Every patch
 * carries `source: "sse_event:<type>"` and a timestamp. `cardId` resolves the
 * node for permission.updated (which has no session field).
 */
function emitGraphPatch(ev: AgentEvent, cardId: string | undefined): void {
  const key = sessionKeyOf(ev) ?? cardId ?? 'unknown';
  let edgeType: GraphPatchEvent['edgeType'];
  let source: string;

  switch (ev.type) {
    case 'permission.updated':
      edgeType = 'tool-call';
      source = 'sse_event:permission.updated';
      break;
    case 'budget.updated':
      if (!(ev.limit > 0 && ev.spent >= ev.limit)) return; // only real crossings
      edgeType = 'message';
      source = 'sse_event:budget.updated';
      break;
    case 'gate.updated':
      if (!BLOCKING_GATE_DECISIONS.has(ev.decision)) return;
      edgeType = 'blocker';
      source = 'sse_event:gate.updated';
      break;
    default:
      return;
  }

  pushGraphPatch({
    edgeType,
    fromNodeId: key,
    toNodeId: key,
    source,
    timestamp: Date.now(),
  });
}

// --- live / snapshot label ----------------------------------------------------

const [liveLabel, setLiveLabel] = createSignal<'live' | 'snapshot'>('snapshot');

// Session-keyed live-handle set (V15-02): which sessionIds have an actively
// connected stream. Fixes the multi-session label problem — one stream ending
// must not read 'snapshot' while another session is still live. Immutable
// Set copies only (no produce/structuredClone — Pitfall 5).
const [liveHandles, setLiveHandles] = createSignal<Set<string>>(new Set());

// --- session correlation key --------------------------------------------------

/**
 * Read the session correlation key off an event. The plan-00 mock wraps events
 * as `AgentEvent & { sessionID }` (PROTOCOL §6 correlation key), while the raw
 * SDK union carries `session_id` (snake_case) on budget/gate/confidence/idle and
 * NOTHING on permission.updated. Prefer the correlation key that exists:
 * `sessionID`, falling back to `session_id`. Returns undefined when neither
 * exists (e.g. permission.updated — routed by ingest context, not by session).
 */
function sessionKeyOf(ev: AgentEvent): string | undefined {
  const withCorrelation = ev as AgentEvent & {
    sessionID?: string;
    session_id?: string;
  };
  return withCorrelation.sessionID ?? withCorrelation.session_id;
}

/**
 * Update the live overlay for one event, narrowed by `type` before reading any
 * type-specific field (the SDK union is NOT uniform — never assume a field).
 */
function applyOverlay(ev: AgentEvent): void {
  const key = sessionKeyOf(ev);
  if (key === undefined) return; // permission.updated has no session — overlay n/a

  switch (ev.type) {
    case 'budget.updated':
      mergeOverlay(key, {
        budget: {
          spent: ev.spent,
          remaining: ev.remaining,
          limit: ev.limit,
          unit: ev.unit,
        },
        status: 'running',
      });
      break;
    case 'confidence.updated':
      mergeOverlay(key, { confidence: ev.score });
      break;
    case 'gate.updated':
      mergeOverlay(key, { gate: { gate: ev.gate, decision: ev.decision } });
      break;
    case 'session.idle':
      mergeOverlay(key, { status: 'idle' });
      break;
    default:
      break;
  }
}

// --- connectLiveStream --------------------------------------------------------

export interface ConnectLiveStreamArgs {
  sidecarId?: string;
  sessionId: string;
  /**
   * The card bound to this stream (Bridge A: the native session id IS the
   * cardId). Threaded into ingestEvent so permission.updated rows carry a
   * defined cardId (Pitfall 3 — the event itself has no session field).
   */
  cardId?: string;
  /**
   * Per-pane sink (V15-02): invoked for EVERY yielded event, after ingest +
   * overlay. Plan 03 points this at the ProtocolPane transcript.
   */
  onEvent?: (ev: AgentEvent) => void;
  /**
   * Invoked once when the stream ends for ANY reason (clean end, server
   * death, abort) — after the label/handle bookkeeping. protocolSessions
   * derives ended/error states from this.
   */
  onEnd?: () => void;
  /**
   * Test/mock injection: an async-iterable of AgentEvents to consume instead of
   * the Tauri Channel stream.
   */
  stream?: AsyncIterable<AgentEvent>;
}

export interface LiveStreamHandle {
  /** Abort the stream cleanly: stops the for-await loop, resets liveLabel. */
  abort(): void;
}

/**
 * Connect a live SSE stream for the selected run. Consumes the Rust-forwarded
 * stream (or an injected test stream), routing each event into both
 * ingestEvent (attention queue) and the live overlay. Sets liveLabel to 'live'
 * while the stream is active and resets to 'snapshot' on end / abort / error.
 *
 * Returns a handle with `abort()` for clean teardown (no dangling generator).
 */
export function connectLiveStream(args: ConnectLiveStreamArgs): LiveStreamHandle {
  const ac = new AbortController();
  const stream =
    args.stream ??
    subscribeSidecarEvents(
      args.sidecarId ?? '',
      args.sessionId,
      ac.signal,
    );

  setLiveLabel('live');
  setLiveHandles((prev) => new Set([...prev, args.sessionId]));

  void (async () => {
    try {
      for await (const ev of stream) {
        if (ac.signal.aborted) break;
        ingestEvent(ev, args.cardId ? { cardId: args.cardId } : {});
        applyOverlay(ev);
        emitGraphPatch(ev, args.cardId);
        ingestSwarmEvent(ev); // V25 swarm.* plane (structural narrow; no-op otherwise)
        args.onEvent?.(ev);
      }
    } catch {
      // Aborted / ended / network error — degrade to snapshot, never throw.
    } finally {
      // liveHandles is the source of truth for the label: only fall back to
      // 'snapshot' once THIS session's handle is gone AND none remain. A swarm
      // launches many concurrent streams — one ending must not blank the label
      // while siblings are still live (the multi-session fix, completed here).
      let remaining = 0;
      setLiveHandles((prev) => {
        const s = new Set(prev);
        s.delete(args.sessionId);
        remaining = s.size;
        return s;
      });
      setLiveLabel(remaining > 0 ? 'live' : 'snapshot');
      args.onEnd?.();
    }
  })();

  return {
    abort(): void {
      ac.abort();
      // Drop this session's handle and recompute the label from the survivors —
      // never blindly 'snapshot' (would lie while other streams are live) and
      // never leave a leaked handle behind (parked generators end later).
      let remaining = 0;
      setLiveHandles((prev) => {
        const s = new Set(prev);
        s.delete(args.sessionId);
        remaining = s.size;
        return s;
      });
      setLiveLabel(remaining > 0 ? 'live' : 'snapshot');
    },
  };
}

export { liveLabel, liveOverlay, liveHandles, liveGraphPatches };

/**
 * Test-only reset: clears the live overlay and resets the label to its default
 * 'snapshot'. Tests call this in afterEach so module-level live state does not
 * leak across tests (mirrors __resetBridgeMaps / __resetAttentionQueue).
 */
export function __resetLiveStream(): void {
  setLiveOverlay({});
  setLiveLabel('snapshot');
  setLiveHandles(new Set<string>());
  setLiveGraphPatches([]);
}
