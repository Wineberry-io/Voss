import { describe, it, expect, vi } from 'vitest';

/**
 * A6-05 Task 2 — requirement-level acceptance for PER-01..PER-06.
 *
 * Each describe block maps to a ROADMAP requirement. Tests exercise
 * the pure session persistence logic (buildSessionFile, applySessionFile,
 * layoutToSession) to prove the end-to-end contract without a live Tauri
 * backend. Mocked: Tauri invoke (no live IPC).
 */

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));

import {
  collectLeaves,
  makePane,
  makeSplit,
  recomputeIndices,
  type PaneLeaf,
  type TreeNode,
} from '../tree';
import {
  buildSessionFile,
  applySessionFile,
  layoutToSession,
} from '../sessionCommands';
import type { SessionFileV1 } from '../sessionStorage';
import type { LayoutFile } from '../layoutStorage';
import {
  SESSION_SAVE_FAILED,
  SESSION_LOAD_FAILED,
} from '../sessionStorage';

// --- Helpers -----------------------------------------------------------------

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
  opts?: {
    activePreset?: string | null;
    projectLessAccepted?: boolean;
  },
): SessionFileV1 {
  return {
    version: 1,
    activePreset: (opts?.activePreset as SessionFileV1['activePreset']) ?? null,
    grid: { root, focusedId },
    panes,
    projectLessAccepted: opts?.projectLessAccepted ?? false,
  };
}

// ---------------------------------------------------------------------------
// PER-01 — Session restore applies saved geometry, focus, and preset
// ---------------------------------------------------------------------------

