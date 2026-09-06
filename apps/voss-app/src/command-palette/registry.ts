/**
 * A7-01 Task 2 — typed command registry and v0 command catalog.
 *
 * Single source of truth for keyboard dispatch, palette search, and
 * native OS menus (D-01). Replaces the A3 switch-based keymap.ts as
 * the canonical command surface (D-02). Handlers receive an AppContext
 * object built once at App.tsx mount (D-03).
 */

// --- Types -------------------------------------------------------------------

export type CommandCategory =
  | 'Window'
  | 'Workspace'
  | 'Pane'
  | 'Layout'
  | 'Project'
  | 'Settings'
  | 'Help';

export interface CommandDefinition {
  id: string;
  label: string;
  category: CommandCategory;
  /** Primary keybinding (shown in palette chord hint). */
  keybinding?: string;
  /** Additional chord bindings not shown in palette. */
  aliases?: string[];
  handler: (ctx: AppContext) => void;
}

export type Command = Readonly<CommandDefinition>;

export type KeyBindingOverrides = Readonly<
  Record<string, { key: string } | null>
>;

/**
 * Cross-module action callbacks (D-03). Built once at App.tsx mount.
 * Handlers destructure what they need — no Solid imports leak in.
 */
export interface AppContext {
  splitFocused: (orientation: 'H' | 'V') => void;
  closeFocused: () => void;
  equalizePanes: () => void;
  cycleLayout: () => void;
  focusNext: () => void;
  focusPrev: () => void;
  focusIndex: (n: number) => void;
  focusDirection: (dir: 'left' | 'right' | 'up' | 'down') => void;
  resizeDirection: (dir: 'left' | 'right' | 'up' | 'down') => void;
  zoomReset?: () => void;
  zoomFit?: () => void;
  zoomToFocused?: () => void;
  moveMode?: () => void;
  newTerminalNode?: () => void;
  openQuickPalette: () => void;
  openFullPalette: () => void;
  openProject: () => void;
  saveLayout: () => void;
  loadLayout: () => void;
  switchProfile: () => void;
  showKeybindings: () => void;
  newWorkspace?: () => void;
  closeWorkspace?: () => void;
  nextWorkspace?: () => void;
  prevWorkspace?: () => void;
  focusWorkspace?: (index: number) => void;
  renameWorkspace?: () => void;
  colorWorkspace?: () => void;
  switchTheme?: () => void;
  switchFont?: () => void;
  toggleHighContrast?: () => void;
  setBellBehavior?: () => void;
  startAgent?: () => void;
  toggleSidebar?: () => void;
}

// --- Registry ----------------------------------------------------------------

export interface CommandRegistry {
  readonly commands: ReadonlyMap<string, Command>;
  dispatch(chord: string, ctx: AppContext): boolean;
  all(): Command[];
  byCategory(category: CommandCategory): Command[];
  findByChord(chord: string): Command | undefined;
}

export function createCommandRegistry(
  definitions: readonly CommandDefinition[],
  overrides: KeyBindingOverrides = {},
): CommandRegistry {
  const commands = new Map<string, Command>();
  const byChord = new Map<string, Command>();

  for (const def of definitions) {
    if (commands.has(def.id)) {
      throw new Error(`Duplicate command id: ${def.id}`);
    }
    const override = overrides[def.id];
    const command =
      override && override.key
        ? { ...def, keybinding: override.key, aliases: [] }
        : def;
    commands.set(def.id, command);
    if (override === null) continue;
    if (command.keybinding) byChord.set(command.keybinding, command);
    for (const alias of command.aliases ?? []) {
      byChord.set(alias, command);
    }
  }

  return {
    commands,
    dispatch(chord: string, ctx: AppContext): boolean {
      const cmd = byChord.get(chord);
      if (!cmd) return false;
      cmd.handler(ctx);
      return true;
    },
    all(): Command[] {
      return [...commands.values()];
    },
    byCategory(category: CommandCategory): Command[] {
      return [...commands.values()].filter((c) => c.category === category);
    },
    findByChord(chord: string): Command | undefined {
      return byChord.get(chord);
    },
  };
}

// --- v0 Command Catalog (CMD-03) ---------------------------------------------

