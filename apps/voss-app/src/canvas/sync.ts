import { invoke } from '@tauri-apps/api/core';
import { notifyStructuralChange } from '../grid/sync';
import type { CanvasState } from './model';

function serialize(state: CanvasState): CanvasState {
  return JSON.parse(JSON.stringify(state)) as CanvasState;
}

export async function syncCanvasToRust(state: CanvasState): Promise<void> {
  await invoke('sync_canvas', { newState: serialize(state) });
}

/** Structural change (add/remove/move/resize/focus): mirror now, autosave later. */
export function markCanvasChange(state: CanvasState): void {
  void syncCanvasToRust(state).catch(() => {});
  notifyStructuralChange();
}

let pendingDrag: CanvasState | null = null;

export function markCanvasDragMove(state: CanvasState): void {
  pendingDrag = state;
}

export function markCanvasDragSettled(state: CanvasState): void {
  const final = pendingDrag ?? state;
  pendingDrag = null;
  markCanvasChange(final);
}
