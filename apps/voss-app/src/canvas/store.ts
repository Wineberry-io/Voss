/**
 * Pure canvas operations (S1). Each function mutates the passed state and
 * calls `onChange` when something structural happened, mirroring the grid
 * operations contract so callers wrap them in `setStore(produce(...))`.
 */
import {
  MIN_NODE_H,
  MIN_NODE_W,
  NODE_GAP,
  findNode,
  makeNode,
  maxZ,
  orderedNodes,
  recomputeIndices,
  type CanvasNode,
  type CanvasState,
  type CanvasView,
} from './model';
import { boundsOf, clampZoom, type Rect } from './geometry';

export type Side = 'right' | 'below';
export type Direction = 'left' | 'right' | 'up' | 'down';

export const RESIZE_STEP = 40;

export function clampSize(w: number, h: number): { w: number; h: number } {
  return { w: Math.max(MIN_NODE_W, Math.round(w)), h: Math.max(MIN_NODE_H, Math.round(h)) };
}

function finish(state: CanvasState, onChange?: () => void): void {
  recomputeIndices(state.nodes);
  onChange?.();
}

export function focusNode(
  state: CanvasState,
  id: string,
  onChange?: () => void,
): void {
  const n = findNode(state, id);
  if (!n) return;
  state.focusedId = id;
  n.z = maxZ(state.nodes) + 1;
  onChange?.();
}

export function addNode(
  state: CanvasState,
  node: CanvasNode,
  onChange?: () => void,
): CanvasNode {
  node.z = maxZ(state.nodes) + 1;
  state.nodes.push(node);
  state.focusedId = node.id;
  finish(state, onChange);
  return node;
}

/**
 * ⌘D / ⌘⇧D: a new node the same size as the focused one, snapped to its
 * right or bottom edge. Falls back to the origin when nothing is focused.
 */
export function placeAdjacent(
  state: CanvasState,
  side: Side,
  defaults?: { cwd?: string; shell?: string },
  onChange?: () => void,
): CanvasNode {
  const from = findNode(state, state.focusedId);
  const node = makeNode({
    cwd: defaults?.cwd ?? from?.cwd,
    shell: defaults?.shell ?? from?.shell,
    w: from?.w,
    h: from?.h,
    x: from ? (side === 'right' ? from.x + from.w + NODE_GAP : from.x) : 0,
    y: from ? (side === 'below' ? from.y + from.h + NODE_GAP : from.y) : 0,
  });
  return addNode(state, node, onChange);
}

/**
 * Close a node. The app is never empty: closing the last node respawns a
 * fresh default node in its place. Returns the removed id, or null.
 */
export function removeNode(
  state: CanvasState,
  id: string,
  onChange?: () => void,
): string | null {
  const idx = state.nodes.findIndex((n) => n.id === id);
  if (idx < 0) return null;
  const removed = state.nodes[idx];
  state.nodes.splice(idx, 1);
  if (state.nodes.length === 0) {
    const fresh = makeNode({ x: removed.x, y: removed.y, w: removed.w, h: removed.h });
    state.nodes.push(fresh);
    state.focusedId = fresh.id;
  } else if (state.focusedId === id) {
    const ordered = recomputeIndices(state.nodes);
    const pos = Math.min(removed.index - 1, ordered.length - 1);
    state.focusedId = ordered[Math.max(pos, 0)].id;
  }
  finish(state, onChange);
  return id;
}

export function moveNode(
  state: CanvasState,
  id: string,
  x: number,
  y: number,
  onChange?: () => void,
): void {
  const n = findNode(state, id);
  if (!n) return;
  n.x = Math.round(x);
  n.y = Math.round(y);
  finish(state, onChange);
}

export function resizeNode(
  state: CanvasState,
  id: string,
  w: number,
  h: number,
  onChange?: () => void,
): void {
  const n = findNode(state, id);
  if (!n) return;
  const c = clampSize(w, h);
  n.w = c.w;
  n.h = c.h;
  finish(state, onChange);
}

/** ⌘⌥⇧arrow: grow or shrink the focused node by one step along `dir`. */
export function resizeFocusedByStep(
  state: CanvasState,
  dir: Direction,
  onChange?: () => void,
): void {
  const n = findNode(state, state.focusedId);
  if (!n) return;
  const w = dir === 'right' ? n.w + RESIZE_STEP : dir === 'left' ? n.w - RESIZE_STEP : n.w;
  const h = dir === 'down' ? n.h + RESIZE_STEP : dir === 'up' ? n.h - RESIZE_STEP : n.h;
  resizeNode(state, n.id, w, h, onChange);
}

export function focusByIndex(
  state: CanvasState,
  n: number,
  onChange?: () => void,
): void {
  const hit = state.nodes.find((node) => node.index === n);
  if (hit) focusNode(state, hit.id, onChange);
}

export function cycleFocus(
  state: CanvasState,
  dir: 'next' | 'prev',
  onChange?: () => void,
): void {
  const ordered = orderedNodes(state);
  if (ordered.length < 2) return;
  const i = ordered.findIndex((n) => n.id === state.focusedId);
  if (i < 0) return;
  const len = ordered.length;
  const j = dir === 'next' ? (i + 1) % len : (i - 1 + len) % len;
  focusNode(state, ordered[j].id, onChange);
}

/** i3-style nearest node on the requested side of the focused node. */
export function focusByDirection(
  state: CanvasState,
  dir: Direction,
  onChange?: () => void,
): void {
  const f = findNode(state, state.focusedId);
  if (!f) return;
  const horizontal = dir === 'left' || dir === 'right';
  const mid = horizontal ? f.y + f.h / 2 : f.x + f.w / 2;
  const EPS = 0.5;
  let bestId: string | null = null;
  let bestAxis = Infinity;
  let bestPerp = Infinity;
  for (const r of state.nodes) {
    if (r.id === f.id) continue;
    let axisGap: number;
    if (dir === 'right') axisGap = r.x - (f.x + f.w);
    else if (dir === 'left') axisGap = f.x - (r.x + r.w);
    else if (dir === 'down') axisGap = r.y - (f.y + f.h);
    else axisGap = f.y - (r.y + r.h);
    if (axisGap < -EPS) continue;
    const lo = horizontal ? r.y : r.x;
    const hi = horizontal ? r.y + r.h : r.x + r.w;
    const clamped = Math.max(lo, Math.min(mid, hi));
    const perp = Math.abs(clamped - mid);
    const axis = Math.max(0, axisGap);
    if (axis < bestAxis - EPS || (axis <= bestAxis + EPS && perp < bestPerp)) {
      bestAxis = axis;
      bestPerp = perp;
      bestId = r.id;
    }
  }
  if (bestId) focusNode(state, bestId, onChange);
}

export function setView(state: CanvasState, view: CanvasView): void {
  state.view = { x: view.x, y: view.y, zoom: clampZoom(view.zoom) };
}

export function contentBounds(state: CanvasState): Rect | null {
  return boundsOf(state.nodes);
}
