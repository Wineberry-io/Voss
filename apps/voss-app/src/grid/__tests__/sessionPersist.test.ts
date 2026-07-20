import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * A6-04 Task 1 — structural session autosave tests.
 *
 * Verifies:
 * - Multiple structural changes collapse into one debounced save
 * - Autosave does NOT read xterm scrollback (empty map)
 * - Global session path used when projectPath is null
 * - Cleanup clears timer and unsubscribes
 */

// --- Mocks -------------------------------------------------------------------

const h = vi.hoisted(() => {
  const listeners: (() => void)[] = [];
  return {
    saveSession: vi.fn(() => Promise.resolve()),
    saveGlobalSession: vi.fn(() => Promise.resolve()),
    listeners,
    subscribeStructuralChange: vi.fn((fn: () => void) => {
      listeners.push(fn);
      return () => {
        const idx = listeners.indexOf(fn);
        if (idx >= 0) listeners.splice(idx, 1);
      };
    }),
  };
});

vi.mock('../sync', () => ({
  subscribeStructuralChange: h.subscribeStructuralChange,
}));
vi.mock('../sessionStorage', () => ({
  saveSession: h.saveSession,
  saveGlobalSession: h.saveGlobalSession,
}));
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    onCloseRequested: vi.fn(() => Promise.resolve(() => {})),
    close: vi.fn(() => Promise.resolve()),
  }),
}));

import {
  installStructuralSessionAutosave,
  type SessionContext,
} from '../sessionPersist';

// --- Helpers -----------------------------------------------------------------

function makeCtx(projectPath: string | null = '/ws'): SessionContext {
  return {
    workspaceId: 'ws-1',
    getRoot: () => ({
      kind: 'pane',
      id: 'a',
      cwd: '/repo',
      shell: 'zsh',
      index: 1,
    }),
    getFocusedId: () => 'a',
    getActiveLayout: () => 'custom',
    getProjectLessAccepted: () => false,
    projectPath,
  };
}

function fireStructuralChange() {
  for (const fn of h.listeners) fn();
}

// --- Tests -------------------------------------------------------------------

describe('installStructuralSessionAutosave', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    h.saveSession.mockClear();
    h.saveGlobalSession.mockClear();
    h.listeners.length = 0;
  });
  afterEach(() => vi.useRealTimers());

  it('debounces multiple structural changes into one save', () => {
    const cleanup = installStructuralSessionAutosave(makeCtx());

    fireStructuralChange();
    fireStructuralChange();
    fireStructuralChange();

    expect(h.saveSession).not.toHaveBeenCalled();

    vi.advanceTimersByTime(2000);

    expect(h.saveSession).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it('autosave builds session with null scrollback per pane (no xterm read)', () => {
    installStructuralSessionAutosave(makeCtx());
    fireStructuralChange();
    vi.advanceTimersByTime(2000);

    const args = h.saveSession.mock.calls[0] as unknown[];
    const session = args[1] as { panes: { scrollback: unknown }[] };
    expect(session.panes).toHaveLength(1);
    expect(session.panes[0].scrollback).toBeNull();
  });

  it('uses saveGlobalSession when projectPath is null', () => {
    installStructuralSessionAutosave(makeCtx(null));
    fireStructuralChange();
    vi.advanceTimersByTime(2000);

    expect(h.saveGlobalSession).toHaveBeenCalledTimes(1);
    expect(h.saveSession).not.toHaveBeenCalled();
  });

  it('uses saveSession with project path', () => {
    installStructuralSessionAutosave(makeCtx('/my/project'));
    fireStructuralChange();
    vi.advanceTimersByTime(2000);

    expect(h.saveSession).toHaveBeenCalledWith('/my/project', expect.anything());
  });

  it('cleanup clears pending timer and unsubscribes', () => {
    const cleanup = installStructuralSessionAutosave(makeCtx());
    fireStructuralChange();
    cleanup();

    vi.advanceTimersByTime(5000);

    expect(h.saveSession).not.toHaveBeenCalled();
    expect(h.listeners).toHaveLength(0);
  });

  it('second save after cleanup does not fire', () => {
    const cleanup = installStructuralSessionAutosave(makeCtx());
    fireStructuralChange();
    vi.advanceTimersByTime(2000);
    expect(h.saveSession).toHaveBeenCalledTimes(1);

    cleanup();
    h.saveSession.mockClear();

    // Listeners have been removed, so no new fires possible
    expect(h.listeners).toHaveLength(0);
  });
});
