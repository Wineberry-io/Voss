import { describe, expect, it } from 'vitest';
import {
  createCanvasState,
  makeNode,
  orderedNodes,
  recomputeIndices,
  MIN_NODE_H,
  MIN_NODE_W,
  NODE_GAP,
  type CanvasState,
} from '../model';
import {
  addNode,
  cycleFocus,
  focusByDirection,
  focusByIndex,
  focusNode,
  moveNode,
  placeAdjacent,
  removeNode,
  resizeFocusedByStep,
  resizeNode,
  RESIZE_STEP,
} from '../store';

function state(...rects: [number, number, number, number][]): CanvasState {
  const s = createCanvasState({ cwd: '/r', shell: 'zsh' });
  s.nodes = rects.map(([x, y, w, h], i) => ({
    ...makeNode({ x, y, w, h, cwd: '/r', shell: 'zsh' }),
    id: `n${i + 1}`,
    z: i + 1,
  }));
  recomputeIndices(s.nodes);
  s.focusedId = 'n1';
  return s;
}

describe('indices', () => {
  it('reads row by row, left to right, with a band tolerance', () => {
    const s = state([400, 10, 100, 100], [0, 0, 100, 100], [0, 300, 100, 100], [200, 20, 100, 100]);
    expect(orderedNodes(s).map((n) => n.id)).toEqual(['n2', 'n4', 'n1', 'n3']);
    expect(orderedNodes(s).map((n) => n.index)).toEqual([1, 2, 3, 4]);
  });

  it('moving a node far left makes it index 1', () => {
    const s = state([0, 0, 100, 100], [200, 0, 100, 100]);
    let changed = 0;
    moveNode(s, 'n2', -500, 0, () => changed++);
    expect(orderedNodes(s)[0].id).toBe('n2');
    expect(changed).toBe(1);
  });
});

describe('placeAdjacent', () => {
  it('right: same size, snapped to the right edge, focused', () => {
    const s = state([10, 20, 300, 200]);
    const n = placeAdjacent(s, 'right');
    expect([n.x, n.y, n.w, n.h]).toEqual([10 + 300 + NODE_GAP, 20, 300, 200]);
    expect(s.focusedId).toBe(n.id);
    expect(n.cwd).toBe('/r');
    expect(n.z).toBeGreaterThan(s.nodes[0].z);
  });

  it('below: snapped to the bottom edge', () => {
    const s = state([10, 20, 300, 200]);
    const n = placeAdjacent(s, 'below');
    expect([n.x, n.y]).toEqual([10, 20 + 200 + NODE_GAP]);
  });
});

describe('removeNode', () => {
  it('last node respawns a fresh one in place', () => {
    const s = state([50, 60, 300, 200]);
    removeNode(s, 'n1');
    expect(s.nodes).toHaveLength(1);
    expect(s.nodes[0].id).not.toBe('n1');
    expect([s.nodes[0].x, s.nodes[0].y]).toEqual([50, 60]);
    expect(s.focusedId).toBe(s.nodes[0].id);
  });

  it('focus moves to the neighbour in reading order', () => {
    const s = state([0, 0, 100, 100], [200, 0, 100, 100], [400, 0, 100, 100]);
    focusNode(s, 'n2');
    removeNode(s, 'n2');
    expect(s.nodes.map((n) => n.id)).toEqual(['n1', 'n3']);
    expect(s.focusedId).toBe('n3');
  });

  it('unknown id is a no-op', () => {
    const s = state([0, 0, 100, 100]);
    expect(removeNode(s, 'nope')).toBeNull();
    expect(s.nodes).toHaveLength(1);
  });
});

describe('resize', () => {
  it('clamps to the terminal floor', () => {
    const s = state([0, 0, 500, 400]);
    resizeNode(s, 'n1', 10, 10);
    expect([s.nodes[0].w, s.nodes[0].h]).toEqual([MIN_NODE_W, MIN_NODE_H]);
  });

  it('keyboard step grows and shrinks the focused node', () => {
    const s = state([0, 0, 500, 400]);
    resizeFocusedByStep(s, 'right');
    resizeFocusedByStep(s, 'up');
    expect([s.nodes[0].w, s.nodes[0].h]).toEqual([500 + RESIZE_STEP, 400 - RESIZE_STEP]);
  });
});

describe('focus', () => {
  it('by index, cycle, and direction', () => {
    const s = state([0, 0, 100, 100], [200, 0, 100, 100], [0, 200, 100, 100]);
    focusByIndex(s, 2);
    expect(s.focusedId).toBe('n2');
    cycleFocus(s, 'next');
    expect(s.focusedId).toBe('n3');
    cycleFocus(s, 'next');
    expect(s.focusedId).toBe('n1');
    focusByDirection(s, 'right');
    expect(s.focusedId).toBe('n2');
    focusByDirection(s, 'left');
    focusByDirection(s, 'down');
    expect(s.focusedId).toBe('n3');
    focusByDirection(s, 'down');
    expect(s.focusedId).toBe('n3');
  });

  it('focusing brings the node to the front', () => {
    const s = state([0, 0, 100, 100], [50, 50, 100, 100]);
    focusNode(s, 'n1');
    expect(s.nodes[0].z).toBeGreaterThan(s.nodes[1].z);
  });

  it('addNode focuses and indexes the new node', () => {
    const s = state([0, 0, 100, 100]);
    const n = addNode(s, makeNode({ x: 300, y: 0, w: 100, h: 100 }));
    expect(s.focusedId).toBe(n.id);
    expect(n.index).toBe(2);
  });
});
