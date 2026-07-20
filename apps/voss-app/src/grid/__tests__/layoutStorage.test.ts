import { describe, it, expect, vi, beforeEach } from 'vitest';

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));

import {
  EMPTY_LIST,
  INVALID_FILE,
  INVALID_NAME,
  LAYOUT_NAME_PLACEHOLDER,
  LOAD_FAILED,
  LOAD_LAYOUT_LABEL,
  LOAD_SUCCESS,
  NAME_EXISTS_CONFIRM,
  NOT_FOUND,
  SAVE_FAILED,
  SAVE_LAYOUT_LABEL,
  SAVE_SUCCESS,
  UNSUPPORTED_VERSION,
  listLayouts,
  loadDefaultLayout,
  loadLayout,
  saveLayout,
  type LayoutFile,
} from '../layoutStorage';

/**
 * A4-04 Task 1 — invoke wrappers + exact UI-SPEC copy.
 *
 * Command names and payload keys must match
 * `apps/voss-app/src-tauri/src/lib.rs` (A4-03) exactly, otherwise Tauri's
 * camelCase param mapping fails silently at runtime.
 */

function makeLayout(): LayoutFile {
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
  };
}

describe('layoutStorage — UI-SPEC copy constants', () => {
  it('matches A4-UI-SPEC Save/Load tables verbatim', () => {
    expect(SAVE_LAYOUT_LABEL).toBe('Save layout as...');
    expect(LOAD_LAYOUT_LABEL).toBe('Load layout...');
    expect(LAYOUT_NAME_PLACEHOLDER).toBe('layout name');
    expect(SAVE_SUCCESS).toBe('layout saved');
    expect(LOAD_SUCCESS).toBe('layout loaded');
    expect(EMPTY_LIST).toBe('no saved layouts');
    expect(NAME_EXISTS_CONFIRM).toBe('replace existing layout?');
    expect(NOT_FOUND).toBe('layout not found');
    expect(INVALID_FILE).toBe('layout ignored: invalid file');
    expect(UNSUPPORTED_VERSION).toBe('layout ignored: unsupported version');
    expect(SAVE_FAILED).toBe('could not save layout');
    expect(LOAD_FAILED).toBe('could not load layout');
    expect(INVALID_NAME).toBe('layout name cannot contain /, \\ or ..');
  });
});

describe('layoutStorage — Tauri invoke bridges', () => {
  beforeEach(() => h.invoke.mockReset());

  it('saveLayout → invoke("save_layout", { workspaceId, name, layout })', async () => {
    h.invoke.mockResolvedValueOnce(undefined);
    const layout = makeLayout();
    await saveLayout('ws-1', 'build-watch', layout);
    expect(h.invoke).toHaveBeenCalledTimes(1);
    expect(h.invoke).toHaveBeenCalledWith('save_layout', {
      workspaceId: 'ws-1',
      name: 'build-watch',
      layout,
    });
  });

  it('loadLayout → invoke("load_layout", { workspaceId, name }) and returns LayoutFile', async () => {
    const layout = makeLayout();
    h.invoke.mockResolvedValueOnce(layout);
    const got = await loadLayout('ws-1', 'build-watch');
    expect(h.invoke).toHaveBeenCalledWith('load_layout', {
      workspaceId: 'ws-1',
      name: 'build-watch',
    });
    expect(got).toBe(layout);
  });

  it('listLayouts → invoke("list_layouts", { workspaceId }) and returns string[]', async () => {
    h.invoke.mockResolvedValueOnce(['apple', 'zebra']);
    const names = await listLayouts('ws-1');
    expect(h.invoke).toHaveBeenCalledWith('list_layouts', {
      workspaceId: 'ws-1',
    });
    expect(names).toEqual(['apple', 'zebra']);
  });

  it('loadDefaultLayout → invoke("load_default_layout", { workspaceId }); accepts null', async () => {
    h.invoke.mockResolvedValueOnce(null);
    const missing = await loadDefaultLayout('ws-1');
    expect(h.invoke).toHaveBeenCalledWith('load_default_layout', {
      workspaceId: 'ws-1',
    });
    expect(missing).toBeNull();

    const layout = makeLayout();
    h.invoke.mockResolvedValueOnce(layout);
    const present = await loadDefaultLayout('ws-1');
    expect(present).toBe(layout);
  });
});

describe('layoutStorage — propagates Rust error strings verbatim', () => {
  beforeEach(() => h.invoke.mockReset());

  it('saveLayout surfaces Rust error string for an invalid name', async () => {
    h.invoke.mockRejectedValueOnce(INVALID_NAME);
    await expect(
      saveLayout('/ws', '../escape', makeLayout()),
    ).rejects.toBe(INVALID_NAME);
  });

  it('loadLayout surfaces "layout ignored: invalid file" for corrupt JSON', async () => {
    h.invoke.mockRejectedValueOnce(INVALID_FILE);
    await expect(loadLayout('/ws', 'bad')).rejects.toBe(INVALID_FILE);
  });

  it('loadLayout surfaces "layout not found" for missing files', async () => {
    h.invoke.mockRejectedValueOnce(NOT_FOUND);
    await expect(loadLayout('/ws', 'ghost')).rejects.toBe(NOT_FOUND);
  });
});
