import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createRoot } from 'solid-js';

const h = vi.hoisted(() => ({
  invoke: vi.fn(),
  listLayouts: vi.fn(),
  loadLayout: vi.fn(),
  saveLayout: vi.fn(),
  loadKeymapProfile: vi.fn(),
  saveKeymapProfile: vi.fn(),
  watchWorkspaceKeymap: vi.fn(),
  setAsAppMenu: vi.fn(),
  showToast: vi.fn(),
}));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));
vi.mock('../../grid/layoutStorage', () => ({ listLayouts: h.listLayouts, loadLayout: h.loadLayout, saveLayout: h.saveLayout }));
vi.mock('../../command-palette/keymapStorage', () => ({
  loadKeymapProfile: h.loadKeymapProfile,
  saveKeymapProfile: h.saveKeymapProfile,
  watchWorkspaceKeymap: h.watchWorkspaceKeymap,
}));
vi.mock('../../command-palette/nativeMenu', () => ({ setAsAppMenu: h.setAsAppMenu }));
vi.mock('../../command-palette/toast', () => ({ showToast: h.showToast, default: () => null }));

import { createKeymapHost } from '../keymapHost';
import type { WorkspaceHost } from '../workspaceHost';
import type { ViewRouter } from '../viewRouter';

function controller() {
  return {
    splitFocused: vi.fn(),
    closeFocused: vi.fn(),
    equalizePanes: vi.fn(),
    cycleLayout: vi.fn(),
    focusNext: vi.fn(),
    focusPrev: vi.fn(),
    focusIndex: vi.fn(),
    focusDirection: vi.fn(),
    resizeDirection: vi.fn(),
    zoomReset: vi.fn(),
    zoomFit: vi.fn(),
    zoomToFocused: vi.fn(),
    placeNode: vi.fn(),
    openFile: vi.fn(),
    applyLoadedLayout: vi.fn(),
    snapshot: vi.fn(() => ({ nodes: [], view: { x: 0, y: 0, zoom: 1 }, focusedId: '' })),
  };
}

function fakes(opts: { project?: boolean; pickerOpen?: boolean } = {}) {
  const ctrl = controller();
  const ws = {
    activeId: () => 'w1',
    activeMounted: () => ({ project: () => (opts.project === false ? null : { path: '/proj', name: 'proj', gitBranch: null }), activeLayout: () => 'custom' }),
    gridController: () => ctrl,
    recents: () => ['/tmp/old'],
    newWorkspacePickerOpen: () => !!opts.pickerOpen,
    openSelectedProject: vi.fn(() => Promise.resolve()),
    handleOpenFolder: vi.fn(() => Promise.resolve()),
    handleNewWorkspace: vi.fn(),
    handleCloseActiveWorkspace: vi.fn(),
    handleNextWorkspace: vi.fn(),
    handlePrevWorkspace: vi.fn(),
    handleFocusWorkspaceByIndex: vi.fn(),
    handleRenameActiveWorkspace: vi.fn(),
    handleColorActiveWorkspace: vi.fn(),
    handleWorkspaceShortcut: vi.fn(),
  } as unknown as WorkspaceHost;
  const view = {
    toggleSidebar: vi.fn(),
    openConsole: vi.fn(() => Promise.resolve()),
    navigatePortal: vi.fn(),
    toggleContextPanel: vi.fn(),
  } as unknown as ViewRouter;
  return { ctrl, ws, view };
}

const key = (init: KeyboardEventInit) => {
  const e = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init });
  window.dispatchEvent(e);
  return e;
};

let disposeRoot: (() => void) | undefined;
function host(opts: Parameters<typeof fakes>[0] = {}) {
  const f = fakes(opts);
  let keys!: ReturnType<typeof createKeymapHost>;
  disposeRoot = createRoot((dispose) => {
    keys = createKeymapHost(f.ws, f.view);
    return dispose;
  });
  keys.install();
  return { ...f, keys };
}

beforeEach(() => {
  h.invoke.mockReset().mockResolvedValue([]);
  h.listLayouts.mockReset().mockResolvedValue(['default']);
  h.loadLayout.mockReset().mockResolvedValue({ version: 2, activePreset: null, nodes: [] });
  h.saveLayout.mockReset().mockResolvedValue(undefined);
  h.loadKeymapProfile.mockReset().mockResolvedValue('vscode');
  h.saveKeymapProfile.mockReset().mockResolvedValue(undefined);
  h.watchWorkspaceKeymap.mockReset().mockResolvedValue(() => {});
  h.setAsAppMenu.mockReset().mockResolvedValue(undefined);
  h.showToast.mockReset();
});
afterEach(() => {
  disposeRoot?.();
  disposeRoot = undefined;
});

