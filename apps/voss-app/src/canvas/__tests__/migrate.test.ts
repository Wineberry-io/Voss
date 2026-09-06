import { describe, expect, it } from 'vitest';
import { makePane, makeSplit, recomputeIndices } from './legacyTree';
import { gridToCanvas, treeToNodes, type LegacyTreeNode } from '../migrate';
import { NODE_GAP } from '../model';

describe('v1 tree → nodes', () => {
  it('positions leaves proportionally to the ratios', () => {
    const a = makePane({ cwd: '/a', shell: 'zsh' });
    const b = makePane({ cwd: '/b', shell: 'zsh' });
    const c = makePane({ cwd: '/c', shell: 'zsh' });
    const root: LegacyTreeNode = makeSplit('H', a, makeSplit('V', b, c));
    root.ratio = 0.25;
    recomputeIndices(root);

    const nodes = treeToNodes(root, { w: 1000, h: 800 });
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

    expect(byId[a.id].x).toBe(0);
    expect(byId[a.id].w).toBe(Math.round((1000 + NODE_GAP) * 0.25) - NODE_GAP);
    expect(byId[a.id].h).toBe(800);
    expect(byId[b.id].x).toBe(Math.round((1000 + NODE_GAP) * 0.25));
    expect(byId[c.id].y).toBeGreaterThan(byId[b.id].y);
    expect(byId[c.id].cwd).toBe('/c');
    expect(nodes.map((n) => n.index)).toEqual([1, 2, 3]);
  });

  it('keeps ids, focus, and falls back when focus is stale', () => {
    const a = makePane();
    const b = makePane();
    const root = makeSplit('H', a, b);
    recomputeIndices(root);
    const s = gridToCanvas({ root, focusedId: b.id });
    expect(s.focusedId).toBe(b.id);
    expect(s.view).toEqual({ x: 0, y: 0, zoom: 1 });
    const stale = gridToCanvas({ root, focusedId: 'gone' });
    expect(stale.focusedId).toBe(a.id);
  });
});
