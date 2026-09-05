// V24-07 (VADE2-07) — live edge honest-signal contract. A mock SSE stream of
// each mapped event type must yield a liveGraphPatches entry whose source is a
// non-empty "sse_event:*" string. Mirrors swarmReconcile.test.ts + the sseClient
// injected-stream mock.

import { afterEach, describe, expect, it } from 'vitest';

import {
  connectLiveStream,
  liveGraphPatches,
  __resetLiveStream,
} from '../../../org/live/sseClient';
import { __resetAttentionQueue } from '../../../org/attention/attentionQueue';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function* mockStream(events: any[]) {
  for (const e of events) yield e;
}

const flush = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => {
  __resetLiveStream();
  __resetAttentionQueue();
});

const EVENTS = [
  { type: 'permission.updated', v: 1, id: 'p1', tool_name: 'Write', args: {}, dimension: 'tool' },
  { type: 'budget.updated', v: 1, session_id: 's1', spent: 10, remaining: 0, limit: 10, unit: 'usd' },
  { type: 'gate.updated', v: 1, session_id: 's1', gate: 'b-verify', decision: 'block' },
];

describe('sseClient liveGraphPatches — honest live signal', () => {
  it('emits one source-tagged patch per mapped event', async () => {
    const handle = connectLiveStream({
      sessionId: 's1',
      cardId: 'cardA',
      stream: mockStream(EVENTS),
    });
    await flush();
    handle.abort();

    const patches = liveGraphPatches();
    expect(patches.length).toBe(3);

    const byType = Object.fromEntries(patches.map((p) => [p.edgeType, p]));
    expect(byType['tool-call'].source).toBe('sse_event:permission.updated');
    expect(byType['message'].source).toBe('sse_event:budget.updated');
    expect(byType['blocker'].source).toBe('sse_event:gate.updated');

    // Honest-signal: every live patch carries a non-empty sse_event source.
    expect(
      patches.every(
        (p) => typeof p.source === 'string' && p.source.startsWith('sse_event:'),
      ),
    ).toBe(true);
  });

  it('does not emit a message patch when the budget threshold is not crossed', async () => {
    const handle = connectLiveStream({
      sessionId: 's1',
      stream: mockStream([
        { type: 'budget.updated', v: 1, session_id: 's1', spent: 2, remaining: 8, limit: 10, unit: 'usd' },
      ]),
    });
    await flush();
    handle.abort();
    expect(liveGraphPatches().length).toBe(0);
  });
});
