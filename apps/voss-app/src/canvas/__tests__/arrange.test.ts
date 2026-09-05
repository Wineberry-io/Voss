import { describe, expect, it } from 'vitest';
import { applyArrangement, arrangeRects } from '../arrange';
import { makeNode, NODE_GAP } from '../model';

const box = { w: 1200, h: 800 };

function overlaps(a: { x: number; y: number; w: number; h: number }, b: typeof a): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

describe('arrangements', () => {
  it.each([1, 2, 4, 7])('no arrangement overlaps or escapes the box for %i nodes', (n) => {
    for (const a of ['fanout', 'pipeline', 'swarm', 'watchers', 'grid'] as const) {
      const rects = arrangeRects(a, n, box);
      expect(rects).toHaveLength(n);
      for (let i = 0; i < n; i += 1) {
        expect(rects[i].x).toBeGreaterThanOrEqual(0);
        expect(rects[i].y).toBeGreaterThanOrEqual(0);
        expect(rects[i].x + rects[i].w).toBeLessThanOrEqual(box.w + 1);
        expect(rects[i].y + rects[i].h).toBeLessThanOrEqual(box.h + 1);
        for (let j = i + 1; j < n; j += 1) {
          expect(overlaps(rects[i], rects[j])).toBe(false);
        }
      }
    }
  });

  it('pipeline is one row, fanout puts the first on top full width', () => {
    const p = arrangeRects('pipeline', 3, box);
    expect(new Set(p.map((r) => r.y)).size).toBe(1);
    const f = arrangeRects('fanout', 3, box);
    expect(f[0]).toMatchObject({ x: 0, y: 0, w: box.w });
    expect(f[1].y).toBe(f[0].h + NODE_GAP);
  });

  it('applyArrangement writes rects onto nodes in order', () => {
    const nodes = [makeNode(), makeNode()];
    applyArrangement(nodes, 'grid', box);
    expect(nodes[0].x).toBe(0);
    expect(nodes[1].x).toBeGreaterThan(nodes[0].x);
  });
});
