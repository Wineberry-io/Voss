import { invoke } from '@tauri-apps/api/core';
import type { CanvasState } from './model';

function serialize(state: CanvasState): CanvasState {
  return JSON.parse(JSON.stringify(state)) as CanvasState;
}

export async function syncCanvasToRust(state: CanvasState): Promise<void> {
  await invoke('sync_canvas', { newState: serialize(state) });
}

type StructuralChangeListener = () => void;
const structuralListeners: StructuralChangeListener[] = [];

/** Subscribe to structural changes (session autosave hooks in here). */
export function subscribeStructuralChange(
  listener: StructuralChangeListener,
): () => void {
  structuralListeners.push(listener);
  return () => {
    const idx = structuralListeners.indexOf(listener);
    if (idx >= 0) structuralListeners.splice(idx, 1);
  };
}

export function notifyStructuralChange(): void {
  for (const listener of structuralListeners) listener();
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
