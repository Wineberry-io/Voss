import { createMemo, createSignal } from 'solid-js';
import { serializeLayout } from '../canvas/session';
import { normalizeChord, normalizePrefixKey } from '../command-palette/chords';
import {
  loadKeymapProfile,
  saveKeymapProfile,
  watchWorkspaceKeymap,
  type KeymapProfile,
  type KeymapUpdatePayload,
} from '../command-palette/keymapStorage';
import { setAsAppMenu } from '../command-palette/nativeMenu';
import { moveModeDirection } from '../command-palette/moveMode';
import { createPrefixMode } from '../command-palette/prefixMode';
import { buildQuickOpenItems } from '../command-palette/quickOpen';
import {
  appearanceCommands,
  createCommandRegistry,
  v0Commands,
  workspaceCommands,
  type AppContext,
  type KeyBindingOverrides,
} from '../command-palette/registry';
import { showToast } from '../command-palette/toast';
import { listLayouts, loadLayout, saveLayout } from '../grid/layoutStorage';
import { PORTAL_ITEMS } from '../portal/portalTypes';
import { parseWorkspaceShortcut } from '../workspaces/workspaceShortcuts';
import type { ViewRouter } from './viewRouter';
import type { WorkspaceHost } from './workspaceHost';

export function createKeymapHost(ws: WorkspaceHost, view: ViewRouter) {
  const [paletteMode, setPaletteMode] = createSignal<'quick' | 'full' | null>(null);
  const [layoutNames, setLayoutNames] = createSignal<string[]>([]);
  const [keymapProfile, setKeymapProfile] = createSignal<KeymapProfile>('vscode');
  const [keymapOverrides, setKeymapOverrides] = createSignal<KeyBindingOverrides>({});
  const [prefixActive, setPrefixActive] = createSignal(false);
  const [moveMode, setMoveMode] = createSignal(false);
  const [recentCommandIds] = createSignal<Set<string>>(new Set());
  let keymapUnlisten: (() => void) | undefined;

  const baseCommands = [...v0Commands(), ...workspaceCommands(), ...appearanceCommands()];
  const registry = createMemo(() => createCommandRegistry(baseCommands, keymapOverrides()));
  const knownCommandIds = () => baseCommands.map((cmd) => cmd.id);
  const knownChords = () =>
    baseCommands.flatMap((cmd) => [...(cmd.keybinding ? [cmd.keybinding] : []), ...(cmd.aliases ?? [])]);

  const openPalette = (mode: 'quick' | 'full') => {
    setPaletteMode(mode);
    const id = ws.activeId();
    if (mode === 'quick' && id && ws.activeMounted()?.project()) {
      void listLayouts(id)
        .then(setLayoutNames)
        .catch(() => setLayoutNames([]));
    }
  };
  const dismissPalette = () => setPaletteMode(null);
  const quickItems = () => buildQuickOpenItems(layoutNames(), ws.recents());

  const saveCurrentLayout = async (workspaceId: string, name: string): Promise<void> => {
    const ctrl = ws.gridController();
    const mounted = ws.activeMounted();
    if (!ctrl || !mounted) return;
    await saveLayout(workspaceId, name, serializeLayout(ctrl.snapshot(), mounted.activeLayout()));
  };
  const loadLayoutByName = async (workspaceId: string, name: string): Promise<void> => {
    const ctrl = ws.gridController();
    if (!ctrl) return;
    ctrl.applyLoadedLayout(await loadLayout(workspaceId, name));
  };

  const handlePaletteExecute = (id: string) => {
    if (id.startsWith('layout:')) {
      const workspaceId = ws.activeId();
      if (workspaceId && ws.gridController()) void loadLayoutByName(workspaceId, id.slice('layout:'.length));
    } else if (id.startsWith('recent:')) {
      void ws.openSelectedProject(id.slice('recent:'.length), 'palette open_recent failed:');
    } else {
      dispatchCommandId(id);
    }
  };

  const applyKeymapUpdate = (payload: KeymapUpdatePayload) => {
    setKeymapOverrides(payload.valid);
    for (const issue of payload.issues) showToast('warning', `${issue.commandId}: ${issue.reason}`);
  };

  const installWorkspaceKeymap = async (path: string) => {
    keymapUnlisten?.();
    keymapUnlisten = undefined;
    try {
      keymapUnlisten = await watchWorkspaceKeymap(path, knownCommandIds(), knownChords(), applyKeymapUpdate);
    } catch (e) {
      console.error('watch_keymap_overrides failed:', e);
      setKeymapOverrides({});
      showToast('error', 'could not load keymap settings');
    }
  };

  const ctrl = () => ws.gridController();
  const appCtx: AppContext = {
    splitFocused: (orientation) => ctrl()?.splitFocused(orientation),
    closeFocused: () => ctrl()?.closeFocused(),
    equalizePanes: () => ctrl()?.equalizePanes(),
    cycleLayout: () => ctrl()?.cycleLayout(),
    focusNext: () => ctrl()?.focusNext(),
    focusPrev: () => ctrl()?.focusPrev(),
    focusIndex: (n) => ctrl()?.focusIndex(n),
    focusDirection: (dir) => ctrl()?.focusDirection(dir),
    resizeDirection: (dir) => ctrl()?.resizeDirection(dir),
    zoomReset: () => ctrl()?.zoomReset(),
    zoomFit: () => ctrl()?.zoomFit(),
    zoomToFocused: () => ctrl()?.zoomToFocused(),
    moveMode: () => setMoveMode(true),
    newTerminalNode: () => ctrl()?.placeNode('terminal'),
    openQuickPalette: () => openPalette('quick'),
    openFullPalette: () => openPalette('full'),
    openProject: () => void ws.handleOpenFolder(),
    saveLayout: () => {
      const id = ws.activeId();
      if (!id || !ws.activeMounted()?.project()) return;
      const name = window.prompt('Save layout as');
      const trimmed = name?.trim();
      if (!trimmed) return;
      void saveCurrentLayout(id, trimmed)
        .then(() => listLayouts(id))
        .then(setLayoutNames)
        .catch((e) => console.error('save_layout failed:', e));
    },
    loadLayout: () => openPalette('quick'),
    switchProfile: () => {
      const next: KeymapProfile = keymapProfile() === 'tmux' ? 'vscode' : 'tmux';
      void saveKeymapProfile(next)
        .then(() => {
          setKeymapProfile(next);
          showToast('info', `Keymap profile: ${next}`);
        })
        .catch((e) => {
          console.error('save_keymap_profile failed:', e);
          showToast('error', 'could not save keymap settings');
        });
    },
    showKeybindings: () => openPalette('full'),
    newWorkspace: () => ws.handleNewWorkspace(),
    closeWorkspace: () => ws.handleCloseActiveWorkspace(),
    nextWorkspace: () => ws.handleNextWorkspace(),
    prevWorkspace: () => ws.handlePrevWorkspace(),
    focusWorkspace: (index) => ws.handleFocusWorkspaceByIndex(index),
    renameWorkspace: () => ws.handleRenameActiveWorkspace(),
    colorWorkspace: () => ws.handleColorActiveWorkspace(),
    switchTheme: () => openPalette('full'),
    switchFont: () => openPalette('full'),
    toggleHighContrast: () => openPalette('full'),
    setBellBehavior: () => openPalette('full'),
    toggleSidebar: view.toggleSidebar,
  };

  const dispatchCommandId = (id: string): boolean => {
    const cmd = registry().commands.get(id);
    if (!cmd) return false;
    cmd.handler(appCtx);
    return true;
  };

  const prefixMode = createPrefixMode({
    onActivate: () => setPrefixActive(true),
    onDeactivate: () => setPrefixActive(false),
    dispatch: (commandId) => void dispatchCommandId(commandId),
    setTimeout: (fn, ms) => window.setTimeout(fn, ms),
    clearTimeout: (id) => window.clearTimeout(id),
  });

  const consume = (e: KeyboardEvent) => {
    e.preventDefault();
    e.stopImmediatePropagation();
  };

  const onAppKey = (e: KeyboardEvent) => {
    if (ws.newWorkspacePickerOpen()) {
      if (e.key === 'Escape') return;
      consume(e);
      return;
    }
    if (paletteMode() !== null) {
      if (e.metaKey) consume(e);
      return;
    }
    if (moveMode()) {
      if (e.metaKey || e.ctrlKey || e.altKey) {
        setMoveMode(false);
      } else {
        const dir = moveModeDirection(e.key);
        if (dir) ctrl()?.focusDirection(dir);
        else setMoveMode(false);
        consume(e);
        return;
      }
    }
    const workspaceAction = parseWorkspaceShortcut(e);
    if (workspaceAction) {
      ws.handleWorkspaceShortcut(workspaceAction);
      consume(e);
      return;
    }
    const chord = normalizeChord(e);
    if (prefixMode.isActive()) {
      const prefixKey = normalizePrefixKey(e);
      if (prefixKey) {
        if (prefixMode.handleKey(prefixKey).action !== 'passthrough') consume(e);
        return;
      }
      if (chord === 'Cmd+B') {
        consume(e);
        prefixMode.tryEnter(keymapProfile());
        return;
      }
    }
    if (chord === 'Cmd+B' && prefixMode.tryEnter(keymapProfile())) {
      consume(e);
      return;
    }
    if (e.metaKey && e.shiftKey && (e.key === 'b' || e.key === 'B')) {
      view.toggleSidebar();
      consume(e);
      return;
    }
    if (e.metaKey && e.shiftKey && (e.key === 'o' || e.key === 'O')) {
      void view.openConsole('review');
      consume(e);
      return;
    }
    if (e.metaKey && !e.shiftKey && !e.altKey && (e.key === 'k' || e.key === 'K')) {
      void view.openConsole('review');
      consume(e);
      return;
    }
    if (e.metaKey && e.altKey && !e.shiftKey && e.key >= '1' && e.key <= '8') {
      const item = PORTAL_ITEMS[Number(e.key) - 1];
      if (item) {
        view.navigatePortal(item.id);
        consume(e);
        return;
      }
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
      view.toggleContextPanel();
      consume(e);
      return;
    }
    if (chord && registry().dispatch(chord, appCtx)) consume(e);
  };

  const install = () => {
    window.addEventListener('keydown', onAppKey, true);
    void setAsAppMenu(registry(), (id) => void dispatchCommandId(id));
    void loadKeymapProfile()
      .then(setKeymapProfile)
      .catch(() => setKeymapProfile('vscode'));
  };
  const dispose = () => {
    window.removeEventListener('keydown', onAppKey, true);
    keymapUnlisten?.();
    prefixMode.cancel();
    setMoveMode(false);
  };

  return {
    paletteMode,
    setPaletteMode,
    keymapProfile,
    prefixActive,
    moveMode,
    recentCommandIds,
    registry,
    openPalette,
    dismissPalette,
    quickItems,
    handlePaletteExecute,
    installWorkspaceKeymap,
    dispatchCommandId,
    install,
    dispose,
  };
}

export type KeymapHost = ReturnType<typeof createKeymapHost>;
