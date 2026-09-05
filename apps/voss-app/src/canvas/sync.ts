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

let dragInFlight = false;

/** Pointer-move during a drag: nothing is mirrored until the pointer settles. */
export function markCanvasDragMove(): void {
  dragInFlight = true;
}

/** Pointer-up: mirror the caller's settled state exactly once. */
export function markCanvasDragSettled(state: CanvasState): void {
  dragInFlight = false;
  markCanvasChange(state);
}

export function isCanvasDragInFlight(): boolean {
  return dragInFlight;
}

/** Drag abandoned (pointer cancelled, host unmounted): nothing to mirror. */
export function resetCanvasDrag(): void {
  dragInFlight = false;
}
