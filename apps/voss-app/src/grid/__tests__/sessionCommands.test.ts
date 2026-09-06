import { describe, it, expect } from 'vitest';

import {
  collectLeaves,
  makePane,
  makeSplit,
  recomputeIndices,
  type PaneLeaf,
  type TreeNode,
} from '../tree';
import { buildSessionFile, applySessionFile } from '../sessionCommands';
import type { SessionFileV1 } from '../sessionStorage';

/**
 * A6-02 Task 2 — pure session snapshot/restore.
 *
 * Hard invariants under test:
 *  - PER-01: scrollback capped at 2,000 lines
 *  - T-A6-03: runtime-only fields cannot enter the session file
 *  - D-10: session restore preserves saved pane ids (no remap needed)
 *  - D-12: projectLessAccepted round-trips
 */

function makePanes(
  n: number,
  ctx?: { cwd?: string; shell?: string },
): PaneLeaf[] {
  return Array.from({ length: n }, () => makePane(ctx));
}

function chain(orientation: 'H' | 'V', leaves: PaneLeaf[]): TreeNode {
  if (leaves.length === 1) return leaves[0];
  return makeSplit(orientation, leaves[0], chain(orientation, leaves.slice(1)));
}

function makeSessionFile(
  root: TreeNode,
  focusedId: string,
  panes: { id: string; scrollback: string[] | null }[],
  opts?: { activePreset?: string | null; projectLessAccepted?: boolean },
): SessionFileV1 {
  return {
    version: 1,
    activePreset: (opts?.activePreset as SessionFileV1['activePreset']) ?? null,
    grid: { root, focusedId },
    panes,
    projectLessAccepted: opts?.projectLessAccepted ?? false,
  };
}

// --- buildSessionFile --------------------------------------------------------

describe('buildSessionFile — serialization rules', () => {
  it('custom active layout serializes as activePreset: null', () => {
    const leaves = makePanes(1);
    const file = buildSessionFile(
      leaves[0],
      leaves[0].id,
      'custom',
      new Map(),
      false,
    );
    expect(file.activePreset).toBeNull();
  });

  it('named preset survives as activePreset string', () => {
    const leaves = makePanes(1);
    const file = buildSessionFile(
      leaves[0],
      leaves[0].id,
      'fanout',
      new Map(),
      false,
    );
    expect(file.activePreset).toBe('fanout');
  });

  it('projectLessAccepted round-trips', () => {
    const leaves = makePanes(1);
    const file = buildSessionFile(
      leaves[0],
      leaves[0].id,
      'custom',
      new Map(),
      true,
    );
    expect(file.projectLessAccepted).toBe(true);
  });

  it('caps scrollback at 2,000 lines (keeps tail)', () => {
    const leaves = makePanes(1);
    const lines = Array.from({ length: 3000 }, (_, i) => `line-${i}`);
    const sb = new Map([[leaves[0].id, lines]]);
    const file = buildSessionFile(
      leaves[0],
      leaves[0].id,
      'custom',
      sb,
      false,
    );
    const pane = file.panes[0];
    expect(pane.scrollback).toHaveLength(2000);
    // Keeps the LAST 2000 lines (tail, not head).
    expect(pane.scrollback![0]).toBe('line-1000');
    expect(pane.scrollback![1999]).toBe('line-2999');
  });

  it('missing pane scrollback becomes null', () => {
    const leaves = makePanes(2);
    const root = chain('H', leaves);
    // Only provide scrollback for first pane.
    const sb = new Map([[leaves[0].id, ['$ ls']]]);
    const file = buildSessionFile(root, leaves[0].id, 'custom', sb, false);
    expect(file.panes[0].scrollback).toEqual(['$ ls']);
    expect(file.panes[1].scrollback).toBeNull();
  });

  it('version is always 1', () => {
    const leaves = makePanes(1);
    const file = buildSessionFile(
      leaves[0],
      leaves[0].id,
      'custom',
      new Map(),
      false,
    );
    expect(file.version).toBe(1);
  });

  it('runtime-only fields are NOT serialized (T-A6-03)', () => {
    const leaves = makePanes(1, { cwd: '/repo', shell: 'zsh' });
    type DirtyLeaf = PaneLeaf & {
      ptySessionId?: string;
      processName?: string;
      env?: Record<string, string>;
    };
    const dirty = leaves[0] as DirtyLeaf;
    dirty.ptySessionId = 'pty-123';
    dirty.processName = 'vim';
    dirty.env = { FOO: 'bar' };

    const file = buildSessionFile(dirty, dirty.id, 'custom', new Map(), false);
    const json = JSON.stringify(file);
    expect(json).not.toMatch(/ptySessionId/);
    expect(json).not.toMatch(/processName/);
    expect(json).not.toMatch(/"env"/);
    // cwd + shell ARE preserved.
    expect(json).toMatch(/"cwd":"\/repo"/);
    expect(json).toMatch(/"shell":"zsh"/);
  });

  it('one SessionPane per leaf in inorder', () => {
    const leaves = makePanes(3);
    const root = chain('H', leaves);
    recomputeIndices(root);
    const file = buildSessionFile(root, leaves[0].id, 'custom', new Map(), false);
    expect(file.panes).toHaveLength(3);
    expect(file.panes.map((p) => p.id)).toEqual(leaves.map((l) => l.id));
  });
});

