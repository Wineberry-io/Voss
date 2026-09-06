import { invoke } from '@tauri-apps/api/core';
import type { LayoutPreset } from '../canvas/arrange';
import type { LegacyGridStore } from '../canvas/migrate';
import type { CanvasState } from '../canvas/model';

/**
 * Frontend bridge for A6-01 Rust session persistence commands. Mirrors
 * `layoutStorage.ts` — thin invoke wrappers, no remap logic.
 *
 * Tauri converts snake_case Rust param names to camelCase on the JS side;
 * payload keys here MUST match the Rust function signatures from
 * `apps/voss-app/src-tauri/src/lib.rs`.
 */

/** Per-pane scrollback payload — mirrors Rust `SessionPane`. */
export type SessionPane = {
  id: string;
  scrollback: string[] | null;
};

/** v1 (split tree) — still loadable; migrated to v2 on first save. */
export type SessionFileV1 = {
  version: 1;
  activePreset: LayoutPreset | null;
  grid: LegacyGridStore;
  panes: SessionPane[];
  projectLessAccepted: boolean;
};

/** v2 (free canvas) — mirrors Rust `SessionFile` with `canvas` set. */
export type SessionFileV2 = {
  version: 2;
  activePreset: LayoutPreset | null;
  /** Absent only for files Rust wrote from a legacy tree; `grid` is set then. */
  canvas?: CanvasState;
  grid?: LegacyGridStore;
  panes: SessionPane[];
  projectLessAccepted: boolean;
};

/** Wire-level session shape — mirrors Rust `SessionFile`. */
export type SessionFile = SessionFileV1 | SessionFileV2;

// --- Error copy constants (match Rust SessionError::Display) ----------------

export const SESSION_SAVE_FAILED = 'could not save session';
export const SESSION_LOAD_FAILED = 'could not load session';

// --- Tauri command bridges --------------------------------------------------

export async function saveSession(
  workspaceId: string,
  session: SessionFile,
): Promise<void> {
  await invoke('save_session', { workspaceId, session });
}

export async function loadSession(
  workspaceId: string,
): Promise<SessionFile | null> {
  return invoke<SessionFile | null>('load_session', { workspaceId });
}

export async function saveGlobalSession(
  session: SessionFile,
): Promise<void> {
  await invoke('save_global_session', { session });
}

export async function loadGlobalSession(): Promise<SessionFile | null> {
  return invoke<SessionFile | null>('load_global_session');
}