describe('PER-01 — session restore preserves geometry, focus, and preset', () => {
  it('applySessionFile returns saved pane ids, focus, and preset', () => {
    const leaves = makePanes(3, { cwd: '/repo', shell: 'zsh' });
    const root = chain('H', leaves);
    recomputeIndices(root);

    const session = makeSessionFile(
      root,
      leaves[1].id,
      leaves.map((l) => ({ id: l.id, scrollback: ['$ ls'] })),
      { activePreset: 'pipeline' },
    );

    const result = applySessionFile(session);

    expect(collectLeaves(result.root).map((l) => l.id)).toEqual(
      leaves.map((l) => l.id),
    );
    expect(result.focusedId).toBe(leaves[1].id);
    expect(result.activeLayout).toBe('pipeline');
  });

  it('buildSessionFile + applySessionFile round-trips without data loss', () => {
    const leaves = makePanes(4, { cwd: '/ws', shell: 'fish' });
    const root = chain('V', leaves);
    recomputeIndices(root);

    const scrollback = new Map([
      [leaves[0].id, ['line1', 'line2']],
      [leaves[2].id, ['$ cargo test']],
    ]);

    const file = buildSessionFile(
      root,
      leaves[2].id,
      'swarm',
      scrollback,
      true,
    );
    const result = applySessionFile(file);

    expect(collectLeaves(result.root)).toHaveLength(4);
    expect(result.focusedId).toBe(leaves[2].id);
    expect(result.activeLayout).toBe('swarm');
    expect(result.restoredScrollbackByPaneId.get(leaves[0].id)).toEqual([
      'line1',
      'line2',
    ]);
    expect(result.restoredScrollbackByPaneId.get(leaves[2].id)).toEqual([
      '$ cargo test',
    ]);
    expect(result.restoredScrollbackByPaneId.has(leaves[1].id)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// PER-02 — Scrollback capped at 2,000 lines
// ---------------------------------------------------------------------------

describe('PER-02 — scrollback capped at 2,000 lines per pane', () => {
  it('buildSessionFile caps scrollback to last 2,000 lines', () => {
    const leaves = makePanes(1);
    const lines = Array.from({ length: 5000 }, (_, i) => `line-${i}`);
    const sb = new Map([[leaves[0].id, lines]]);
    const file = buildSessionFile(leaves[0], leaves[0].id, 'custom', sb, false);
    expect(file.panes[0].scrollback).toHaveLength(2000);
    expect(file.panes[0].scrollback![0]).toBe('line-3000');
  });
});

// ---------------------------------------------------------------------------
// PER-03 — Project-less global session with projectLessAccepted bypasses setup
// ---------------------------------------------------------------------------

describe('PER-03 — project-less global session bypasses setup', () => {
  it('global session with projectLessAccepted=true round-trips correctly', () => {
    const leaves = makePanes(2);
    const root = chain('H', leaves);
    recomputeIndices(root);
    const file = buildSessionFile(
      root,
      leaves[0].id,
      'custom',
      new Map(),
      true,
    );
    expect(file.projectLessAccepted).toBe(true);

    const result = applySessionFile(file);
    expect(collectLeaves(result.root)).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// PER-04 — Corrupt/unsupported session falls through
// ---------------------------------------------------------------------------

describe('PER-04 — corrupt session fallback via layoutToSession', () => {
  it('layoutToSession converts a default LayoutFile to a SessionFileV1 for fallback', () => {
    const leaves = makePanes(2, { cwd: '/repo', shell: 'zsh' });
    const layout: LayoutFile = {
      version: 1,
      activePreset: 'fanout',
      grid: { root: chain('H', leaves), focusedId: leaves[0].id },
    };
    const session = layoutToSession(layout, false);
    expect(session.version).toBe(1);
    expect(session.activePreset).toBe('fanout');
    expect(session.panes).toHaveLength(2);
    expect(session.panes[0].scrollback).toBeNull();
    expect(session.projectLessAccepted).toBe(false);

    // Confirm it applies cleanly
    const result = applySessionFile(session);
    expect(collectLeaves(result.root)).toHaveLength(2);
    expect(result.activeLayout).toBe('fanout');
  });
});

// ---------------------------------------------------------------------------
// PER-05 — Tree-only autosave writes null scrollback
// ---------------------------------------------------------------------------

describe('PER-05 — tree-only autosave carries null scrollback', () => {
  it('buildSessionFile with empty Map produces null scrollback per pane', () => {
    const leaves = makePanes(3);
    const root = chain('H', leaves);
    recomputeIndices(root);
    const file = buildSessionFile(
      root,
      leaves[0].id,
      'custom',
      new Map(),
      false,
    );
    for (const pane of file.panes) {
      expect(pane.scrollback).toBeNull();
    }
  });
});

// ---------------------------------------------------------------------------
// PER-06 — No PTY/process metadata in serialized session
// ---------------------------------------------------------------------------

describe('PER-06 — no process relaunch metadata in session file', () => {
  it('serialized session JSON has no PTY, process, or env fields', () => {
    const leaves = makePanes(2, { cwd: '/repo', shell: 'zsh' });
    type DirtyLeaf = PaneLeaf & {
      ptySessionId?: string;
      processName?: string;
      env?: Record<string, string>;
    };
    (leaves[0] as DirtyLeaf).ptySessionId = 'pty-abc';
    (leaves[0] as DirtyLeaf).processName = 'vim';
    (leaves[0] as DirtyLeaf).env = { TERM: 'xterm-256color' };

    const root = chain('H', leaves);
    const file = buildSessionFile(
      root,
      leaves[0].id,
      'custom',
      new Map(),
      false,
    );
    const json = JSON.stringify(file);
    expect(json).not.toMatch(/ptySessionId/);
    expect(json).not.toMatch(/processName/);
    expect(json).not.toMatch(/"env"/);
    // cwd and shell ARE preserved
    expect(json).toMatch(/"cwd":"\/repo"/);
    expect(json).toMatch(/"shell":"zsh"/);
  });

  it('error copy constants match Rust SessionError::Display', () => {
    expect(SESSION_SAVE_FAILED).toBe('could not save session');
    expect(SESSION_LOAD_FAILED).toBe('could not load session');
  });
});
