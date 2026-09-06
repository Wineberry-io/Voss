import { describe, expect, it } from 'vitest';
import { makeNode, ZOOM_MAX, ZOOM_MIN } from '../model';
import {
  boundsOf,
  centerOn,
  clampZoom,
  fitToBounds,
  hitTest,
  screenToWorld,
  worldToScreen,
  zoomAt,
} from '../geometry';

describe('transforms', () => {
  it('screen ↔ world round-trips', () => {
    const view = { x: 120, y: -40, zoom: 0.5 };
    const w = screenToWorld(view, 300, 200);
    const s = worldToScreen(view, w.x, w.y);
    expect(s.x).toBeCloseTo(300);
    expect(s.y).toBeCloseTo(200);
  });

  it('zoomAt keeps the point under the cursor fixed', () => {
    const view = { x: 10, y: 20, zoom: 1 };
    const before = screenToWorld(view, 400, 300);
    const next = zoomAt(view, 2, 400, 300);
    const after = screenToWorld(next, 400, 300);
    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
    expect(next.zoom).toBe(2);
  });

  it('clamps zoom', () => {
    expect(clampZoom(0)).toBe(ZOOM_MIN);
    expect(clampZoom(99)).toBe(ZOOM_MAX);
  });
});

describe('bounds and fit', () => {
  const nodes = [
    makeNode({ x: 0, y: 0, w: 400, h: 300 }),
    makeNode({ x: 800, y: 500, w: 400, h: 300 }),
  ];

  it('bounds covers every node', () => {
    expect(boundsOf(nodes)).toEqual({ x: 0, y: 0, w: 1200, h: 800 });
    expect(boundsOf([])).toBeNull();
  });

  it('fitToBounds frames everything inside the viewport at ≤ 1 zoom', () => {
    const v = fitToBounds(boundsOf(nodes)!, { w: 600, h: 400 }, 20);
    expect(v.zoom).toBeLessThan(1);
    const tl = worldToScreen(v, 0, 0);
    const br = worldToScreen(v, 1200, 800);
    expect(tl.x).toBeGreaterThanOrEqual(19);
    expect(br.x).toBeLessThanOrEqual(581);
    expect(br.y).toBeLessThanOrEqual(381);
  });

  it('centerOn puts the node in the middle at zoom 1', () => {
    const v = centerOn({ x: 100, y: 100, w: 200, h: 100 }, { w: 1000, h: 800 });
    const c = worldToScreen(v, 200, 150);
    expect(c).toEqual({ x: 500, y: 400 });
  });

  it('hitTest prefers the top-most node', () => {
    const a = { ...makeNode({ x: 0, y: 0, w: 100, h: 100 }), z: 1 };
    const b = { ...makeNode({ x: 50, y: 50, w: 100, h: 100 }), z: 2 };
    expect(hitTest({ x: 0, y: 0, zoom: 1 }, [a, b], 75, 75)?.id).toBe(b.id);
    expect(hitTest({ x: 0, y: 0, zoom: 1 }, [a, b], 10, 10)?.id).toBe(a.id);
    expect(hitTest({ x: 0, y: 0, zoom: 1 }, [a, b], 500, 500)).toBeUndefined();
  });
});
