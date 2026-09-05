// Protocol-session store (grid-rearrange fix, Part B). A native pane's
// transcript/gate/lifecycle state and its SSE stream now live HERE, keyed by
// SERVER session id — not in ProtocolPane component signals. A remounted
// ProtocolPane (drag/swap/layout) re-renders from this store and never loses
// the transcript or re-subscribes; the stream is aborted only by
// destroyProtocolSession (real pane close via the paneSessionRegistry destroy
// hook — App.openNativePane wires it).
//
// Mirrors the sseClient.ts module pattern: createSignal + immutable spreads
// (no produce/structuredClone — Pitfall 5). Handlers append to the store, so
// nothing closes over component state and nothing needs rebinding on remount.

import { createSignal } from 'solid-js';

import type { AgentEvent } from '../../../../../sdk/typescript/src/client/sse';
import type { PermissionChoice } from '../../../../../sdk/typescript/src/client/permission';
import { connectLiveStream, type LiveStreamHandle } from './sseClient';
import { replySidecarPermission } from './sidecarClient';
import { resolveAttentionItem } from '../attention/attentionQueue';
import { devlog } from '../../devlog';

export type GateState =
  | { state: 'pending' }
  | { state: 'inflight'; choice: PermissionChoice }
  | { state: 'resolved'; choice: PermissionChoice };

export type ProtoBootState = 'booting' | 'live' | 'ended' | 'error';

export interface ProtocolSessionState {
  events: AgentEvent[];
  gateStates: Record<string, GateState>;
  bootState: ProtoBootState;
  errorMsg: string;
  /** Server death (stream ended with no final/session.idle) — ≠ clean idle. */
  died: boolean;
  sawCleanEnd: boolean;
  eventCount: number;
  /** The view derives props.onEnded from this — no callbacks stored here. */
  endedReason: 'idle' | 'death' | null;
  conn: { sidecarId: string };
}

export const PROTO_CAP = 300;

/**
 * D-08 trim: drop oldest entries until length ≤ cap, never trimming the task
 * header (a `user` event at index 0) or any `permission.updated`. Pure.
 */
export function trimOldest(list: AgentEvent[], cap: number): AgentEvent[] {
  if (list.length <= cap) return list;
  const out = [...list];
  let i = 0;
  while (out.length > cap && i < out.length) {
    const e = out[i];
    const pinnedTask = i === 0 && e.type === 'user';
    const pinnedPermission = e.type === 'permission.updated';
    if (pinnedTask || pinnedPermission) {
      i += 1;
      continue;
    }
    out.splice(i, 1);
  }
  return out;
}

const [protocolSessions, setProtocolSessions] = createSignal<
  Record<string, ProtocolSessionState>
>({});

// Non-reactive plumbing: one live handle + connection epoch per session id.
// The epoch guards a reconnect race — an aborted stream's finally must not
// mark the FRESH connection ended/errored.
const handles = new Map<string, LiveStreamHandle>();
const epochs = new Map<string, number>();

export function defaultProtocolState(conn: {
  sidecarId: string;
}): ProtocolSessionState {
  return {
    events: [],
    gateStates: {},
    bootState: 'booting',
    errorMsg: '',
    died: false,
    sawCleanEnd: false,
    eventCount: 0,
    endedReason: null,
    conn,
  };
}

function appendEvent(sessionId: string, epoch: number, ev: AgentEvent): void {
  if (epochs.get(sessionId) !== epoch) return; // stale stream
  devlog('info', 'proto.stream', 'event', {
    sessionId: sessionId.slice(0, 6),
    type: ev.type,
  });
  setProtocolSessions((prev) => {
    const st = prev[sessionId];
    if (!st) return prev;
    const next: ProtocolSessionState = { ...st };
    next.eventCount = st.eventCount + 1;
    if (st.bootState === 'booting') next.bootState = 'live'; // first event = connected (D-10)
    if (ev.type === 'session.idle' || ev.type === 'final') {
      next.sawCleanEnd = true;
    }
    if (ev.type === 'session.idle') {
      next.endedReason = st.endedReason ?? 'idle';
    }
    next.events = trimOldest([...st.events, ev], PROTO_CAP);
    return { ...prev, [sessionId]: next };
  });
}

