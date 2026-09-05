import { describe, it, expect, vi, afterEach } from 'vitest';

import type { VossClient } from '../../../../../../sdk/typescript/src/client/rest';
import {
  serverSessions,
  refreshSessions,
  attachSession,
  sessionId,
  sessionTitle,
  sessionAgeLabel,
  __resetServerSessions,
} from '../serverSessions';
import {
  cardToSessionNode,
  __resetBridgeMaps,
} from '../../model/bridge';

// V15-05 (VLIVE-06): the "Server sessions" list mirrors GET /session honestly
// (newest first, no source filtering, opaque-shape tolerant) and Attach wires
// the forward stream only — no transcript backfill (T-V15-12).

afterEach(() => {
  __resetServerSessions();
  __resetBridgeMaps();
  vi.clearAllMocks();
});

function mockClient(over: Partial<Record<string, unknown>> = {}): VossClient {
  return {
    listSessions: vi.fn().mockResolvedValue([]),
    listSaved: vi.fn(),
    getSession: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    postMessage: vi.fn(),
    abort: vi.fn(),
    getCost: vi.fn(),
    doctor: vi.fn(),
    client: {},
    ...over,
  } as unknown as VossClient;
}

describe('serverSessions — refresh (D-05)', () => {
  it('populates newest-first from listSessions (server order oldest→newest is reversed)', async () => {
    const client = mockClient({
      listSessions: vi.fn().mockResolvedValue([
        { id: 'older-session', title: 'first', cwd: '/a', model: 'm', busy: false },
        { id: 'newer-session', title: 'second', cwd: '/a', model: 'm', busy: true },
      ]),
    });

    await refreshSessions(client);

    expect(serverSessions().map((s) => s.id)).toEqual([
      'newer-session',
      'older-session',
    ]);
  });

  it('degrades silently on a throwing listSessions (empty list, no throw)', async () => {
    const client = mockClient({
      listSessions: vi.fn().mockRejectedValue(new Error('boom')),
    });

    await expect(refreshSessions(client)).resolves.toBeUndefined();
    expect(serverSessions()).toEqual([]);
  });
});

describe('serverSessions — row accessors (opaque SessionInfo, A1)', () => {
  it('id required; title falls back to id; age blank without a timestamp', () => {
    const bare = { id: 'abc123def456' };
    expect(sessionId(bare)).toBe('abc123def456');
    expect(sessionTitle(bare)).toBe('abc123def456');
    expect(sessionAgeLabel(bare)).toBe('');
  });

  it('uses title when present and renders a relative age from a timestamp', () => {
    const twoHoursAgo = Date.now() / 1000 - 2 * 3600;
    const info = { id: 'abc', title: 'fix auth', updated_at: twoHoursAgo };
    expect(sessionTitle(info)).toBe('fix auth');
    expect(sessionAgeLabel(info)).toBe('2h');
  });
});

describe('serverSessions — attachSession (D-06, T-V15-08/T-V15-12)', () => {
  it('ensures the client (respawn-if-cold), registers the native card, opens the pane — no history fetch', async () => {
    const client = mockClient();
    const ensureClient = vi.fn().mockResolvedValue({
      sidecarId: 'test-sidecar',
      client,
    });
    const openAttachedPane = vi.fn();

    await attachSession({
      cwd: '/repo',
      sessionId: 'sess-99',
      ensureClient,
      openAttachedPane,
    });

    expect(ensureClient).toHaveBeenCalledWith('/repo');
    // D-06: attached ≡ started — Bridge A registration.
    expect(cardToSessionNode()['sess-99']).toBe('sess-99');
    expect(openAttachedPane).toHaveBeenCalledWith({
      sessionId: 'sess-99',
      sidecarId: 'test-sidecar',
      client,
    });
    // T-V15-12: forward stream only — no backfill/transcript fetch.
    expect(client.getSession).not.toHaveBeenCalled();
    expect(client.listSaved).not.toHaveBeenCalled();
    expect(client.postMessage).not.toHaveBeenCalled();
  });
});
