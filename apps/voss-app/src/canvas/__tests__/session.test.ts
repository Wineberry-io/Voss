import { describe, expect, it } from 'vitest';
import { makePane, makeSplit, recomputeIndices as treeIndices } from './legacyTree';
import type { SessionFileV1 } from '../../grid/sessionStorage';
import {
  applyLayoutToCanvas,
  applySessionFile,
  buildSessionFile,
  layoutToSession,
  serializeLayout,
} from '../session';
import { createCanvasState, makeNode, orderedNodes, recomputeIndices, type CanvasState } from '../model';

function two(): CanvasState {
  const s = createCanvasState({ cwd: '/r', shell: 'zsh' });
  s.nodes = [
    { ...makeNode({ x: 0, y: 0, w: 300, h: 200, cwd: '/a', shell: 'zsh' }), id: 'a', z: 1 },
    { ...makeNode({ x: 400, y: 0, w: 300, h: 200, cwd: '/b', shell: 'zsh' }), id: 'b', z: 2 },
  ];
  recomputeIndices(s.nodes);
  s.focusedId = 'b';
  s.view = { x: 10, y: 20, zoom: 0.8 };
  return s;
}

describe('session v2', () => {
  it('build strips runtime fields, caps scrollback, orders panes', () => {
    const s = two();
    (s.nodes[0] as unknown as { ptyId: string }).ptyId = 'leak';
    const sb = new Map([['a', Array.from({ length: 3000 }, (_, i) => `l${i}`)]]);
    const file = buildSessionFile(s, 'fanout', sb, true);
    expect(file.version).toBe(2);
    expect(file.activePreset).toBe('fanout');
    expect(Object.keys(file.canvas.nodes[0])).not.toContain('ptyId');
    expect(file.panes.map((p) => p.id)).toEqual(['a', 'b']);
    expect(file.panes[0].scrollback).toHaveLength(2000);
    expect(file.panes[1].scrollback).toBeNull();
    expect(file.canvas.view).toEqual({ x: 10, y: 20, zoom: 0.8 });
  });

  it('apply v2 restores geometry, focus, view, and scrollback', () => {
    const file = buildSessionFile(two(), 'custom', new Map([['b', ['x']]]), false);
    const r = applySessionFile(file);
    expect(r.canvas.nodes.map((n) => n.id)).toEqual(['a', 'b']);
    expect(r.canvas.focusedId).toBe('b');
    expect(r.canvas.view.zoom).toBe(0.8);
    expect(r.activeLayout).toBe('custom');
    expect(r.restoredScrollbackByPaneId.get('b')).toEqual(['x']);
  });

  it('apply v1 migrates the tree to nodes (AC-S1-1)', () => {
    const a = makePane({ cwd: '/a', shell: 'zsh' });
    const b = makePane({ cwd: '/b', shell: 'zsh' });
    const c = makePane({ cwd: '/c', shell: 'zsh' });
    const root = makeSplit('H', a, makeSplit('V', b, c));
    treeIndices(root);
    const v1: SessionFileV1 = {
      version: 1,
      activePreset: 'pipeline',
      grid: { root, focusedId: c.id },
      panes: [{ id: b.id, scrollback: ['hi'] }, { id: 'gone', scrollback: ['x'] }],
      projectLessAccepted: false,
    };
    const r = applySessionFile(v1);
    expect(r.canvas.nodes.map((n) => n.id)).toEqual([a.id, b.id, c.id]);
    expect(r.canvas.focusedId).toBe(c.id);
    expect(r.activeLayout).toBe('pipeline');
    expect(r.restoredScrollbackByPaneId.get(b.id)).toEqual(['hi']);
    expect(r.restoredScrollbackByPaneId.has('gone')).toBe(false);
    const byId = Object.fromEntries(r.canvas.nodes.map((n) => [n.id, n]));
    expect(byId[b.id].x).toBeGreaterThan(byId[a.id].x);
    expect(byId[c.id].y).toBeGreaterThan(byId[b.id].y);
  });

  it('stale focus falls back to the first node', () => {
    const file = buildSessionFile(two(), 'custom', new Map(), false);
    file.canvas.focusedId = 'nope';
    expect(applySessionFile(file).canvas.focusedId).toBe('a');
  });
});

describe('layouts', () => {
  it('serialize carries nodes, view, and focus without a tree', () => {
    const file = serializeLayout(two(), 'swarm');
    expect(file.version).toBe(2);
    expect(file.activePreset).toBe('swarm');
    expect(file.nodes!.map((n) => n.id)).toEqual(['a', 'b']);
    expect(file.grid).toBeUndefined();
    expect(file.focusedId).toBe('b');
    expect(file.view!.zoom).toBe(0.8);
  });

  it('layoutToSession prefers nodes and falls back to the tree', () => {
    const withNodes = layoutToSession(serializeLayout(two(), 'custom'), true);
    expect(withNodes.version).toBe(2);
    expect(withNodes.canvas.nodes.map((n) => n.id)).toEqual(['a', 'b']);
    expect(withNodes.projectLessAccepted).toBe(true);

    const p = makePane({ cwd: '/x', shell: 'sh' });
    const legacy = layoutToSession({ version: 1, activePreset: null, grid: { root: p, focusedId: p.id } }, false);
    expect(legacy.canvas.nodes[0].id).toBe(p.id);
    expect(legacy.canvas.nodes[0].cwd).toBe('/x');
  });

  it('a v1 layout with nodes but no focusedId takes focus from its tree', () => {
    const s = two();
    const p = makePane({ cwd: '/x', shell: 'sh' });
    const r = layoutToSession({ version: 1, activePreset: null, grid: { root: p, focusedId: 'b' }, nodes: s.nodes, view: s.view }, false);
    expect(r.canvas.focusedId).toBe('b');
  });

  it('apply remaps live nodes and spawns or keeps extras without losing ids', () => {
    const saved = serializeLayout(two(), 'fanout');
    const one = createCanvasState({ cwd: '/live' });
    one.nodes[0].id = 'live1';
    one.focusedId = 'live1';
    const grown = applyLayoutToCanvas(one, saved);
    expect(grown.canvas.nodes).toHaveLength(2);
    expect(grown.canvas.nodes[0].id).toBe('live1');
    expect(grown.canvas.nodes[0].x).toBe(0);
    expect(grown.canvas.nodes[1].cwd).toBe('/b');
    expect(grown.activeLayout).toBe('fanout');

    const three = two();
    three.nodes.push({ ...makeNode({ x: 900, y: 0, w: 100, h: 100 }), id: 'c', z: 3 });
    recomputeIndices(three.nodes);
    const shrunk = applyLayoutToCanvas(three, saved);
    expect(orderedNodes(shrunk.canvas).map((n) => n.id)).toEqual(['a', 'b', 'c']);
    expect(shrunk.canvas.focusedId).toBe('b');
  });
});

describe('review follow-ups', () => {
  it('a v2 file with grid but no canvas still loads', () => {
    const p = makePane({ cwd: '/g', shell: 'sh' });
    const r = applySessionFile({ version: 2, activePreset: null, grid: { root: p, focusedId: p.id }, panes: [], projectLessAccepted: false });
    expect(r.canvas.nodes[0].id).toBe(p.id);
  });

  it('extra layout slots keep the saved node kind', () => {
    const s = two();
    s.nodes[1].kind = 'native';
    const saved = serializeLayout(s, 'custom');
    const one = createCanvasState({ cwd: '/live' });
    const r = applyLayoutToCanvas(one, saved);
    expect(r.canvas.nodes[1].kind).toBe('native');
  });
});