function streamEnded(sessionId: string, epoch: number): void {
  if (epochs.get(sessionId) !== epoch) return; // aborted by reconnect/destroy
  handles.delete(sessionId);
  setProtocolSessions((prev) => {
    const st = prev[sessionId];
    if (!st) return prev;
    const next: ProtocolSessionState = { ...st };
    if (st.bootState === 'booting' && st.eventCount === 0) {
      // Zero events while booting = the stream never connected (D-12).
      next.bootState = 'error';
      next.errorMsg = 'stream did not connect';
    } else {
      next.bootState = 'ended';
      if (!st.sawCleanEnd) {
        next.died = true;
        next.endedReason = 'death'; // flips write affordances (D-11)
      } else {
        next.endedReason = st.endedReason ?? 'idle';
      }
    }
    return { ...prev, [sessionId]: next };
  });
}

function connect(
  sessionId: string,
  sidecarId: string,
  stream?: AsyncIterable<AgentEvent>,
): void {
  const epoch = (epochs.get(sessionId) ?? 0) + 1;
  epochs.set(sessionId, epoch);
  const handle = connectLiveStream({
    sidecarId,
    sessionId,
    cardId: sessionId, // Bridge A: the session id IS the cardId
    stream,
    onEvent: (ev) => appendEvent(sessionId, epoch, ev),
    onEnd: () => streamEnded(sessionId, epoch),
  });
  handles.set(sessionId, handle);
}

/**
 * Idempotent connect-once: the first mounting ProtocolPane subscribes; a
 * remounted one finds the live handle and just renders the store.
 */
export function ensureProtocolStream(
  sessionId: string,
  sidecarId: string,
  stream?: AsyncIterable<AgentEvent>,
): void {
  setProtocolSessions((prev) =>
    prev[sessionId]
      ? prev
      : { ...prev, [sessionId]: defaultProtocolState({ sidecarId }) },
  );
  if (handles.has(sessionId)) return;
  connect(sessionId, sidecarId, stream);
}

/**
 * D-12 "Retry start": abort the old stream (its finally is epoch-fenced),
 * reset the lifecycle flags, and rebind to the fresh handshake.
 */
export function reconnectProtocolStream(
  sessionId: string,
  sidecarId: string,
): void {
  handles.get(sessionId)?.abort();
  handles.delete(sessionId);
  setProtocolSessions((prev) => {
    const st = prev[sessionId] ?? defaultProtocolState({ sidecarId });
    return {
      ...prev,
      [sessionId]: {
        ...st,
        bootState: 'booting',
        errorMsg: '',
        died: false,
        sawCleanEnd: false,
        eventCount: 0,
        endedReason: null,
        conn: { sidecarId },
      },
    };
  });
  connect(sessionId, sidecarId);
}

/**
 * One reply loop for both surfaces (VLIVE-05): POST first, clear ONLY on
 * success (never optimistic — T-V15-07); the queue clear uses the identical
 * `permission:${id}` prefixed id (T-V15-11). Client is built from the
 * session's own handshake (Bearer middleware — T-V15-03).
 */
export async function replyToProtocolGate(
  sessionId: string,
  id: string,
  choice: PermissionChoice,
): Promise<void> {
  const st = protocolSessions()[sessionId];
  if (!st) return;
  const current = st.gateStates[id];
  if (current && current.state !== 'pending') return; // in-flight/resolved
  const setGate = (g: GateState) =>
    setProtocolSessions((prev) => {
      const cur = prev[sessionId];
      if (!cur) return prev;
      return {
        ...prev,
        [sessionId]: {
          ...cur,
          gateStates: { ...cur.gateStates, [id]: g },
        },
      };
    });
  setGate({ state: 'inflight', choice });
  try {
    await replySidecarPermission(st.conn.sidecarId, sessionId, id, choice);
    setGate({ state: 'resolved', choice });
    resolveAttentionItem(`permission:${id}`);
  } catch {
    // Failed POST: both surfaces stay pending; buttons re-enable.
    setGate({ state: 'pending' });
  }
}

/** Real teardown (pane close / reap via the pane destroy hook). */
export function destroyProtocolSession(sessionId: string): void {
  epochs.delete(sessionId); // fence the aborted stream's finally
  handles.get(sessionId)?.abort();
  handles.delete(sessionId);
  setProtocolSessions((prev) => {
    if (!(sessionId in prev)) return prev;
    const next = { ...prev };
    delete next[sessionId];
    return next;
  });
}

export { protocolSessions };

/** Test-only reset (mirrors __resetLiveStream). */
export function __resetProtocolSessions(): void {
  for (const [, h] of handles) h.abort();
  handles.clear();
  epochs.clear();
  setProtocolSessions({});
}