const DIRECTIONS = ['Left', 'Right', 'Up', 'Down'] as const;
type Dir = (typeof DIRECTIONS)[number];
const dir = (d: Dir) => d.toLowerCase() as 'left' | 'right' | 'up' | 'down';

export function v0Commands(): CommandDefinition[] {
  return [
    // ---- Pane ---------------------------------------------------------------
    {
      id: 'pane.splitRight',
      label: 'Split Right',
      category: 'Pane',
      keybinding: 'Cmd+D',
      aliases: ['Cmd+\\'],
      handler: (ctx) => ctx.splitFocused('H'),
    },
    {
      id: 'pane.splitBelow',
      label: 'Split Below',
      category: 'Pane',
      keybinding: 'Cmd+Shift+D',
      aliases: ['Cmd+Shift+\\'],
      handler: (ctx) => ctx.splitFocused('V'),
    },
    {
      id: 'pane.close',
      label: 'Close Pane',
      category: 'Pane',
      keybinding: 'Cmd+W',
      handler: (ctx) => ctx.closeFocused(),
    },
    {
      id: 'pane.equalize',
      label: 'Equalize Panes',
      category: 'Pane',
      keybinding: 'Cmd+=',
      handler: (ctx) => ctx.equalizePanes(),
    },
    {
      id: 'pane.focusNext',
      label: 'Focus Next Pane',
      category: 'Pane',
      keybinding: 'Cmd+]',
      handler: (ctx) => ctx.focusNext(),
    },
    {
      id: 'pane.focusPrev',
      label: 'Focus Previous Pane',
      category: 'Pane',
      keybinding: 'Cmd+[',
      handler: (ctx) => ctx.focusPrev(),
    },
    // ⌘1–⌘9 numeric focus
    ...Array.from({ length: 9 }, (_, i) => ({
      id: `pane.focus${i + 1}`,
      label: `Focus Pane ${i + 1}`,
      category: 'Pane' as CommandCategory,
      keybinding: `Cmd+${i + 1}`,
      handler: (ctx: AppContext) => ctx.focusIndex(i + 1),
    })),
    // Directional focus (⌘⌥Arrow)
    ...DIRECTIONS.map((d) => ({
      id: `pane.focus${d}`,
      label: `Focus ${d}`,
      category: 'Pane' as CommandCategory,
      keybinding: `Cmd+Alt+Arrow${d}`,
      handler: (ctx: AppContext) => ctx.focusDirection(dir(d)),
    })),
    // Directional resize (⌘⌥⇧Arrow)
    ...DIRECTIONS.map((d) => ({
      id: `pane.resize${d}`,
      label: `Resize ${d}`,
      category: 'Pane' as CommandCategory,
      keybinding: `Cmd+Alt+Shift+Arrow${d}`,
      handler: (ctx: AppContext) => ctx.resizeDirection(dir(d)),
    })),

    // ---- Canvas -------------------------------------------------------------
    {
      id: 'canvas.zoomReset',
      label: 'Reset Zoom',
      category: 'Layout',
      keybinding: 'Cmd+0',
      handler: (ctx) => ctx.zoomReset?.(),
    },
    {
      id: 'canvas.zoomFit',
      label: 'Zoom to Fit',
      category: 'Layout',
      keybinding: 'Cmd+Shift+0',
      handler: (ctx) => ctx.zoomFit?.(),
    },
    {
      id: 'canvas.zoomToFocused',
      label: 'Zoom to Focused Pane',
      category: 'Layout',
      handler: (ctx) => ctx.zoomToFocused?.(),
    },
    {
      id: 'canvas.moveMode',
      label: 'Move Focus (hjkl / WASD)',
      category: 'Pane',
      handler: (ctx) => ctx.moveMode?.(),
    },
    {
      id: 'canvas.newTerminal',
      label: 'New Terminal Node',
      category: 'Pane',
      keybinding: 'Cmd+Shift+T',
      handler: (ctx) => ctx.newTerminalNode?.(),
    },

    // ---- Layout -------------------------------------------------------------
    {
      id: 'layout.cycle',
      label: 'Cycle Layout',
      category: 'Layout',
      keybinding: 'Cmd+G',
      handler: (ctx) => ctx.cycleLayout(),
    },
    {
      id: 'layout.save',
      label: 'Save Layout As...',
      category: 'Layout',
      handler: (ctx) => ctx.saveLayout(),
    },
    {
      id: 'layout.load',
      label: 'Load Layout...',
      category: 'Layout',
      handler: (ctx) => ctx.loadLayout(),
    },

    // ---- Window -------------------------------------------------------------
    {
      id: 'palette.quick',
      label: 'Quick Open',
      category: 'Window',
      keybinding: 'Cmd+P',
      handler: (ctx) => ctx.openQuickPalette(),
    },
    {
      id: 'palette.full',
      label: 'Command Palette',
      category: 'Window',
      keybinding: 'Cmd+Shift+P',
      handler: (ctx) => ctx.openFullPalette(),
    },

    {
      id: 'sidebar.toggle',
      label: 'Toggle Sidebar',
      category: 'Window',
      keybinding: 'Cmd+Shift+B',
      handler: (ctx) => ctx.toggleSidebar?.(),
    },

    // ---- Project ------------------------------------------------------------
    {
      id: 'project.open',
      label: 'Open Project',
      category: 'Project',
      handler: (ctx) => ctx.openProject(),
    },

    // ---- Settings -----------------------------------------------------------
    {
      id: 'settings.switchProfile',
      label: 'Switch Keymap Profile',
      category: 'Settings',
      handler: (ctx) => ctx.switchProfile(),
    },

    // ---- Help ---------------------------------------------------------------
    {
      id: 'help.keybindings',
      label: 'Keyboard Shortcuts',
      category: 'Help',
      handler: (ctx) => ctx.showKeybindings(),
    },
  ];
}

