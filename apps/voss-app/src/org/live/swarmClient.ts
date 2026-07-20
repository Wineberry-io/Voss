// VADE2 (V24 swarm surface) — typed client for the V25 server-native swarm plane.
//
// Read-only snapshot of a swarm's authoritative state: GET /swarm/{id} →
// {v, swarm:{id, goal, cwd, roster:[Role], tasks:[Task]}}. This is the structure
// + task-state source of truth; live transitions ride the SSE bus (swarm.* events,
// handled in sseClient.ts / swarmLive.ts). Rust retains loopback credentials.

import { callSidecar } from './sidecarClient';

export interface SwarmRole {
  name: string;
  model: string;
  auth_pref: string;
}

export type SwarmTaskState = 'open' | 'assigned' | 'candidate_ready' | 'done';

export interface SwarmTask {
  id: string;
  goal: string;
  owned_files: string[];
  depends_on: string[];
  state: SwarmTaskState;
  candidate_branch?: string | null;
  candidate_worktree?: string | null;
  candidate_head?: string | null;
}

export interface SwarmSnapshot {
  id: string;
  goal: string;
  cwd: string;
  roster: SwarmRole[];
  tasks: SwarmTask[];
}

/**
 * Fetch a swarm's authoritative snapshot through the Rust sidecar proxy.
 */
export async function fetchSwarm(
  sidecarId: string,
  swarmId: string,
): Promise<SwarmSnapshot> {
  const body = await callSidecar<{ v: number; swarm: SwarmSnapshot }>(sidecarId, {
    kind: 'get_swarm',
    swarm_id: swarmId,
  });
  return body.swarm;
}

/** One spawned roster session returned by POST /swarm (native roles only). */
export interface SpawnedSession {
  session_id?: string; // present for native (in-process) roles
  role: string;
  model?: string;
  agent?: string;
  pending?: boolean; // non-native CLI role recorded but not spawned here
}

export interface CreateSwarmResult {
  id: string;
  sessions: SpawnedSession[];
}

/** One explicit roster role (R3 agent axis) sent to POST /swarm. */
export interface RoleSpecBody {
  name: string;
  /** Agent axis: 'voss' native, or a CLI key (claude/codex/...). */
  agent: string;
  /** '--model' value for CLI roles; ignored for native. */
  model: string;
}

/**
 * Create + spawn a swarm (POST /swarm). With no `roster` the server builds the
 * default (coordinator + N builders + reviewer); an explicit roster is spawned
 * verbatim. Native roles spawn in-process (builders spawn-gated); CLI roles are
 * recorded `pending` and run via runSwarm(). Returns the swarm id + spawned
 * sessions. The coordinator does NOT auto-run — the caller kicks it.
 */
export async function createSwarm(
  sidecarId: string,
  body: {
    goal: string;
    builders?: number;
    cwd?: string | null;
    roster?: RoleSpecBody[];
  },
): Promise<CreateSwarmResult> {
  const out = await callSidecar<{
    v: number;
    id: string;
    sessions: SpawnedSession[];
  }>(sidecarId, {
    kind: 'create_swarm',
    goal: body.goal,
    builders: body.builders ?? 2,
    ...(body.roster && body.roster.length > 0
      ? { roster: body.roster as unknown as Array<Record<string, unknown>> }
      : {}),
  });
  return { id: out.id, sessions: out.sessions ?? [] };
}

/**
 * Drive a swarm's CLI (non-native) roles headlessly (POST /swarm/{id}/run).
 * Fire-and-forget on the server: it worktree-spawns each pending CLI member
 * with its `--model` and streams progress over the swarm SSE plane. Native
 * roles are untouched. No-op to call when a roster is all-native.
 */
export async function runSwarm(
  sidecarId: string,
  swarmId: string,
): Promise<void> {
  await callSidecar(sidecarId, {
    kind: 'run_swarm',
    swarm_id: swarmId,
  });
}
