import { afterEach, describe, expect, it, vi } from 'vitest';

import { invoke } from '@tauri-apps/api/core';
import { fetchMemory } from '../memoryClient';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), Channel: class {} }));
const mockInvoke = vi.mocked(invoke);
const OK_BODY = { v: 1, summary: '# Memory', query: null, hits: [] };

afterEach(() => vi.clearAllMocks());

describe('fetchMemory', () => {
  it('uses the opaque sidecar operation and sends no cwd or credential', async () => {
    mockInvoke.mockResolvedValueOnce(OK_BODY);
    await expect(fetchMemory('opaque-1', 'rollout', 8)).resolves.toEqual(OK_BODY);
    expect(mockInvoke).toHaveBeenCalledWith('call_voss_sidecar', {
      sidecarId: 'opaque-1',
      operation: { kind: 'memory', query: 'rollout', top_k: 8 },
    });
    expect(JSON.stringify(mockInvoke.mock.calls[0])).not.toContain('token');
    expect(JSON.stringify(mockInvoke.mock.calls[0])).not.toContain('/repo');
  });
});
