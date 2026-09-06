import type { Page } from '@playwright/test';

/**
 * Shared Tauri v2 IPC mock + app boot helpers for mock-IPC e2e tests.
 *
 * Extracted from pane-drag-rearrange.spec.ts. Boots the app against `vite dev`
 * (no Tauri runtime required) with `window.__TAURI_INTERNALS__` mocked via
 * addInitScript. PTYs are inert (spawn_pty mocked) — UI behavior is what's
 * under test.
 *
 * Requires the dev server: `pnpm dev` (http://localhost:5173) — or rely on
 * the webServer auto-start in playwright.config.ts.
 */

export const APP_URL = process.env.VOSS_APP_URL ?? 'http://localhost:5173';

export interface MockWorkspace {
  id: string;
  name: string;
  projectPath: string | null;
  accentColor: string;
  order: number;
}

export interface MockConfig {
  /** Workspaces returned by load_workspaces_index. Default: single workspace
   *  with projectPath='/tmp/voss-e2e-proj' so the grid mounts immediately. */
  workspaces?: MockWorkspace[];
  /** Active workspace id (default: first workspace's id). */
  activeWorkspaceId?: string;
  /** Recents returned by load_recents (default: []). */
  recents?: string[];
  /** Layout names returned by list_layouts (default: []). */
  layoutNames?: string[];
  /** Default layout returned by load_default_layout (default: null). */
  defaultLayout?: unknown | null;
  /** Session returned by load_session (default: null). */
  session?: unknown | null;
  /** Active theme id returned by load_active_theme_id (default: null). */
  activeThemeId?: string | null;
  /** Appearance settings returned by load_appearance_settings (default: {}). */
  appearance?: Record<string, unknown>;
  /** Keymap profile returned by load_keymap_profile (default: '"vscode"'). */
  keymapProfile?: string;
  /** Keymap overrides returned by load_keymap_overrides (default: null). */
  keymapOverrides?: unknown | null;
  /** Result of the native folder dialog (plugin:dialog|open). Default: null
   *  (cancel). Set to a path string to simulate a folder pick. */
  dialogOpenResult?: string | null;
  /** Per-command overrides: command name → return value. Checked before the
   *  built-in defaults, so these win. Values must be JSON-serializable. */
  commandOverrides?: Record<string, unknown>;
  /** Track sync_grid calls into window.__SYNCS__ (default: true). */
  trackSyncs?: boolean;
}

const DEFAULT_WORKSPACES: MockWorkspace[] = [
  {
    id: 'w1',
    name: 'Test',
    projectPath: '/tmp/voss-e2e-proj',
    accentColor: 'blue',
    order: 0,
  },
];

