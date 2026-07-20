// V24 swarm surface — launchSwarm orchestration: create → activate → stream → kick.

import { afterEach, describe, expect, it, vi } from 'vitest';

const createSwarm = vi.fn();
const runSwarm = vi.fn().mockResolvedValue(undefined);
const connectLiveStream = vi.fn((_args?: unknown) => ({ abort: vi.fn() }));

vi.mock('../swarmClient', () => ({
  createSwarm: (sidecarId: string, body: unknown) =>
    createSwarm(sidecarId, body),
  runSwarm: (sidecarId: string, id: string) => runSwarm(sidecarId, id),
}));
vi.mock('../sseClient', () => ({
  connectLiveStream: (args: unknown) => connectLiveStream(args),
}));

import { launchSwarm } from '../swarmLaunch';
import { activeSwarmId, __resetSwarmLive } from '../swarmLive';

afterEach(() => {
  __resetSwarmLive();
  createSwarm.mockReset();
  runSwarm.mockReset();
  runSwarm.mockResolvedValue(undefined);
  connectLiveStream.mockReset();
});

describe('launchSwarm', () => {
  it('creates the swarm, marks it active, streams native sessions, kicks the coordinator', async () => {
    createSwarm.mockResolvedValue({
      id: 'sw9',
      sessions: [
        { session_id: 's-co', role: 'coordinator' },
        { session_id: 's-b1', role: 'builder-1' },
        { role: 'cli-builder', pending: true }, // non-native: no session_id
      ],
    });
    const postMessage = vi.fn().mockResolvedValue(undefined);
    const srv = { sidecarId: 'test-sidecar', cwd: '/repo', followUpClient: { postMessage } };

    const id = await launchSwarm(srv, { goal: 'ship it', builders: 2 });

    expect(id).toBe('sw9');
    expect(activeSwarmId()).toBe('sw9');
    expect(createSwarm).toHaveBeenCalledWith('http://x', 't', {
      goal: 'ship it',
      builders: 2,
      cwd: '/repo',
    });
    // streams only the 2 native sessions (pending CLI role skipped)
    expect(connectLiveStream).toHaveBeenCalledTimes(2);
    // coordinator kicked with the goal
    expect(postMessage).toHaveBeenCalledWith('s-co', 'ship it');
    // a pending CLI role is present → the headless driver is kicked
    expect(runSwarm).toHaveBeenCalledWith('http://x', 't', 'sw9');
  });

  it('forwards an explicit roster and skips runSwarm when all roles are native', async () => {
    createSwarm.mockResolvedValue({
      id: 'sw10',
      sessions: [
        { session_id: 's-co', role: 'coordinator' },
        { session_id: 's-b1', role: 'builder-1' },
      ],
    });
    const roster = [
      { name: 'coordinator', agent: 'voss', model: 'default' },
      { name: 'builder-1', agent: 'voss', model: 'default' },
    ];
    const srv = { sidecarId: 'test-sidecar', cwd: '/repo' };

    await launchSwarm(srv, { goal: 'go', builders: 1, roster });

    expect(createSwarm).toHaveBeenCalledWith('http://x', 't', {
      goal: 'go',
      builders: 1,
      cwd: '/repo',
      roster,
    });
    // all sessions native (session_id present) → no CLI driver call
    expect(runSwarm).not.toHaveBeenCalled();
  });

  it('propagates a creation failure (e.g. no credentials)', async () => {
    createSwarm.mockRejectedValue(new Error('POST /swarm failed: 400'));
    const srv = { sidecarId: 'test-sidecar', cwd: '/repo' };
    await expect(launchSwarm(srv, { goal: 'g', builders: 2 })).rejects.toThrow(/400/);
    expect(activeSwarmId()).toBeNull();
  });
});