describe('keymapHost', () => {
  it('quick open lists layouts, recents, and workspace files; execute routes each kind', async () => {
    h.invoke.mockResolvedValue([{ name: 'src', is_dir: true, children: [{ name: 'a.ts', is_dir: false }] }]);
    const { keys, ctrl, ws } = host();
    keys.openPalette('quick');
    await vi.waitFor(() => expect(keys.quickItems().map((i) => i.id)).toEqual(['layout:default', 'recent:/tmp/old', 'file:src/a.ts']));
    expect(h.invoke).toHaveBeenCalledWith('list_dir', { path: '/proj' });
    keys.handlePaletteExecute('file:src/a.ts');
    expect(ctrl.openFile).toHaveBeenCalledWith('src/a.ts');
    keys.handlePaletteExecute('recent:/tmp/old');
    expect(ws.openSelectedProject).toHaveBeenCalledWith('/tmp/old', 'palette open_recent failed:');
    keys.handlePaletteExecute('layout:default');
    await vi.waitFor(() => expect(ctrl.applyLoadedLayout).toHaveBeenCalledTimes(1));
    expect(h.loadLayout).toHaveBeenCalledWith('w1', 'default');
    expect(keys.handlePaletteExecute('canvas.zoomFit')).toBeUndefined();
    expect(ctrl.zoomFit).toHaveBeenCalledTimes(1);
    keys.dismissPalette();
    expect(keys.paletteMode()).toBeNull();
    keys.dispose();
  });

  it('without a project the quick palette skips layouts and files', () => {
    const { keys } = host({ project: false });
    keys.openPalette('quick');
    expect(h.listLayouts).not.toHaveBeenCalled();
    expect(h.invoke).not.toHaveBeenCalledWith('list_dir', expect.anything());
    expect(keys.quickItems().map((i) => i.id)).toEqual(['recent:/tmp/old']);
    keys.dispose();
  });

  it('canvas commands reach the controller: zoom, placement, note, and move mode', () => {
    const { keys, ctrl } = host();
    keys.dispatchCommandId('canvas.zoomReset');
    keys.dispatchCommandId('canvas.zoomToFocused');
    keys.dispatchCommandId('canvas.newTerminal');
    keys.dispatchCommandId('canvas.newNote');
    expect(ctrl.zoomReset).toHaveBeenCalledTimes(1);
    expect(ctrl.zoomToFocused).toHaveBeenCalledTimes(1);
    expect(ctrl.placeNode).toHaveBeenNthCalledWith(1, 'terminal');
    expect(ctrl.placeNode).toHaveBeenNthCalledWith(2, 'note');
    expect(keys.dispatchCommandId('nope.missing')).toBe(false);

    keys.dispatchCommandId('canvas.moveMode');
    expect(keys.moveMode()).toBe(true);
    expect(key({ key: 'l' }).defaultPrevented).toBe(true);
    expect(ctrl.focusDirection).toHaveBeenCalledWith('right');
    key({ key: 'w' });
    expect(ctrl.focusDirection).toHaveBeenCalledWith('up');
    expect(keys.moveMode()).toBe(true);
    key({ key: 'Escape' });
    expect(keys.moveMode()).toBe(false);
    keys.dispatchCommandId('canvas.moveMode');
    key({ key: 'k', code: 'KeyK', metaKey: true });
    expect(keys.moveMode()).toBe(false);
    keys.dispose();
  });

  it('app chords: sidebar, console, portal, context panel, and workspace shortcuts', () => {
    const { keys, view, ws } = host();
    expect(key({ key: 'b', metaKey: true, shiftKey: true }).defaultPrevented).toBe(true);
    expect(view.toggleSidebar).toHaveBeenCalledTimes(1);
    key({ key: 'k', metaKey: true });
    key({ key: 'o', metaKey: true, shiftKey: true });
    expect(view.openConsole).toHaveBeenCalledTimes(2);
    key({ key: '2', metaKey: true, altKey: true });
    expect(view.navigatePortal).toHaveBeenCalledWith('overview');
    key({ key: 'i', metaKey: true });
    expect(view.toggleContextPanel).toHaveBeenCalledTimes(1);
    key({ key: 'Tab', ctrlKey: true });
    expect(ws.handleWorkspaceShortcut).toHaveBeenCalledWith('next');
    keys.dispose();
  });

  it('registry chords dispatch through the same listener and the picker swallows keys', () => {
    const { keys, ctrl } = host();
    expect(key({ key: 'd', code: 'KeyD', metaKey: true }).defaultPrevented).toBe(true);
    expect(ctrl.splitFocused).toHaveBeenCalledWith('H');
    keys.setPaletteMode('full');
    expect(key({ key: 'd', code: 'KeyD', metaKey: true }).defaultPrevented).toBe(true);
    expect(ctrl.splitFocused).toHaveBeenCalledTimes(1);
    keys.dispose();

    const other = host({ pickerOpen: true });
    expect(key({ key: 'd', code: 'KeyD', metaKey: true }).defaultPrevented).toBe(true);
    expect(key({ key: 'Escape' }).defaultPrevented).toBe(false);
    expect(other.ctrl.splitFocused).not.toHaveBeenCalled();
    other.keys.dispose();
  });

  it('tmux profile: ⌘B then z fits, ⌘B twice cancels, prefix state is exposed', async () => {
    h.loadKeymapProfile.mockResolvedValue('tmux');
    const { keys, ctrl } = host();
    await vi.waitFor(() => expect(keys.keymapProfile()).toBe('tmux'));
    expect(key({ key: 'b', code: 'KeyB', metaKey: true }).defaultPrevented).toBe(true);
    expect(keys.prefixActive()).toBe(true);
    expect(key({ key: 'z' }).defaultPrevented).toBe(true);
    expect(ctrl.zoomFit).toHaveBeenCalledTimes(1);
    expect(keys.prefixActive()).toBe(false);
    key({ key: 'b', code: 'KeyB', metaKey: true });
    key({ key: 'b', code: 'KeyB', metaKey: true });
    expect(keys.prefixActive()).toBe(false);
    keys.dispose();
  });

  it('save layout prompts for a name, writes the snapshot, and refreshes the list; switchProfile toggles', async () => {
    const { keys, ctrl } = host();
    vi.spyOn(window, 'prompt').mockReturnValueOnce('  ').mockReturnValueOnce('mine');
    keys.dispatchCommandId('layout.save');
    expect(h.saveLayout).not.toHaveBeenCalled();
    keys.dispatchCommandId('layout.save');
    await vi.waitFor(() => expect(h.saveLayout).toHaveBeenCalledWith('w1', 'mine', expect.objectContaining({ version: 2 })));
    expect(ctrl.snapshot).toHaveBeenCalled();
    await vi.waitFor(() => expect(h.listLayouts).toHaveBeenCalled());

    keys.dispatchCommandId('settings.switchProfile');
    await vi.waitFor(() => expect(keys.keymapProfile()).toBe('tmux'));
    expect(h.saveKeymapProfile).toHaveBeenCalledWith('tmux');
    expect(h.showToast).toHaveBeenCalledWith('info', 'Keymap profile: tmux');
    keys.dispose();
  });

  it('workspace keymap watch applies valid overrides and toasts issues; failures reset', async () => {
    let cb: ((p: { valid: Record<string, { key: string } | null>; issues: { commandId: string; reason: string }[] }) => void) | undefined;
    h.watchWorkspaceKeymap.mockImplementation(async (_p: string, _ids: string[], _chords: string[], apply: typeof cb) => {
      cb = apply;
      return () => {};
    });
    const { keys } = host();
    await keys.installWorkspaceKeymap('/proj');
    cb!({ valid: { 'pane.close': { key: 'Cmd+Shift+W' } }, issues: [{ commandId: 'pane.x', reason: 'unknown command' }] });
    expect(h.showToast).toHaveBeenCalledWith('warning', 'pane.x: unknown command');
    expect(keys.registry().commands.get('pane.close')?.keybinding).toBe('Cmd+Shift+W');

    h.watchWorkspaceKeymap.mockRejectedValueOnce(new Error('boom'));
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    await keys.installWorkspaceKeymap('/proj');
    expect(h.showToast).toHaveBeenCalledWith('error', 'could not load keymap settings');
    err.mockRestore();
    keys.dispose();
  });
});
