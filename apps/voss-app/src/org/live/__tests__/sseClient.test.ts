import { describe, it, expect, afterEach } from 'vitest';

import { mockSseStream } from './mockSseStream';
import {
  connectLiveStream,
  liveLabel,
  liveOverlay,
  liveHandles,
  __resetLiveStream,
} from '../sseClient';
import {
  attentionQueue,
  __resetAttentionQueue,
} from '../../attention/attentionQueue';
import { __resetBridgeMaps } from '../../model/bridge';
import type { AgentEvent } from '../../../../../../sdk/typescript/src/client/sse';

// VCKP-06: the live SSE client wrapper `../sseClient` consumes V13.1
// `subscribeToEvents` (never raw EventSource), routes each event into ingestEvent
// + the live overlay keyed by the session correlation key, and exposes a
// 'live' | 'snapshot' label with graceful snapshot fallback (Pitfall 4 — the
// webview only consumes; the stream is mocked here).

const SESSION = '0139377ff590';

/** Drain the connect handle's async loop to completion (mock stream ends fast). */
async function flush(): Promise<void> {
  // Two microtask turns is enough for the mock generator (2 yields) to drain
  // and the finally-block to run; await a macrotask to be safe.
  await new Promise((r) => setTimeout(r, 0));
}

afterEach(() => {
  __resetLiveStream();
  __resetAttentionQueue();
  __resetBridgeMaps();
});

describe('live SSE consumer — VCKP-06 (../sseClient)', () => {
  it('mockSseStream yields >=2 typed AgentEvents, each carrying sessionID', async () => {
    const events = [];
    for await (const ev of mockSseStream(SESSION)) {
      events.push(ev);
    }

    expect(events.length).toBeGreaterThanOrEqual(2);
    for (const ev of events) {
      expect(ev.sessionID).toBe(SESSION);
      if (ev.type === 'budget.updated' || ev.type === 'gate.updated') {
        expect(ev.session_id).toBe(SESSION);
      }
    }

    const types = events.map((e) => e.type);
    expect(types).toContain('budget.updated');
    expect(types).toContain('gate.updated');
  });

  it('drives mockSseStream into ingestEvent + the live overlay with no manual refresh, label -> live', async () => {
    const handle = connectLiveStream({
      sessionId: SESSION,
      stream: mockSseStream(SESSION),
    });

    // 'live' is set synchronously while the stream is connected.
    expect(liveLabel()).toBe('live');

    await flush();

    // Overlay was updated reactively (no manual snapshot refresh call).
    const entry = liveOverlay()[SESSION];
    expect(entry).toBeDefined();
    expect(entry.budget).toEqual({
      spent: 1200,
      remaining: 8800,
      limit: 10000,
      unit: 'tokens',
    });
    expect(entry.gate).toEqual({ gate: 'plan', decision: 'approved' });

    // ingestEvent routed the gate.updated event into the attention queue.
    const gateItem = attentionQueue().find((i) => i.kind === 'gate');
    expect(gateItem).toBeDefined();
    expect(gateItem?.summary).toContain('plan');

    handle.abort();
  });

  it("defaults to 'snapshot' with no stream and never throws (graceful degrade)", () => {
    // No connectLiveStream called: the module-level label is its default.
    expect(liveLabel()).toBe('snapshot');
    // Snapshot fallback: reading the overlay with no stream is empty, no throw.
    expect(() => liveOverlay()).not.toThrow();
    expect(liveOverlay()).toEqual({});
  });

  it('a budget.updated event updates the budget overlay with no manual refresh', async () => {
    async function* oneBudget(): AsyncGenerator<AgentEvent & { sessionID: string }> {
      yield {
        type: 'budget.updated',
        session_id: SESSION,
        sessionID: SESSION,
        spent: 4200,
        remaining: 5800,
        limit: 10000,
        unit: 'tokens',
        v: 1,
      };
    }

    const handle = connectLiveStream({
      sessionId: SESSION,
      stream: oneBudget(),
    });

    await flush();

    expect(liveOverlay()[SESSION]?.budget?.spent).toBe(4200);
    handle.abort();
  });

  it('AbortController teardown stops the stream cleanly and resets label -> snapshot', async () => {
    let delivered = 0;
    // A stream that would yield forever if not aborted.
    async function* infinite(): AsyncGenerator<AgentEvent & { sessionID: string }> {
      while (true) {
        delivered += 1;
        yield {
          type: 'budget.updated',
          session_id: SESSION,
          sessionID: SESSION,
          spent: delivered,
          remaining: 1,
          limit: 10,
          unit: 'tokens',
          v: 1,
        };
        await new Promise((r) => setTimeout(r, 1));
      }
    }

    const handle = connectLiveStream({
      sessionId: SESSION,
      stream: infinite(),
    });

    expect(liveLabel()).toBe('live');
    await flush();
    handle.abort();

    expect(liveLabel()).toBe('snapshot');

    // After abort the loop breaks (at most one in-flight iteration resumes from
    // its pending await, then the aborted-check breaks). Let everything settle,
    // then confirm deliveries have STOPPED growing — no dangling generator.
    await new Promise((r) => setTimeout(r, 10));
    const settled = delivered;
    await new Promise((r) => setTimeout(r, 20));
    expect(delivered).toBe(settled);
  });
});

