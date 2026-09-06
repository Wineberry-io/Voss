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

  it('pipeline is one row; fanout puts the first on the left at half width; watchers on top full width', () => {
    const p = arrangeRects('pipeline', 3, box);
    expect(new Set(p.map((r) => r.y)).size).toBe(1);
    const f = arrangeRects('fanout', 3, box);
    expect(f[0]).toMatchObject({ x: 0, y: 0, h: box.h });
    expect(f[0].w).toBe(Math.round((box.w - NODE_GAP) / 2));
    expect(f[1].x).toBe(f[0].w + NODE_GAP);
    expect(f[2].y).toBeGreaterThan(f[1].y);
    const w = arrangeRects('watchers', 3, box);
    expect(w[0]).toMatchObject({ x: 0, y: 0, w: box.w });
    expect(w[1].y).toBe(w[0].h + NODE_GAP);
    expect(w[2].x).toBeGreaterThan(w[1].x);
  });

  it('swarm caps at four columns; grid does not', () => {
    const s = arrangeRects('swarm', 20, { w: 4000, h: 3000 });
    expect(new Set(s.map((r) => r.x)).size).toBe(4);
    const g = arrangeRects('grid', 20, { w: 4000, h: 3000 });
    expect(new Set(g.map((r) => r.x)).size).toBe(5);
  });

  it('AC-S2-4: preset silhouettes are stable for 1, 2, 4, 7 nodes', () => {
    const out: Record<string, unknown> = {};
    for (const a of ['fanout', 'pipeline', 'swarm', 'watchers'] as const) {
      for (const n of [1, 2, 4, 7]) out[`${a}/${n}`] = arrangeRects(a, n, box);
    }
    expect(out).toMatchSnapshot();
  });

  it('applyArrangement writes rects onto nodes in order', () => {
    const nodes = [makeNode(), makeNode()];
    applyArrangement(nodes, 'grid', box);
    expect(nodes[0].x).toBe(0);
    expect(nodes[1].x).toBeGreaterThan(nodes[0].x);
  });
});

describe('minimum sizes', () => {
  it('never emits a rect below the terminal floor, even for many nodes in a small box', async () => {
    const { MIN_NODE_H, MIN_NODE_W } = await import('../model');
    for (const a of ['fanout', 'pipeline', 'swarm', 'watchers', 'grid'] as const) {
      for (const n of [1, 5, 20]) {
        for (const r of arrangeRects(a, n, { w: 400, h: 200 })) {
          expect(r.w).toBeGreaterThanOrEqual(MIN_NODE_W);
          expect(r.h).toBeGreaterThanOrEqual(MIN_NODE_H);
        }
      }
    }
  });
});
