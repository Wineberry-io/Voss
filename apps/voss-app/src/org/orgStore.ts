// Org-view data store: the SolidJS surface over the V11 Tauri data commands.
// Every panel renders from `runData()`; this is the single load path. The
// `load_run` result is validated through assertRunData (D-02) so contract drift
// surfaces as an explicit error rather than a half-rendered board.

import { createSignal } from 'solid-js';
import { invoke } from '@tauri-apps/api/core';
import { assertRunData } from './guards';
import type { RunData, RunEntry } from './types';

export const [runData, setRunData] = createSignal<RunData | null>(null);
export const [runEntries, setRunEntries] = createSignal<RunEntry[]>([]);
export const [loadError, setLoadError] = createSignal<string | null>(null);
export const [loading, setLoading] = createSignal(false);
export const [currentRunId, setCurrentRunId] = createSignal<string | null>(null);
// Decision context for the CLI write path (D-07/D-08): the cwd + voss binary the
// current run was loaded with. Panels (e.g. BlockedPanel) read these to shell a
// decision via run_decision without re-threading them through the shell.
export const [currentCwd, setCurrentCwd] = createSignal<string>('');
export const [currentCliBinary, setCurrentCliBinary] = createSignal<string>('voss');

/** Load + validate a single run (D-01/D-02). */
export async function loadRun(
  runId: string,
  cwd: string,
  cliBinary: string,
): Promise<void> {
  setLoading(true);
  setLoadError(null);
  setCurrentRunId(runId);
  setCurrentCwd(cwd);
  setCurrentCliBinary(cliBinary);
  try {
    const raw = await invoke<RunData>('load_run', { runId });
    // Boundary validation: drift → explicit error (D-02).
    const data = assertRunData(raw);
    setRunData(data);
  } catch (e) {
    setLoadError(String(e));
    setRunData(null);
  } finally {
    setLoading(false);
  }
}

/** Discover V4+ runs, newest first (D-03). */
export async function enumerateRuns(_cwd: string): Promise<RunEntry[]> {
  const entries = await invoke<RunEntry[]>('enumerate_runs');
  setRunEntries(entries);
  return entries;
}

/** Re-load the current run (D-08 auto-refresh after a decision). */
export async function refreshRun(cwd: string, cliBinary: string): Promise<void> {
  const id = currentRunId();
  if (!id) return;
  await loadRun(id, cwd, cliBinary);
}
