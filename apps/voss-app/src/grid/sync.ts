import { invoke } from '@tauri-apps/api/core';
import type { GridStore } from './tree';

/**
 * Solid→Rust mirror sync (GRD-08, A1 D-09 seam).
 *
 * Cadence (A3-CONTEXT discretion): structural changes
 * (split/fork/close/focus/equalize) sync IMMEDIATELY; drag-resize coalesces —
 * no sync per pointer-move, exactly one sync on pointer-up. No return value
 * is consumed (A3 = in-memory mirror, no read-back, no disk I/O).
 */

/** Deep structural clone — strips Solid store proxies to a plain object. */
function serialize(state: GridStore): GridStore {
  return JSON.parse(JSON.stringify(state)) as GridStore;
}

export async function syncGridToRust(state: GridStore): Promise<void> {
  await invoke('sync_grid', { newState: serialize(state) });
}

// A6: structural-change listeners. Session autosave hooks in here.
type StructuralChangeListener = () => void;
const structuralListeners: StructuralChangeListener[] = [];

/** Subscribe to structural changes. Returns an unsubscribe function. */
export function subscribeStructuralChange(
  listener: StructuralChangeListener,
): () => void {
  structuralListeners.push(listener);
  return () => {
    const idx = structuralListeners.indexOf(listener);
    if (idx >= 0) structuralListeners.splice(idx, 1);
  };
}

/** Fire every structural-change listener (session autosave hooks). */
export function notifyStructuralChange(): void {
  for (const listener of structuralListeners) listener();
}

/** Structural change → sync now (split/fork/close/focus/equalize). */
export function markStructuralChange(state: GridStore): void {
  void syncGridToRust(state);
  notifyStructuralChange();
}

// Drag coalescer: pointer-move stores the latest state but never syncs;
// pointer-up flushes exactly one sync.
let pendingDrag: GridStore | null = null;

/** Pointer-move during a resize drag — record, do NOT sync (coalesced). */
export function markDragMove(state: GridStore): void {
  pendingDrag = state;
}

/** Pointer-up — flush the coalesced drag state in a single sync. */
export function markDragSettled(state: GridStore): void {
  const finalState = pendingDrag ?? state;
  pendingDrag = null;
  void syncGridToRust(finalState);
}
