/**
 * Auto-arrangements over free nodes (S1 subset; S2 adds templates). Pure:
 * takes nodes in reading order and a world-space box, returns rects in the
 * same order. Callers assign and recompute indices.
 */
import { NODE_GAP, type CanvasNode } from './model';
import type { Rect, Size } from './geometry';
import type { LayoutPreset } from '../grid/layoutPresets';

export type Arrangement = LayoutPreset | 'grid';

function slots(cols: number, rows: number, box: Size, offset = { x: 0, y: 0 }): Rect[] {
  const w = (box.w - NODE_GAP * (cols - 1)) / cols;
  const h = (box.h - NODE_GAP * (rows - 1)) / rows;
  const out: Rect[] = [];
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      out.push({
        x: Math.round(offset.x + c * (w + NODE_GAP)),
        y: Math.round(offset.y + r * (h + NODE_GAP)),
        w: Math.round(w),
        h: Math.round(h),
      });
    }
  }
  return out;
}

function gridRects(n: number, box: Size): Rect[] {
  if (n === 0) return [];
  const cols = Math.ceil(Math.sqrt(n));
  const rows = Math.ceil(n / cols);
  return slots(cols, rows, box).slice(0, n);
}

/** One primary on top spanning the width, the rest in a row beneath. */
function fanoutRects(n: number, box: Size): Rect[] {
  if (n <= 1) return gridRects(n, box);
  const topH = Math.round(box.h * 0.5);
  const rest = slots(n - 1, 1, { w: box.w, h: box.h - topH - NODE_GAP }, { x: 0, y: topH + NODE_GAP });
  return [{ x: 0, y: 0, w: box.w, h: topH }, ...rest];
}

/** Single row, left to right. */
function pipelineRects(n: number, box: Size): Rect[] {
  return slots(Math.max(n, 1), 1, box).slice(0, n);
}

/** One primary on the left at two thirds, the rest stacked on the right. */
function watchersRects(n: number, box: Size): Rect[] {
  if (n <= 1) return gridRects(n, box);
  const leftW = Math.round(box.w * (2 / 3));
  const rest = slots(1, n - 1, { w: box.w - leftW - NODE_GAP, h: box.h }, { x: leftW + NODE_GAP, y: 0 });
  return [{ x: 0, y: 0, w: leftW, h: box.h }, ...rest];
}

export function arrangeRects(
  arrangement: Arrangement,
  n: number,
  box: Size,
): Rect[] {
  switch (arrangement) {
    case 'fanout':
      return fanoutRects(n, box);
    case 'pipeline':
      return pipelineRects(n, box);
    case 'watchers':
      return watchersRects(n, box);
    case 'swarm':
    case 'grid':
    default:
      return gridRects(n, box);
  }
}

/** Assign arrangement rects to `nodes` (already in reading order), in place. */
export function applyArrangement(
  nodes: CanvasNode[],
  arrangement: Arrangement,
  box: Size,
): void {
  const rects = arrangeRects(arrangement, nodes.length, box);
  nodes.forEach((node, i) => {
    const r = rects[i];
    node.x = r.x;
    node.y = r.y;
    node.w = r.w;
    node.h = r.h;
  });
}
