import { afterEach, describe, expect, it, vi } from 'vitest';

import { createSidecarVossClient } from '../sidecarClient';
import { buildVossClientFromHandle } from '../vossClientBuild';

vi.mock('../sidecarClient', () => ({
  createSidecarVossClient: vi.fn(),
}));

const mockCreateClient = vi.mocked(createSidecarVossClient);

function mockClient() {
  return {
    createSession: vi.fn().mockResolvedValue('sess-abc123'),
    postMessage: vi.fn().mockResolvedValue({ status: 'accepted' }),
  } as unknown as ReturnType<typeof createSidecarVossClient>;
}

afterEach(() => vi.clearAllMocks());

describe('buildVossClientFromHandle', () => {
  it('builds the client from an opaque sidecar id only', () => {
    const client = mockClient();
    mockCreateClient.mockReturnValueOnce(client);
    const built = buildVossClientFromHandle({ sidecarId: 'opaque-1' });

    expect(mockCreateClient).toHaveBeenCalledWith('opaque-1');
    expect(built.sidecarId).toBe('opaque-1');
    expect(built.client).toBe(client);
    expect(JSON.stringify(built)).not.toContain('token');
    expect(JSON.stringify(built)).not.toContain('127.0.0.1');
  });

  it('adapts createSession and follow-up calls', async () => {
    const client = mockClient();
    mockCreateClient.mockReturnValueOnce(client);
    const built = buildVossClientFromHandle({ sidecarId: 'opaque-1' });

    await expect(
      built.runNativeClient.createSession({
        goal: 'fix',
        mode: 'Plan',
        team: 'solo',
        target: 'native',
      }),
    ).resolves.toEqual({ id: 'sess-abc123' });
    await built.followUpClient.postMessage('sess-abc123', 'retry');
    expect(client.postMessage).toHaveBeenCalledWith('sess-abc123', 'retry');
  });
});
