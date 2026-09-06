import { describe, expect, it } from 'vitest';
import { SNAP_PX, snapRect } from '../snap';

const A = { x: 0, y: 0, w: 300, h: 200 };

describe('snapRect', () => {
  it('AC-S2-1: a left edge within 8 px of a right edge snaps onto it with an x guide', () => {
    const r = snapRect({ x: 300 + SNAP_PX - 1, y: 500, w: 100, h: 100 }, [A]);
    expect(r.x).toBe(300);
    expect(r.y).toBe(500);
    expect(r.guides).toEqual([{ axis: 'x', at: 300 }]);
  });

  it('does not snap beyond the threshold', () => {
    const r = snapRect({ x: 300 + SNAP_PX + 1, y: 500, w: 100, h: 100 }, [A]);
    expect(r.x).toBe(300 + SNAP_PX + 1);
    expect(r.guides).toEqual([]);
  });

  it('snaps centres and both axes at once', () => {
    const r = snapRect({ x: 103, y: 47, w: 100, h: 100 }, [A]);
    expect(r.x).toBe(100);
    expect(r.y).toBe(50);
    expect(r.guides).toEqual([
      { axis: 'x', at: 150 },
      { axis: 'y', at: 100 },
    ]);
  });

  it('prefers the nearest candidate', () => {
    const r = snapRect({ x: 296, y: 500, w: 100, h: 100 }, [A, { x: 298, y: 900, w: 10, h: 10 }]);
    expect(r.x).toBe(298);
  });
});
