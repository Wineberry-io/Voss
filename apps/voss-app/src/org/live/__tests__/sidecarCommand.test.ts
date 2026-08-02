import { afterEach, describe, expect, it, vi } from 'vitest';

import { invoke } from '@tauri-apps/api/core';
import { startVossServe } from '../sidecarClient';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), Channel: class {} }));

const mockInvoke = vi.mocked(invoke);

afterEach(() => vi.clearAllMocks());

describe('startVossServe', () => {
  it('returns only the opaque Rust-owned sidecar handle', async () => {
    mockInvoke.mockResolvedValueOnce({ sidecarId: 'opaque-1' });
    const handle = await startVossServe('/some/cwd');

    expect(mockInvoke).toHaveBeenCalledWith('start_voss_serve', {
      cwd: '/some/cwd',
    });
    expect(handle).toEqual({ sidecarId: 'opaque-1' });
    expect(JSON.stringify(handle)).not.toContain('token');
    expect(JSON.stringify(handle)).not.toContain('port');
  });

  it('propagates command errors', async () => {
    mockInvoke.mockRejectedValueOnce('workspace path does not exist');
    await expect(startVossServe('/missing')).rejects.toBe(
      'workspace path does not exist',
    );
  });
});
