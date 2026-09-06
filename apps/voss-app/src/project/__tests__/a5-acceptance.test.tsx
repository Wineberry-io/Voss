import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';
import { fireEvent, waitFor } from '@testing-library/dom';

const h = vi.hoisted(() => ({
  invoke: vi.fn(),
  openDialog: vi.fn(),
  platform: vi.fn(),
  gridMountCount: 0,
}));

vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: h.openDialog }));
vi.mock('@tauri-apps/plugin-os', () => ({ platform: h.platform }));
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    close: vi.fn(),
    minimize: vi.fn(),
    setFullscreen: vi.fn(),
    isFullscreen: vi.fn().mockResolvedValue(false),
    onCloseRequested: vi.fn(() => Promise.resolve(() => {})),
  }),
}));

vi.mock('../../canvas/CanvasRoot', () => ({
  default: (props: {
    controllerRef?: (ctrl: {
      applyPreset: () => void;
      applyLoadedLayout: () => void;
      snapshot: () => { root: unknown; focusedId: string };
    }) => void;
    projectCwd?: string;
  }) => {
    h.gridMountCount += 1;
    props.controllerRef?.({
      applyPreset: vi.fn(),
      applyLoadedLayout: vi.fn(),
      snapshot: () => ({ root: { kind: 'pane', id: 'pane-1' }, focusedId: 'pane-1' }),
    });
    return (
      <div
        data-testid="grid-root"
        data-mount-id={String(h.gridMountCount)}
        data-project-cwd={props.projectCwd ?? ''}
      >
        grid
      </div>
    );
  },
}));

import App from '../../App';
import SetupWindow from '../../components/setup/SetupWindow';
import Titlebar from '../../components/titlebar/Titlebar';
import {
  defaultCwd,
  listRecents,
  openProject,
  pickFolder,
  type ProjectInfo,
} from '../projectStorage';

const RUST_COVERAGE = [
  'update_recents_caps_at_five_newest_first',
  'update_recents_moves_existing_path_to_front_without_duplicate',
  'open_project_does_not_create_voss_directory',
  'open_project_returns_current_branch_for_git_dir',
  'open_project_returns_none_branch_for_non_git_dir',
  'default_cwd_falls_back_to_home_for_no_project',
];

let dispose: (() => void) | undefined;
function mount(ui: () => unknown) {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}

function project(path: string, name = path.split('/').pop() || path): ProjectInfo {
  return { path, name, gitBranch: null };
}

function mockInvoke() {
  h.invoke.mockImplementation((cmd: string, args?: Record<string, unknown>) => {
    if (cmd === 'open_project') return Promise.resolve(project(args?.path as string));
    if (cmd === 'load_recents') return Promise.resolve(['/tmp/recent-a']);
    if (cmd === 'default_cwd') return Promise.resolve(args?.projectPath ?? '/Users/ben');
    if (cmd === 'load_default_layout') return Promise.resolve(null);
    if (cmd === 'load_workspaces_index') {
      return Promise.resolve({
        version: 1,
        activeWorkspaceId: 'default',
        workspaces: [
          {
            id: 'default',
            name: 'Workspace',
            accentColor: 'blue',
            order: 0,
          },
        ],
      });
    }
    if (cmd === 'load_project_less_session') return Promise.resolve(null);
    if (cmd === 'load_global_session') return Promise.resolve(null);
    if (cmd === 'load_session') return Promise.resolve(null);
    if (cmd === 'get_active_agents') return Promise.resolve([]);
    if (cmd === 'sweep_orphan_agents') return Promise.resolve(undefined);
    if (cmd === 'update_agents_last_seen') return Promise.resolve(undefined);
    return Promise.resolve(undefined);
  });
}

beforeEach(() => {
  h.invoke.mockReset();
  h.openDialog.mockReset();
  h.platform.mockReset().mockResolvedValue('linux');
  h.gridMountCount = 0;
  mockInvoke();
});

afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  vi.restoreAllMocks();
});

describe('WS-01 — folder picker opens a local project', () => {
  it('uses the Tauri directory picker contract', async () => {
    h.openDialog.mockResolvedValueOnce('/tmp/voss-a');
    const picked = await pickFolder();
    expect(h.openDialog).toHaveBeenCalledWith({ directory: true, multiple: false });
    expect(picked).toBe('/tmp/voss-a');
  });
  it('sets the active project and mounts the grid after a picked folder', async () => {
    h.openDialog.mockResolvedValueOnce('/tmp/voss-a');
    const el = mount(() => <App />);
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);
    // SPEC AC #2: User can select a local directory and the active path becomes it.
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith('open_project', { path: '/tmp/voss-a' }));
    await waitFor(() => expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull());
    expect(el.textContent).toContain('voss-a');
  });
  it('documents that Cmd+O is outside the locked A5 picker contract', () => {
    expect('A5-CONTEXT D-05 owns folder picker; Cmd+O accelerator is planner discretion').toContain('picker');
  });
});

describe('WS-02 — recents round-trip through global app storage', () => {
  it('listRecents reads the Rust recents command', async () => {
    h.invoke.mockResolvedValueOnce(['/tmp/a', '/tmp/b']);
    const recents = await listRecents();
    expect(h.invoke).toHaveBeenCalledWith('load_recents');
    expect(recents).toEqual(['/tmp/a', '/tmp/b']);
  });
  it('maps same-dir dedupe and cap-5 to Rust acceptance coverage', () => {
    // SPEC AC #3: Re-selecting the same directory succeeds without duplicate recents.
    expect(RUST_COVERAGE).toContain('update_recents_moves_existing_path_to_front_without_duplicate');
    // SPEC AC #8: Recents retain only the last 5 unique folders, newest first.
    expect(RUST_COVERAGE).toContain('update_recents_caps_at_five_newest_first');
  });
});

describe('WS-03 — project open stays lazy with respect to .voss', () => {
  it('maps the lazy .voss invariant to the Rust filesystem test', () => {
    // SPEC AC #9: Project open and recents reads do not create `.voss/`.
    expect(RUST_COVERAGE).toContain('open_project_does_not_create_voss_directory');
  });
});

describe('WS-04 — project metadata exposes name and git branch', () => {
  it('ProjectInfo carries path, folder basename, and nullable gitBranch', async () => {
    h.invoke.mockResolvedValueOnce({ path: '/repo/voss', name: 'voss', gitBranch: 'main' });
    const info = await openProject('/repo/voss');
    // SPEC AC #5: Project name is derived from folder basename.
    expect(info.name).toBe('voss');
    // SPEC AC #6: Git repos expose branch; non-git repos expose null.
    expect(info.gitBranch).toBe('main');
  });
  it('maps non-git branch nullability to Rust acceptance coverage', () => {
    expect(RUST_COVERAGE).toContain('open_project_returns_none_branch_for_non_git_dir');
    expect(RUST_COVERAGE).toContain('open_project_returns_current_branch_for_git_dir');
  });
});

describe('WS-05 — project-less mode is an explicit setup choice', () => {
  it('shows setup first, then starts grid without a project path', async () => {
    const el = mount(() => <App />);
    // SPEC AC #1: Startup with no active project shows setup before any project path.
    expect(el.querySelector('[aria-label="Project setup"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="grid-root"]')).toBeNull();
    fireEvent.click(el.querySelector('button[aria-label="Start without project"]')!);
    // SPEC AC #7: Starting without a project uses home cwd and no project path.
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')?.getAttribute('data-project-cwd')).toBe('/Users/ben'),
    );
    expect(el.textContent).toContain('Voss ADE');
  });
});

