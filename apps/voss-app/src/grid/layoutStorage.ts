import { invoke } from '@tauri-apps/api/core';
import type { GridStore } from './tree';
import type { LayoutPreset } from './layoutPresets';

/**
 * Frontend bridge for the A4-03 Rust layout persistence commands. These
 * wrappers carry no remap or geometry logic — that lives in
 * `layoutCommands.ts`. Errors come back as the exact UI-SPEC strings
 * (Rust's `LayoutError::Display` matches the copy table verbatim) so the
 * UI can surface them without translation.
 *
 * Tauri converts snake_case Rust param names to camelCase on the JS
 * side; payload keys here MUST match the Rust function signatures from
 * `apps/voss-app/src-tauri/src/lib.rs`.
 */

/** Wire-level layout shape — mirrors Rust `voss_app_core::layouts::LayoutFile`. */
export type LayoutFile = {
  version: 1;
  activePreset: LayoutPreset | null;
  grid: GridStore;
};

// --- Exact UI-SPEC copy ----------------------------------------------------
// Single source of truth for the renderer and tests; renaming any of these
// is a deliberate spec change.

export const SAVE_LAYOUT_LABEL = 'Save layout as...';
export const LOAD_LAYOUT_LABEL = 'Load layout...';
export const LAYOUT_NAME_PLACEHOLDER = 'layout name';
export const SAVE_SUCCESS = 'layout saved';
export const LOAD_SUCCESS = 'layout loaded';
export const EMPTY_LIST = 'no saved layouts';
export const NAME_EXISTS_CONFIRM = 'replace existing layout?';
export const INVALID_NAME = 'layout name cannot contain /, \\ or ..';
export const NOT_FOUND = 'layout not found';
export const INVALID_FILE = 'layout ignored: invalid file';
export const UNSUPPORTED_VERSION = 'layout ignored: unsupported version';
export const SAVE_FAILED = 'could not save layout';
export const LOAD_FAILED = 'could not load layout';

// --- Tauri command bridges -------------------------------------------------

export async function saveLayout(
  workspaceId: string,
  name: string,
  layout: LayoutFile,
): Promise<void> {
  await invoke('save_layout', { workspaceId, name, layout });
}

export async function loadLayout(
  workspaceId: string,
  name: string,
): Promise<LayoutFile> {
  return invoke<LayoutFile>('load_layout', { workspaceId, name });
}

export async function listLayouts(workspaceId: string): Promise<string[]> {
  return invoke<string[]>('list_layouts', { workspaceId });
}

export async function loadDefaultLayout(
  workspaceId: string,
): Promise<LayoutFile | null> {
  return invoke<LayoutFile | null>('load_default_layout', { workspaceId });
}