// --- applySessionFile --------------------------------------------------------

describe('applySessionFile — restore', () => {
  it('preserves saved pane ids (session restore = before live panes)', () => {
    const leaves = makePanes(3, { cwd: '/repo', shell: 'zsh' });
    const root = chain('H', leaves);
    recomputeIndices(root);
    const session = makeSessionFile(
      root,
      leaves[1].id,
      leaves.map((l) => ({ id: l.id, scrollback: null })),
      { activePreset: 'pipeline' },
    );

    const result = applySessionFile(session);

    const outIds = collectLeaves(result.root).map((l) => l.id);
    expect(outIds).toEqual(leaves.map((l) => l.id));
    expect(result.focusedId).toBe(leaves[1].id);
    expect(result.activeLayout).toBe('pipeline');
  });

  it('recomputes indices on restored tree', () => {
    const leaves = makePanes(3);
    const root = chain('V', leaves);
    const session = makeSessionFile(
      root,
      leaves[0].id,
      leaves.map((l) => ({ id: l.id, scrollback: null })),
    );
    const result = applySessionFile(session);
    const indices = collectLeaves(result.root).map((l) => l.index);
    expect(indices).toEqual([1, 2, 3]);
  });

  it('null activePreset restores as custom', () => {
    const leaves = makePanes(1);
    const session = makeSessionFile(leaves[0], leaves[0].id, [
      { id: leaves[0].id, scrollback: null },
    ]);
    const result = applySessionFile(session);
    expect(result.activeLayout).toBe('custom');
  });

  it('returns scrollback map keyed by pane id', () => {
    const leaves = makePanes(2);
    const root = chain('H', leaves);
    recomputeIndices(root);
    const session = makeSessionFile(root, leaves[0].id, [
      { id: leaves[0].id, scrollback: ['$ ls', 'file.txt'] },
      { id: leaves[1].id, scrollback: null },
    ]);

    const result = applySessionFile(session);

    expect(result.restoredScrollbackByPaneId.get(leaves[0].id)).toEqual([
      '$ ls',
      'file.txt',
    ]);
    expect(result.restoredScrollbackByPaneId.has(leaves[1].id)).toBe(false);
  });

  it('extra scrollback ids not in tree are ignored', () => {
    const leaves = makePanes(1);
    const session = makeSessionFile(leaves[0], leaves[0].id, [
      { id: leaves[0].id, scrollback: ['ok'] },
      { id: 'ghost-pane', scrollback: ['should be ignored'] },
    ]);

    const result = applySessionFile(session);

    expect(result.restoredScrollbackByPaneId.size).toBe(1);
    expect(result.restoredScrollbackByPaneId.has('ghost-pane')).toBe(false);
  });

  it('focus falls back to first leaf when saved focusedId is invalid', () => {
    const leaves = makePanes(2);
    const root = chain('H', leaves);
    recomputeIndices(root);
    const session = makeSessionFile(root, 'nonexistent', [
      { id: leaves[0].id, scrollback: null },
      { id: leaves[1].id, scrollback: null },
    ]);

    const result = applySessionFile(session);
    expect(result.focusedId).toBe(leaves[0].id);
  });
});