// --- Workspace Command Catalog (A8-03 / UXP-03) -----------------------------

export function workspaceCommands(): CommandDefinition[] {
  return [
    {
      id: 'workspace.new',
      label: 'New workspace',
      category: 'Workspace',
      handler: (ctx) => ctx.newWorkspace?.(),
    },
    {
      id: 'workspace.close',
      label: 'Close workspace',
      category: 'Workspace',
      handler: (ctx) => ctx.closeWorkspace?.(),
    },
    {
      id: 'workspace.next',
      label: 'Next workspace',
      category: 'Workspace',
      keybinding: 'Ctrl+Tab',
      handler: (ctx) => ctx.nextWorkspace?.(),
    },
    {
      id: 'workspace.prev',
      label: 'Previous workspace',
      category: 'Workspace',
      keybinding: 'Ctrl+Shift+Tab',
      handler: (ctx) => ctx.prevWorkspace?.(),
    },
    ...Array.from({ length: 9 }, (_, i) => ({
      id: `workspace.focus${i + 1}`,
      label: `Switch to workspace ${i + 1}`,
      category: 'Workspace' as CommandCategory,
      keybinding: `Ctrl+${i + 1}`,
      handler: (ctx: AppContext) => ctx.focusWorkspace?.(i),
    })),
    {
      id: 'workspace.rename',
      label: 'Rename workspace',
      category: 'Workspace',
      handler: (ctx) => ctx.renameWorkspace?.(),
    },
    {
      id: 'workspace.color',
      label: 'Color',
      category: 'Workspace',
      handler: (ctx) => ctx.colorWorkspace?.(),
    },
  ];
}

// --- Agent Command Catalog ----------------------------------------------------

export function agentCommands(): CommandDefinition[] {
  return [
    {
      id: 'agent.start',
      label: 'Start Agent',
      category: 'Pane',
      handler: (ctx) => ctx.startAgent?.(),
    },
  ];
}

// --- Appearance Command Catalog (A8-03 / UXP-04..07) ------------------------

export function appearanceCommands(): CommandDefinition[] {
  return [
    {
      id: 'theme.switch',
      label: 'Switch Theme',
      category: 'Settings',
      handler: (ctx) => ctx.switchTheme?.(),
    },
    {
      id: 'appearance.font',
      label: 'Switch Font',
      category: 'Settings',
      handler: (ctx) => ctx.switchFont?.(),
    },
    {
      id: 'appearance.highContrast',
      label: 'Toggle High Contrast',
      category: 'Settings',
      handler: (ctx) => ctx.toggleHighContrast?.(),
    },
    {
      id: 'appearance.bell',
      label: 'Set Bell Behavior',
      category: 'Settings',
      handler: (ctx) => ctx.setBellBehavior?.(),
    },
  ];
}