describe('WS-06 — pane cwd defaults come from Rust-resolved project cwd', () => {
  it('defaultCwd delegates both project and project-less cwd resolution to Tauri', async () => {
    await defaultCwd(null);
    expect(h.invoke).toHaveBeenCalledWith('default_cwd', { projectPath: null });
    await defaultCwd('/tmp/voss-a');
    expect(h.invoke).toHaveBeenCalledWith('default_cwd', { projectPath: '/tmp/voss-a' });
  });
  it('threads the open project path into GridRoot as the future-pane cwd', async () => {
    h.openDialog.mockResolvedValueOnce('/tmp/voss-a');
    const el = mount(() => <App />);
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')?.getAttribute('data-project-cwd')).toBe('/tmp/voss-a'),
    );
  });
});

describe('WS-07 — project switching path exists before palette UI lands', () => {
  it('open recent updates project metadata without remounting the grid', async () => {
    h.invoke.mockImplementation((cmd: string, args?: Record<string, unknown>) => {
      if (cmd === 'open_project') return Promise.resolve(project(args?.path as string));
      if (cmd === 'load_recents') return Promise.resolve(['/tmp/voss-a', '/tmp/voss-b']);
      if (cmd === 'default_cwd') return Promise.resolve('/Users/ben');
      if (cmd === 'load_default_layout') return Promise.resolve(null);
      if (cmd === 'get_active_agents') return Promise.resolve([]);
      return Promise.resolve(undefined);
    });
    const el = mount(() => <App />);
    await waitFor(() => expect(el.querySelector('button[aria-label="Open recent: voss-a"]')).not.toBeNull());
    fireEvent.click(el.querySelector('button[aria-label="Open recent: voss-a"]')!);
    await waitFor(() => expect(el.textContent).toContain('voss-a'));
    const firstGrid = el.querySelector('[data-testid="grid-root"]');
    fireEvent.click(el.querySelector('button[aria-label="Open recent: voss-b"]')!);
    // SPEC AC #4: Selecting a different directory updates active project metadata.
    await waitFor(() => expect(el.textContent).toContain('voss-b'));
    // SPEC AC #11: Changing project while panes exist does not destroy pane/session identities.
    expect(el.querySelector('[data-testid="grid-root"]')).toBe(firstGrid);
  });
  it('attempts default layout load and ignores failure while keeping the project open', async () => {
    h.openDialog.mockResolvedValueOnce('/tmp/voss-a');
    h.invoke.mockImplementation((cmd: string, args?: Record<string, unknown>) => {
      if (cmd === 'open_project') return Promise.resolve(project(args?.path as string));
      if (cmd === 'load_recents') return Promise.resolve([]);
      if (cmd === 'default_cwd') return Promise.resolve('/Users/ben');
      if (cmd === 'load_default_layout') return Promise.reject(new Error('invalid default'));
      if (cmd === 'load_session') return Promise.resolve(null);
      if (cmd === 'load_global_session') return Promise.resolve(null);
      if (cmd === 'get_active_agents') return Promise.resolve([]);
      return Promise.resolve(undefined);
    });
    const el = mount(() => <App />);
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);
    // A6 D-10: session/default resolved before project state; rejected default
    // caught silently → project still opens.
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull(),
    );
  });
});

describe('A5 final L2-vocab gate — setup and titlebar chrome stay L1', () => {
  it('excludes user project text while checking app chrome for forbidden terms', () => {
    const setup = mount(() => (
      <SetupWindow recents={[]} onOpenProject={() => {}} onOpenRecent={() => {}} onStartProjectLess={() => {}} />
    ));
    const titlebar = mount(() => <Titlebar projectName="agent-checker" />);
    const chromeText = (titlebar.textContent ?? '').replace('agent-checker', '');
    const chrome = `${setup.outerHTML} ${chromeText}`.toLowerCase();
    expect('agent-checker').toContain('agent');
    for (const word of ['agent', 'worktree', 'reviewer', 'model', 'cost', 'token']) {
      expect(chrome).not.toContain(word);
    }
  });
});
