import { afterEach, describe, expect, it, vi } from 'vitest';

import { invoke } from '@tauri-apps/api/core';
import { fetchSwarm } from '../swarmClient';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), Channel: class {} }));
const mockInvoke = vi.mocked(invoke);
const SWARM = {
  id: 'sw1',
  goal: 'ship',
  cwd: '/repo',
  roster: [{ name: 'coordinator', model: 'default', auth_pref: 'auto' }],
  tasks: [],
};

afterEach(() => vi.clearAllMocks());

describe('fetchSwarm', () => {
  it('uses the opaque sidecar operation and unwraps the swarm', async () => {
    mockInvoke.mockResolvedValueOnce({ v: 1, swarm: SWARM });
    await expect(fetchSwarm('opaque-1', 'sw1')).resolves.toEqual(SWARM);
    expect(mockInvoke).toHaveBeenCalledWith('call_voss_sidecar', {
      sidecarId: 'opaque-1',
      operation: { kind: 'get_swarm', swarm_id: 'sw1' },
    });
  });
});