export async function installTauriMock(
  page: Page,
  config: MockConfig = {},
): Promise<void> {
  const cfg: Required<MockConfig> = {
    workspaces: config.workspaces ?? DEFAULT_WORKSPACES,
    activeWorkspaceId: config.activeWorkspaceId ?? (config.workspaces ?? DEFAULT_WORKSPACES)[0]!.id,
    recents: config.recents ?? [],
    layoutNames: config.layoutNames ?? [],
    defaultLayout: config.defaultLayout ?? null,
    session: config.session ?? null,
    activeThemeId: config.activeThemeId ?? null,
    appearance: config.appearance ?? {},
    keymapProfile: config.keymapProfile ?? 'vscode',
    keymapOverrides: config.keymapOverrides ?? null,
    dialogOpenResult: config.dialogOpenResult ?? null,
    commandOverrides: config.commandOverrides ?? {},
    trackSyncs: config.trackSyncs ?? true,
  };

  await page.addInitScript((c: typeof cfg) => {
    let nextCallbackId = 1;
    let nextPty = 1;
    const syncs: unknown[] = [];
    (window as unknown as { __SYNCS__: unknown[] }).__SYNCS__ = syncs;
    const ptyChannels: unknown[] = [];
    (window as unknown as { __PTY_CHANNELS__: unknown[] }).__PTY_CHANNELS__ = ptyChannels;

    const invoke = (cmd: string, args?: Record<string, unknown>): unknown => {
      if (cmd in c.commandOverrides) return c.commandOverrides[cmd];
      switch (cmd) {
        case 'load_workspaces_index':
          return {
            version: 1,
            activeWorkspaceId: c.activeWorkspaceId,
            workspaces: c.workspaces,
          };
        case 'open_project':
          return {
            path: (args?.path as string) ?? '/tmp/voss-e2e-proj',
            name: 'voss-e2e-proj',
            gitBranch: null,
          };
        case 'load_keymap_profile':
          return JSON.stringify(c.keymapProfile);
        case 'load_keymap_overrides':
          return c.keymapOverrides;
        case 'load_appearance_settings':
          return c.appearance;
        case 'load_active_theme_id':
          return c.activeThemeId;
        case 'get_theme_overrides':
          return {};
        case 'load_recents':
          return c.recents;
        case 'default_cwd':
          return '/tmp/voss-e2e-proj';
        case 'spawn_pty':
          if (args?.onData) ptyChannels.push(args.onData);
          return `mock-pty-${nextPty++}`;
        case 'spawn_agent':
          return `mock-agent-${nextPty++}`;
        case 'spawn_managed_agent':
          return { pty_id: `mock-managed-${nextPty++}`, tier: 'C', sandboxed: false };
        case 'get_fg_process':
          return '';
        case 'sync_grid':
          if (c.trackSyncs) syncs.push(JSON.parse(JSON.stringify(args?.newState ?? null)));
          return null;
        case 'get_grid':
          return null;
        case 'sync_canvas':
          if (c.trackSyncs) syncs.push(JSON.parse(JSON.stringify(args?.newState ?? null)));
          return null;
        case 'get_canvas':
          return null;
        case 'get_active_agents':
        case 'list_profiles':
        case 'list_workspaces':
        case 'list_system_fonts':
        case 'list_dir':
        case 'enumerate_runs':
        case 'git_log':
        case 'sweep_orphan_agents':
          return [];
        case 'list_layouts':
          return c.layoutNames;
        case 'read_project_file':
          return { path: args?.relPath, content: `// ${args?.relPath}\nexport const x = 1;\n`, language: 'typescript', size: 32 };
        case 'load_session':
        case 'load_global_session':
        case 'load_project_less_session':
          return c.session;
        case 'load_default_layout':
          return c.defaultLayout;
        case 'load_layout':
          return null;
        case 'save_layout':
        case 'save_session':
        case 'save_global_session':
        case 'save_project_less_session':
        case 'save_workspaces_index':
        case 'save_active_theme_id':
        case 'save_active_profile_id':
        case 'save_appearance_settings':
        case 'save_keymap_profile':
        case 'save_custom_agents':
        case 'write_context_pins':
        case 'write_swarm_files':
        case 'pty_write':
        case 'pty_resize':
        case 'pty_pause':
        case 'pty_resume':
        case 'pty_kill':
        case 'mark_agent_stopped':
        case 'update_agents_last_seen':
        case 'stop_swarm_watcher':
          return null;
        case 'plugin:os|platform':
        case 'plugin:os|os_type':
          return 'macos';
        case 'plugin:dialog|open':
          return c.dialogOpenResult;
        case 'plugin:event|listen':
          return nextCallbackId++;
        default:
          return null;
      }
    };

    const callbacks = new Map<number, (response: unknown) => void>();
    (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {
      invoke,
      transformCallback(cb: (response: unknown) => void, _once?: boolean) {
        const id = nextCallbackId++;
        callbacks.set(id, cb);
        (window as unknown as Record<string, unknown>)[`_${id}`] = cb;
        return id;
      },
      unregisterCallback(id: number) {
        callbacks.delete(id);
        delete (window as unknown as Record<string, unknown>)[`_${id}`];
      },
      convertFileSrc(p: string) {
        return p;
      },
      metadata: {
        currentWindow: { label: 'main' },
        currentWebview: { label: 'main', windowLabel: 'main' },
      },
      plugins: {},
    };
  }, cfg);
}

export interface BootOptions extends MockConfig {
  viewportWidth?: number;
  viewportHeight?: number;
  /** Wait for the grid to mount (default: true). Set false to test the setup
   *  window (no project state). */
  waitForGrid?: boolean;
}

export async function bootApp(
  page: Page,
  opts: BootOptions = {},
): Promise<void> {
  const { viewportWidth = 1400, viewportHeight = 900, waitForGrid = true } = opts;
  await installTauriMock(page, opts);
  await page.setViewportSize({ width: viewportWidth, height: viewportHeight });
  await page.goto(APP_URL);
  if (waitForGrid) {
    // Wait for a VISIBLE pane (hidden grids from inactive workspaces have
    // 0×0 panes that match the selector but aren't visible).
    await page.waitForSelector('[data-pane-id]:visible', { timeout: 15000 });
  } else {
    await page.waitForSelector('main[aria-label="Project setup"]', { timeout: 15000 });
  }
}

export type PaneRect = { id: string; x: number; y: number; w: number; h: number };

export async function paneRects(page: Page): Promise<PaneRect[]> {
  return page.$$eval('[data-pane-id]', (els) =>
    els
      .map((el) => {
        const r = el.getBoundingClientRect();
        return {
          id: el.getAttribute('data-pane-id') ?? '',
          x: r.x,
          y: r.y,
          w: r.width,
          h: r.height,
        };
      })
      .filter((r) => r.w > 0 && r.h > 0),
  );
}

export async function stableRects(page: Page, count: number): Promise<PaneRect[]> {
  let prev = '';
  let rects: PaneRect[] = [];
  const { expect } = await import('@playwright/test');
  await expect
    .poll(
      async () => {
        rects = (await paneRects(page)).sort((a, b) => a.x - b.x || a.y - b.y);
        const sig = JSON.stringify(rects);
        const settled = rects.length === count && sig === prev;
        prev = sig;
        return settled;
      },
      { timeout: 7000 },
    )
    .toBe(true);
  return rects;
}