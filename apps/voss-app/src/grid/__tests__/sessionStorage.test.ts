import { describe, it, expect, vi, beforeEach } from 'vitest';

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));

import {
  SESSION_SAVE_FAILED,
  SESSION_LOAD_FAILED,
  saveSession,
  loadSession,
  saveGlobalSession,
  loadGlobalSession,
  type SessionFileV1,
} from '../sessionStorage';

/**
 * A6-02 Task 1 — session invoke wrappers + error copy.
 *
 * Command names and payload keys must match
 * `apps/voss-app/src-tauri/src/lib.rs` (A6-01) exactly.
 */

function makeSession(): SessionFileV1 {
  return {
    version: 1,
    activePreset: 'fanout',
    grid: {
      root: {
        kind: 'pane',
        id: 'a',
        cwd: '/repo',
        shell: 'zsh',
        index: 1,
      },
      focusedId: 'a',
    },
    panes: [{ id: 'a', scrollback: ['$ ls', 'file.txt'] }],
    projectLessAccepted: false,
  };
}

describe('sessionStorage — error copy constants', () => {
  it('matches Rust SessionError::Display strings', () => {
    expect(SESSION_SAVE_FAILED).toBe('could not save session');
    expect(SESSION_LOAD_FAILED).toBe('could not load session');
  });
});

describe('sessionStorage — project session commands', () => {
  beforeEach(() => h.invoke.mockReset());

  it('saveSession → invoke("save_session", { workspaceId, session })', async () => {
    h.invoke.mockResolvedValueOnce(undefined);
    const session = makeSession();
    await saveSession('ws-1', session);
    expect(h.invoke).toHaveBeenCalledTimes(1);
    expect(h.invoke).toHaveBeenCalledWith('save_session', {
      workspaceId: 'ws-1',
      session,
    });
  });

  it('loadSession → invoke("load_session", { workspaceId }) returns SessionFileV1', async () => {
    const session = makeSession();
    h.invoke.mockResolvedValueOnce(session);
    const got = await loadSession('ws-1');
    expect(h.invoke).toHaveBeenCalledWith('load_session', {
      workspaceId: 'ws-1',
    });
    expect(got).toBe(session);
  });

  it('loadSession returns null for missing session', async () => {
    h.invoke.mockResolvedValueOnce(null);
    const got = await loadSession('ws-1');
    expect(got).toBeNull();
  });
});

describe('sessionStorage — global session commands', () => {
  beforeEach(() => h.invoke.mockReset());

  it('saveGlobalSession → invoke("save_global_session", { session })', async () => {
    h.invoke.mockResolvedValueOnce(undefined);
    const session = makeSession();
    await saveGlobalSession(session);
    expect(h.invoke).toHaveBeenCalledTimes(1);
    expect(h.invoke).toHaveBeenCalledWith('save_global_session', {
      session,
    });
  });

  it('loadGlobalSession → invoke("load_global_session") returns SessionFileV1 | null', async () => {
    h.invoke.mockResolvedValueOnce(null);
    const missing = await loadGlobalSession();
    expect(h.invoke).toHaveBeenCalledWith('load_global_session');
    expect(missing).toBeNull();

    const session = makeSession();
    h.invoke.mockResolvedValueOnce(session);
    const present = await loadGlobalSession();
    expect(present).toBe(session);
  });
});

describe('sessionStorage — propagates Rust error strings', () => {
  beforeEach(() => h.invoke.mockReset());

  it('saveSession surfaces save failure', async () => {
    h.invoke.mockRejectedValueOnce(SESSION_SAVE_FAILED);
    await expect(saveSession('ws-1', makeSession())).rejects.toBe(
      SESSION_SAVE_FAILED,
    );
  });

  it('loadSession surfaces load failure', async () => {
    h.invoke.mockRejectedValueOnce(SESSION_LOAD_FAILED);
    await expect(loadSession('ws-1')).rejects.toBe(SESSION_LOAD_FAILED);
  });
});