// V15-02 (VLIVE-03): per-pane onEvent sink, permission cardId context
// (Pitfall 3), and the session-keyed liveHandles set (multi-session label fix).
describe('live SSE consumer — V15-02 extensions (../sseClient)', () => {
  it('onEvent receives every event from an injected stream', async () => {
    const seen: AgentEvent[] = [];
    const handle = connectLiveStream({
      sessionId: SESSION,
      stream: mockSseStream(SESSION),
      onEvent: (ev) => seen.push(ev),
    });

    await flush();

    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen.map((e) => e.type)).toEqual(
      expect.arrayContaining(['budget.updated', 'gate.updated']),
    );
    handle.abort();
  });

  it('a permission.updated event with a cardId yields a queue row with a defined cardId (Pitfall 3)', async () => {
    async function* onePermission(): AsyncGenerator<AgentEvent> {
      yield {
        type: 'permission.updated',
        id: 'perm-1',
        tool_name: 'bash',
        args: { cmd: 'ls' },
        dimension: 'execution',
        v: 1,
      } as unknown as AgentEvent;
    }

    const handle = connectLiveStream({
      sessionId: SESSION,
      cardId: 'card-77',
      stream: onePermission(),
    });

    await flush();

    const row = attentionQueue().find((i) => i.kind === 'permission');
    expect(row).toBeDefined();
    expect(row?.cardId).toBe('card-77');
    handle.abort();
  });

  it('liveHandles contains the sessionId during the stream and is empty after completion', async () => {
    let release: (() => void) | undefined;
    async function* heldOpen(): AsyncGenerator<AgentEvent> {
      yield {
        type: 'budget.updated',
        session_id: SESSION,
        spent: 1,
        remaining: 9,
        limit: 10,
        unit: 'tokens',
        v: 1,
      } as unknown as AgentEvent;
      await new Promise<void>((r) => {
        release = r;
      });
    }

    connectLiveStream({
      sessionId: SESSION,
      stream: heldOpen(),
    });

    await flush();
    expect(liveHandles().has(SESSION)).toBe(true);

    release?.();
    await flush();
    expect(liveHandles().size).toBe(0);
  });

  it('keeps liveLabel "live" while a sibling stream is still connected (multi-session swarm)', async () => {
    const SESSION_B = 'b0b0b0b0b0b0';
    let releaseB: (() => void) | undefined;
    async function* finite(): AsyncGenerator<AgentEvent> {
      yield {
        type: 'budget.updated',
        session_id: SESSION,
        spent: 1,
        remaining: 9,
        limit: 10,
        unit: 'tokens',
        v: 1,
      } as unknown as AgentEvent;
    }
    async function* heldOpen(): AsyncGenerator<AgentEvent> {
      yield {
        type: 'budget.updated',
        session_id: SESSION_B,
        spent: 1,
        remaining: 9,
        limit: 10,
        unit: 'tokens',
        v: 1,
      } as unknown as AgentEvent;
      await new Promise<void>((r) => {
        releaseB = r;
      });
    }

    // A is a short finite stream; B stays open (a swarm launches many at once).
    connectLiveStream({ sessionId: SESSION, stream: finite() });
    connectLiveStream({ sessionId: SESSION_B, stream: heldOpen() });

    await flush();
    // A has ended; B is still live → the label must NOT have flipped to snapshot.
    expect(liveHandles().has(SESSION)).toBe(false);
    expect(liveHandles().has(SESSION_B)).toBe(true);
    expect(liveLabel()).toBe('live');

    releaseB?.();
    await flush();
    expect(liveHandles().size).toBe(0);
    expect(liveLabel()).toBe('snapshot');
  });
});
