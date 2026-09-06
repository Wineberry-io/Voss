import type { Rect } from './geometry';

export const SNAP_PX = 8;

export type Guide = { axis: 'x' | 'y'; at: number };

type Candidate = { delta: number; at: number };

function edges(r: Rect, axis: 'x' | 'y'): number[] {
  return axis === 'x' ? [r.x, r.x + r.w / 2, r.x + r.w] : [r.y, r.y + r.h / 2, r.y + r.h];
}

function bestOnAxis(
  moving: Rect,
  others: readonly Rect[],
  axis: 'x' | 'y',
  threshold: number,
): Candidate | null {
  const mine = edges(moving, axis);
  let best: Candidate | null = null;
  for (const o of others) {
    for (const target of edges(o, axis)) {
      for (const m of mine) {
        const delta = target - m;
        if (Math.abs(delta) > threshold) continue;
        if (!best || Math.abs(delta) < Math.abs(best.delta)) best = { delta, at: target };
      }
    }
  }
  return best;
}

/**
 * Snap `moving` to the edges and centres of `others` when within
 * `threshold` world px on an axis. Returns the snapped origin and the guide
 * lines to draw (one per snapped axis).
 */
export function snapRect(
  moving: Rect,
  others: readonly Rect[],
  threshold = SNAP_PX,
): { x: number; y: number; guides: Guide[] } {
  const bx = bestOnAxis(moving, others, 'x', threshold);
  const by = bestOnAxis(moving, others, 'y', threshold);
  const guides: Guide[] = [];
  if (bx) guides.push({ axis: 'x', at: bx.at });
  if (by) guides.push({ axis: 'y', at: by.at });
  return {
    x: moving.x + (bx?.delta ?? 0),
    y: moving.y + (by?.delta ?? 0),
    guides,
  };
}
