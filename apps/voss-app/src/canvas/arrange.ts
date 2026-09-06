/**
 * Auto-arrangements over free nodes. Pure: takes a node count and a
 * world-space box, returns rects in reading order. Callers assign and
 * recompute indices. Silhouettes match the A4 tree presets: fanout = primary
 * left half + right column; pipeline = one row; swarm = near-square grid up
 * to four columns; watchers = primary top half + bottom row.
 */
import { MIN_NODE_H, MIN_NODE_W, NODE_GAP, type CanvasNode } from './model';
import type { Rect, Size } from './geometry';

export type LayoutPreset = 'fanout' | 'pipeline' | 'swarm' | 'watchers';
export type ActiveLayout = LayoutPreset | 'custom';
export type Arrangement = LayoutPreset | 'grid';

export const LAYOUT_PRESETS: readonly LayoutPreset[] = [
  'fanout',
  'pipeline',
  'swarm',
  'watchers',
] as const;

const SWARM_MAX_COLS = 4;

/** ⌘G cycle: custom snaps to fanout; within the cycle, wrap watchers → fanout. */
export function nextPreset(active: ActiveLayout): LayoutPreset {
  if (active === 'custom') return LAYOUT_PRESETS[0];
  const idx = LAYOUT_PRESETS.indexOf(active);
  return LAYOUT_PRESETS[(idx + 1) % LAYOUT_PRESETS.length];
}

export function isLayoutPreset(value: unknown): value is LayoutPreset {
  return (LAYOUT_PRESETS as readonly unknown[]).includes(value);
}

/** Most columns/rows of at-least-minimum nodes that fit `box`. */
function maxCols(box: Size): number {
  return Math.max(1, Math.floor((box.w + NODE_GAP) / (MIN_NODE_W + NODE_GAP)));
}
function maxRows(box: Size): number {
  return Math.max(1, Math.floor((box.h + NODE_GAP) / (MIN_NODE_H + NODE_GAP)));
}

/** Evenly split `box`; nodes never shrink below the terminal floor, so a box
 * too small for the count overflows instead of producing sub-floor rects. */
function slots(cols: number, rows: number, box: Size, offset = { x: 0, y: 0 }): Rect[] {
  const w = Math.max(MIN_NODE_W, (box.w - NODE_GAP * (cols - 1)) / cols);
  const h = Math.max(MIN_NODE_H, (box.h - NODE_GAP * (rows - 1)) / rows);
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

function squareRects(n: number, box: Size, capCols: number): Rect[] {
  if (n === 0) return [];
  const cols = Math.max(1, Math.min(Math.ceil(Math.sqrt(n)), capCols, maxCols(box)));
  const rows = Math.ceil(n / cols);
  return slots(cols, rows, box).slice(0, n);
}

function gridRects(n: number, box: Size): Rect[] {
  return squareRects(n, box, Infinity);
}

function swarmRects(n: number, box: Size): Rect[] {
  return squareRects(n, box, SWARM_MAX_COLS);
}

/** Primary on the left at half width; the rest stacked in a column on the right. */
function fanoutRects(n: number, box: Size): Rect[] {
  if (n <= 1) return gridRects(n, box);
  const leftW = Math.max(MIN_NODE_W, Math.round((box.w - NODE_GAP) / 2));
  const restBox = { w: Math.max(MIN_NODE_W, box.w - leftW - NODE_GAP), h: box.h };
  const rows = Math.max(1, Math.min(n - 1, maxRows(restBox)));
  const cols = Math.ceil((n - 1) / rows);
  const rest = slots(cols, rows, restBox, { x: leftW + NODE_GAP, y: 0 }).slice(0, n - 1);
  return [{ x: 0, y: 0, w: leftW, h: Math.max(MIN_NODE_H, box.h) }, ...rest];
}

/** Left to right; wraps to more rows once a row cannot hold minimum-width nodes. */
function pipelineRects(n: number, box: Size): Rect[] {
  if (n === 0) return [];
  const cols = Math.max(1, Math.min(n, maxCols(box)));
  const rows = Math.ceil(n / cols);
  return slots(cols, rows, box).slice(0, n);
}

/** Primary on top at half height spanning the width; the rest in a row beneath. */
function watchersRects(n: number, box: Size): Rect[] {
  if (n <= 1) return gridRects(n, box);
  const topH = Math.max(MIN_NODE_H, Math.round((box.h - NODE_GAP) / 2));
  const restBox = { w: box.w, h: Math.max(MIN_NODE_H, box.h - topH - NODE_GAP) };
  const cols = Math.max(1, Math.min(n - 1, maxCols(restBox)));
  const rest = slots(cols, Math.ceil((n - 1) / cols), restBox, { x: 0, y: topH + NODE_GAP }).slice(0, n - 1);
  return [{ x: 0, y: 0, w: Math.max(MIN_NODE_W, box.w), h: topH }, ...rest];
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
    case 'swarm':
      return swarmRects(n, box);
    case 'watchers':
      return watchersRects(n, box);
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
