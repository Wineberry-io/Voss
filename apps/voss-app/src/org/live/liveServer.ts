// V24 swarm surface — module accessor for the live `voss serve` connection.
//
// The swarm surface (and its command bar) are mounted prop-less, so they reach the
// live server through this module signal instead of props. App sets it from the
// BuiltVossClient inside ensureVossClient; surfaces receive only an opaque
// Rust-owned sidecar handle plus the follow-up client.

import { createSignal } from 'solid-js';

export interface FollowUpLike {
  postMessage(sessionId: string, text: string): Promise<unknown>;
}

export interface LiveServer {
  sidecarId: string;
  /** Workspace cwd — needed to discover the active swarm from the agent registry. */
  cwd?: string | null;
  followUpClient?: FollowUpLike;
}

const [liveServer, setLiveServer] = createSignal<LiveServer | null>(null);

export { liveServer, setLiveServer };

// On-demand connect: the swarm surface is prop-less, so it can't reach App's
// `ensureVossClient`. App registers a connector here (a closure that spawns the
// `voss serve` sidecar for the active workspace and calls setLiveServer as a
// side-effect). Surfaces call connectLiveServer() to start the server without a
// prior native run — e.g. launching an orchestra from a cold workspace.
export type LiveServerConnector = () => Promise<unknown>;

let connector: LiveServerConnector | null = null;

/** App registers (or clears) the sidecar-spawning connector. */
export function setLiveServerConnector(fn: LiveServerConnector | null): void {
  connector = fn;
}

/** Whether on-demand connect is wired (App mounted). */
export function canConnectLiveServer(): boolean {
  return connector != null;
}

/**
 * Ensure a live server, spawning the sidecar on demand. Returns the connected
 * LiveServer, or null when there's nothing to connect to (no connector, or no
 * workspace folder). The connector populates the signal via setLiveServer; we
 * re-read it after it resolves. Propagates connector errors (sidecar failures).
 */
export async function connectLiveServer(): Promise<LiveServer | null> {
  const current = liveServer();
  if (current) return current;
  if (!connector) return null;
  await connector();
  return liveServer();
}

/** Test-only reset. */
export function __resetLiveServer(): void {
  setLiveServer(null);
  connector = null;
}
