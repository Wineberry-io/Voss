import type { Rect, Size } from './geometry';
import { boundsOf, screenToWorld } from './geometry';
import type { CanvasNode, CanvasView } from './model';

export const MINIMAP_MIN_NODES = 3;
export const MINIMAP_SIZE: Size = { w: 180, h: 120 };
const PAD = 6;

export type MinimapLayout = {
  scale: number;
  /** World origin that maps to the minimap's top-left. */
  origin: { x: number; y: number };
  nodes: (Rect & { id: string })[];
  viewport: Rect;
};

/** World rect the viewport shows under `view`. */
export function viewportWorldRect(view: CanvasView, viewport: Size): Rect {
  const tl = screenToWorld(view, 0, 0);
  return { x: tl.x, y: tl.y, w: viewport.w / view.zoom, h: viewport.h / view.zoom };
}

function union(a: Rect, b: Rect): Rect {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  return { x, y, w: Math.max(a.x + a.w, b.x + b.w) - x, h: Math.max(a.y + a.h, b.y + b.h) - y };
}

/** Fit every node plus the viewport into `size`, preserving aspect. */
export function minimapLayout(
  nodes: readonly CanvasNode[],
  view: CanvasView,
  viewport: Size,
  size: Size = MINIMAP_SIZE,
): MinimapLayout {
  const vp = viewportWorldRect(view, viewport);
  const world = union(boundsOf(nodes) ?? vp, vp);
  const scale = Math.min((size.w - PAD * 2) / Math.max(world.w, 1), (size.h - PAD * 2) / Math.max(world.h, 1));
  const origin = {
    x: world.x - (size.w / scale - world.w) / 2,
    y: world.y - (size.h / scale - world.h) / 2,
  };
  const map = (r: Rect): Rect => ({
    x: (r.x - origin.x) * scale,
    y: (r.y - origin.y) * scale,
    w: r.w * scale,
    h: r.h * scale,
  });
  return {
    scale,
    origin,
    nodes: nodes.map((n) => ({ id: n.id, ...map(n) })),
    viewport: map(vp),
  };
}

/** View that centres the world point under minimap pixel (mx, my). */
export function viewCenteredOnMinimapPoint(
  layout: MinimapLayout,
  view: CanvasView,
  viewport: Size,
  mx: number,
  my: number,
): CanvasView {
  const wx = layout.origin.x + mx / layout.scale;
  const wy = layout.origin.y + my / layout.scale;
  return { x: viewport.w / 2 - wx * view.zoom, y: viewport.h / 2 - wy * view.zoom, zoom: view.zoom };
}
