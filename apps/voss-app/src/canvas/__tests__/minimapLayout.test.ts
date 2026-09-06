import { describe, expect, it } from 'vitest';
import { makeNode } from '../model';
import { MINIMAP_SIZE, minimapLayout, viewCenteredOnMinimapPoint, viewportWorldRect } from '../minimapLayout';

const vp = { w: 1000, h: 800 };

describe('minimap layout', () => {
  it('fits nodes and the viewport inside the map and preserves aspect', () => {
    const nodes = [
      { ...makeNode({ x: 0, y: 0, w: 500, h: 400 }), id: 'a' },
      { ...makeNode({ x: 3000, y: 0, w: 500, h: 400 }), id: 'b' },
    ];
    const l = minimapLayout(nodes, { x: 0, y: 0, zoom: 1 }, vp);
    for (const r of [...l.nodes, l.viewport]) {
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.y).toBeGreaterThanOrEqual(0);
      expect(r.x + r.w).toBeLessThanOrEqual(MINIMAP_SIZE.w + 0.01);
      expect(r.y + r.h).toBeLessThanOrEqual(MINIMAP_SIZE.h + 0.01);
    }
    expect(l.nodes[0].w / l.nodes[0].h).toBeCloseTo(500 / 400, 5);
    expect(l.nodes[1].x).toBeGreaterThan(l.nodes[0].x + l.nodes[0].w);
  });

  it('viewport rect follows the view', () => {
    expect(viewportWorldRect({ x: -100, y: 50, zoom: 0.5 }, vp)).toEqual({ x: 200, y: -100, w: 2000, h: 1600 });
  });

  it('clicking a map point centres the view on that world point', () => {
    const nodes = [{ ...makeNode({ x: 0, y: 0, w: 1000, h: 800 }), id: 'a' }];
    const view = { x: 0, y: 0, zoom: 1 };
    const l = minimapLayout(nodes, view, vp);
    const centre = l.nodes[0];
    const next = viewCenteredOnMinimapPoint(l, view, vp, centre.x + centre.w / 2, centre.y + centre.h / 2);
    expect(next.zoom).toBe(1);
    expect(next.x).toBeCloseTo(vp.w / 2 - 500, 5);
    expect(next.y).toBeCloseTo(vp.h / 2 - 400, 5);
  });
});
