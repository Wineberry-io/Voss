// V24 swarm surface — app-side launch.
//
// V25 ships the runtime (POST /swarm spawns the roster sessions) but no app
// launch. This wires it: create the swarm, mark it active so the map renders it
// immediately (no registry round-trip), open a live SSE stream on each spawned
// session (swarm.* events fan out to every swarm session queue, so any stream
// receives them all), and kick the coordinator with the goal so it starts
// decomposing/assigning — builders stay spawn-gated until it assigns.

import { connectLiveStream } from './sseClient';
import { createSwarm, runSwarm, type RoleSpecBody } from './swarmClient';
import { setActiveSwarmId } from './swarmLive';
import type { LiveServer } from './liveServer';

const isCoordinator = (role: string) => /^coord/i.test(role);

export interface LaunchSwarmOpts {
  goal: string;
  builders: number;
  /** Explicit roster (per-role agent/model). Omitted → server default roster. */
  roster?: RoleSpecBody[];
}

/**
 * Launch a swarm from the app. Returns the new swarm id. Throws if creation
 * fails (e.g. no credentials → POST /swarm 400).
 */
export async function launchSwarm(
  srv: LiveServer,
  opts: LaunchSwarmOpts,
): Promise<string> {
  const { id, sessions } = await createSwarm(srv.sidecarId, {
    goal: opts.goal,
    builders: opts.builders,
    cwd: srv.cwd,
    roster: opts.roster,
  });
  setActiveSwarmId(id);

  const native = sessions.filter((s) => !!s.session_id);
  for (const s of native) {
    connectLiveStream({
      sidecarId: srv.sidecarId,
      sessionId: s.session_id!,
    });
  }

  // Kick the coordinator: post the goal so it takes its first turn (it is not
  // spawn-gated). Builders unblock when the coordinator emits swarm.assign.
  const coord = native.find((s) => isCoordinator(s.role));
  if (coord?.session_id && srv.followUpClient) {
    await srv.followUpClient.postMessage(coord.session_id, opts.goal);
  }

  // CLI (non-native) roles come back spawn-pending (no session_id); kick the
  // headless driver so they worktree-spawn with their chosen --model. Native-
  // only rosters skip this entirely.
  const hasCli = sessions.some((s) => s.pending || !s.session_id);
  if (hasCli) {
    await runSwarm(srv.sidecarId, id);
  }
  return id;
}
