import { ZOOM_MAX, ZOOM_MIN, type CanvasNode, type CanvasView } from './model';

export type Rect = { x: number; y: number; w: number; h: number };
export type Size = { w: number; h: number };

export function clampZoom(z: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
}

export function screenToWorld(
  view: CanvasView,
  sx: number,
  sy: number,
): { x: number; y: number } {
  return { x: (sx - view.x) / view.zoom, y: (sy - view.y) / view.zoom };
}

export function worldToScreen(
  view: CanvasView,
  wx: number,
  wy: number,
): { x: number; y: number } {
  return { x: wx * view.zoom + view.x, y: wy * view.zoom + view.y };
}

/** Zoom so the world point under (sx, sy) stays under the cursor. */
export function zoomAt(
  view: CanvasView,
  nextZoom: number,
  sx: number,
  sy: number,
): CanvasView {
  const zoom = clampZoom(nextZoom);
  const before = screenToWorld(view, sx, sy);
  return {
    zoom,
    x: sx - before.x * zoom,
    y: sy - before.y * zoom,
  };
}

export function boundsOf(nodes: readonly CanvasNode[]): Rect | null {
  if (nodes.length === 0) return null;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const n of nodes) {
    x0 = Math.min(x0, n.x);
    y0 = Math.min(y0, n.y);
    x1 = Math.max(x1, n.x + n.w);
    y1 = Math.max(y1, n.y + n.h);
  }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** View that frames `bounds` inside `viewport` with `padding` screen px. */
export function fitToBounds(
  bounds: Rect,
  viewport: Size,
  padding = 32,
): CanvasView {
  const availW = Math.max(viewport.w - padding * 2, 1);
  const availH = Math.max(viewport.h - padding * 2, 1);
  const zoom = clampZoom(
    Math.min(availW / Math.max(bounds.w, 1), availH / Math.max(bounds.h, 1), 1),
  );
  return {
    zoom,
    x: (viewport.w - bounds.w * zoom) / 2 - bounds.x * zoom,
    y: (viewport.h - bounds.h * zoom) / 2 - bounds.y * zoom,
  };
}

/** View that puts `node` at zoom 1 centred in `viewport`. */
export function centerOn(node: Rect, viewport: Size): CanvasView {
  return {
    zoom: 1,
    x: (viewport.w - node.w) / 2 - node.x,
    y: (viewport.h - node.h) / 2 - node.y,
  };
}

/** Is `sx,sy` (screen) inside `node` under `view`? */
export function hitTest(
  view: CanvasView,
  nodes: readonly CanvasNode[],
  sx: number,
  sy: number,
): CanvasNode | undefined {
  const p = screenToWorld(view, sx, sy);
  let best: CanvasNode | undefined;
  for (const n of nodes) {
    if (p.x >= n.x && p.x <= n.x + n.w && p.y >= n.y && p.y <= n.y + n.h) {
      if (!best || n.z > best.z) best = n;
    }
  }
  return best;
}

export function intersects(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/** Normalise a rect dragged from `a` to `b` (either corner may be the origin). */
export function rectFromPoints(
  a: { x: number; y: number },
  b: { x: number; y: number },
): Rect {
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    w: Math.abs(b.x - a.x),
    h: Math.abs(b.y - a.y),
  };
}

export function nodesIntersecting(nodes: readonly CanvasNode[], rect: Rect): CanvasNode[] {
  return nodes.filter((n) => intersects(n, rect));
}

/**
 * Smallest pan that shows `node` inside `viewport` with `padding` screen px
 * at the current zoom; a node larger than the viewport is centred instead.
 * Returns `view` unchanged when the node is already visible.
 */
export function panToReveal(
  view: CanvasView,
  node: Rect,
  viewport: Size,
  padding = 32,
): CanvasView {
  const z = view.zoom;
  const left = node.x * z + view.x;
  const top = node.y * z + view.y;
  const w = node.w * z;
  const h = node.h * z;
  let dx = 0;
  let dy = 0;
  if (w + padding * 2 > viewport.w) dx = (viewport.w - w) / 2 - left;
  else if (left < padding) dx = padding - left;
  else if (left + w > viewport.w - padding) dx = viewport.w - padding - (left + w);
  if (h + padding * 2 > viewport.h) dy = (viewport.h - h) / 2 - top;
  else if (top < padding) dy = padding - top;
  else if (top + h > viewport.h - padding) dy = viewport.h - padding - (top + h);
  if (dx === 0 && dy === 0) return view;
  return { x: view.x + dx, y: view.y + dy, zoom: z };
}
