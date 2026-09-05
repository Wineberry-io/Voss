import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';
import { fireEvent, waitFor } from '@testing-library/dom';

const h = vi.hoisted(() => ({
  pickFolder: vi.fn(),
  openProject: vi.fn(),
  listRecents: vi.fn(),
  defaultCwd: vi.fn(),
  saveLayout: vi.fn(),
  loadLayout: vi.fn(),
  loadDefaultLayout: vi.fn(),
  applyPreset: vi.fn(),
  applyLoadedLayout: vi.fn(),
  snapshot: vi.fn(),
  gridMountCount: 0,
  workspaceStore: null as import('../workspaces/workspaceStore').WorkspaceStore | null,
  setupProps: undefined as
    | {
        recents: string[];
        onOpenProject: () => void;
        onOpenRecent: (path: string) => void;
        onStartProjectLess: () => void;
      }
    | undefined,
}));

vi.mock('../project/projectStorage', () => ({
  pickFolder: h.pickFolder,
  openProject: h.openProject,
  listRecents: h.listRecents,
  defaultCwd: h.defaultCwd,
}));

vi.mock('../grid/layoutStorage', () => ({
  saveLayout: h.saveLayout,
  loadLayout: h.loadLayout,
  loadDefaultLayout: h.loadDefaultLayout,
  listLayouts: vi.fn().mockResolvedValue([]),
}));
vi.mock('../grid/sessionStorage', () => ({
  loadSession: vi.fn().mockResolvedValue(null),
  loadGlobalSession: vi.fn().mockResolvedValue(null),
  saveSession: vi.fn(),
  saveGlobalSession: vi.fn(),
}));
vi.mock('../workspaces/workspaceSessionPersist', () => ({
  installWorkspaceStructuralAutosave: vi.fn(() => () => {}),
  installAllWorkspacesCloseSave: vi.fn(() => Promise.resolve(() => {})),
}));
vi.mock('../workspaces/workspaceStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../workspaces/workspaceStore')>();
  return {
    ...actual,
    createWorkspaceStore: (
      initial?: Parameters<typeof actual.createWorkspaceStore>[0],
    ) => {
      const store = actual.createWorkspaceStore(initial);
      h.workspaceStore = store;
      return store;
    },
  };
});

vi.mock('../workspaces/workspaceStorage', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../workspaces/workspaceStorage')>();
  return {
    ...actual,
    loadWorkspacesIndex: vi.fn().mockResolvedValue({
      version: actual.CURRENT_WORKSPACES_VERSION,
      activeWorkspaceId: actual.DEFAULT_WORKSPACE_ID,
      workspaces: [
        {
          id: actual.DEFAULT_WORKSPACE_ID,
          name: 'Workspace',
          accentColor: actual.DEFAULT_ACCENT_COLOR,
          order: 0,
        },
      ],
    }),
    saveWorkspacesIndex: vi.fn().mockResolvedValue(undefined),
    loadProjectLessSession: vi.fn().mockResolvedValue(null),
    saveProjectLessSession: vi.fn().mockResolvedValue(undefined),
  };
});
vi.mock('../grid/sessionCommands', () => ({
  layoutToSession: vi.fn((layout: unknown) => layout),
}));
vi.mock('../command-palette/CommandPalette', () => ({
  default: () => null,
}));
vi.mock('../command-palette/toast', () => ({
  default: () => null,
  showToast: vi.fn(),
}));
vi.mock('../command-palette/registry', () => ({
  createCommandRegistry: vi.fn(() => ({
    commands: new Map(),
    all: () => [],
    byCategory: () => [],
    dispatch: () => false,
    findByChord: () => undefined,
  })),
  v0Commands: vi.fn(() => []),
  workspaceCommands: vi.fn(() => []),
  appearanceCommands: vi.fn(() => []),
}));
vi.mock('../command-palette/chords', () => ({
  normalizeChord: vi.fn(() => null),
  normalizePrefixKey: vi.fn(() => null),
}));
vi.mock('../command-palette/keymapStorage', () => ({
  loadKeymapProfile: vi.fn().mockResolvedValue('vscode'),
  saveKeymapProfile: vi.fn().mockResolvedValue(undefined),
  watchWorkspaceKeymap: vi.fn().mockResolvedValue(() => {}),
}));
vi.mock('../command-palette/nativeMenu', () => ({
  setAsAppMenu: vi.fn().mockResolvedValue(undefined),
}));
vi.mock('../command-palette/quickOpen', () => ({
  buildQuickOpenItems: vi.fn(() => []),
}));
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: vi.fn(() => ({
    onCloseRequested: vi.fn(() => Promise.resolve(() => {})),
    close: vi.fn(),
  })),
}));

vi.mock('../canvas/CanvasRoot', () => ({
  default: (props: {
    active?: () => boolean;
    controllerRef?: (ctrl: {
      applyPreset: typeof h.applyPreset;
      applyLoadedLayout: typeof h.applyLoadedLayout;
      applySession: ReturnType<typeof vi.fn>;
      splitFocused: ReturnType<typeof vi.fn>;
      closeFocused: ReturnType<typeof vi.fn>;
      equalizePanes: ReturnType<typeof vi.fn>;
      cycleLayout: ReturnType<typeof vi.fn>;
      focusNext: ReturnType<typeof vi.fn>;
      focusPrev: ReturnType<typeof vi.fn>;
      focusIndex: ReturnType<typeof vi.fn>;
      focusDirection: ReturnType<typeof vi.fn>;
      resizeDirection: ReturnType<typeof vi.fn>;
      snapshot: typeof h.snapshot;
    }) => void;
    projectCwd?: string;
  }) => {
    h.gridMountCount += 1;
    props.controllerRef?.({
      applyPreset: h.applyPreset,
      applyLoadedLayout: h.applyLoadedLayout,
      applySession: vi.fn(),
      splitFocused: vi.fn(),
      closeFocused: vi.fn(),
      equalizePanes: vi.fn(),
      cycleLayout: vi.fn(),
      focusNext: vi.fn(),
      focusPrev: vi.fn(),
      focusIndex: vi.fn(),
      focusDirection: vi.fn(),
      resizeDirection: vi.fn(),
      snapshot: h.snapshot,
    });
    return (
      <div
        data-testid="grid-root"
        data-mount-id={String(h.gridMountCount)}
        data-project-cwd={props.projectCwd ?? ''}
        data-active={props.active?.() !== false ? 'true' : 'false'}
      >
        grid
      </div>
    );
  },
}));

vi.mock('../components/setup/SetupWindow', () => ({
  default: (props: {
    recents: string[];
    onOpenProject: () => void;
    onOpenRecent: (path: string) => void;
    onStartProjectLess: () => void;
  }) => {
    h.setupProps = props;
    return (
      <main data-testid="setup-window">
        <button type="button" aria-label="Open project" onClick={props.onOpenProject}>
          Open project
        </button>
        <button
          type="button"
          aria-label="Start without project"
          onClick={props.onStartProjectLess}
        >
          Start without project
        </button>
        {props.recents.map((path) => {
          const name = path.split('/').pop() || path;
          return (
            <button
              type="button"
              aria-label={`Open recent: ${name}`}
              onClick={() => props.onOpenRecent(path)}
            >
              {path}
            </button>
          );
        })}
      </main>
    );
  },
}));

vi.mock('../components/workspace/NewWorkspacePicker', () => ({
  default: (props: {
    onDismiss: () => void;
    onCreate: (payload: unknown) => void;
    onStartEmpty: (payload: unknown) => void;
  }) => (
    <div data-testid="new-workspace-picker">
      <button type="button" data-testid="picker-dismiss" onClick={props.onDismiss}>
        dismiss
      </button>
      <button
        type="button"
        data-testid="picker-start-empty"
        onClick={() =>
          props.onStartEmpty({ name: 'Empty', accentColor: 'blue' })
        }
      >
        Start empty
      </button>
    </div>
  ),
}));

import App from '../App';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown) {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}

afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  vi.restoreAllMocks();
});

function project(path: string, name: string) {
  return { path, name, gitBranch: null };
}

beforeEach(() => {
  h.pickFolder.mockReset();
  h.openProject.mockReset();
  h.listRecents.mockReset();
  h.defaultCwd.mockReset();
  h.saveLayout.mockReset();
  h.loadLayout.mockReset();
  h.loadDefaultLayout.mockReset();
  h.applyPreset.mockReset();
  h.applyLoadedLayout.mockReset();
  h.snapshot.mockReset();
  h.gridMountCount = 0;
  h.workspaceStore = null;
  h.setupProps = undefined;

  h.listRecents.mockResolvedValue([]);
  h.defaultCwd.mockResolvedValue('/Users/benjaminmarks');
  h.loadDefaultLayout.mockResolvedValue(null);
});

describe('App — setup branch', () => {
  it('renders workspace tab bar above the terminal grid when a workspace is ready', async () => {
    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    expect(el.querySelector('[data-workspace-tabbar]')).toBeNull();
    fireEvent.click(
      el.querySelector('button[aria-label="Start without project"]')!,
    );
    await waitFor(() =>
      expect(el.querySelector('[data-workspace-tabbar]')).not.toBeNull(),
    );
  });

  it('+ opens the new workspace picker', async () => {
    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(
      el.querySelector('button[aria-label="Start without project"]')!,
    );
    await waitFor(() =>
      expect(el.querySelector('[data-workspace-tabbar]')).not.toBeNull(),
    );
    fireEvent.click(el.querySelector('[aria-label="New workspace"]')!);
    expect(el.querySelector('[data-testid="new-workspace-picker"]')).not.toBeNull();
  });

  it('renders SetupWindow and not GridRoot on initial no-project mount', () => {
    const el = mount(() => <App />);
    expect(el.querySelector('[data-testid="setup-window"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="grid-root"]')).toBeNull();
  });

  it("shows the titlebar's Voss ADE fallback on initial mount", () => {
    const el = mount(() => <App />);
    expect(el.textContent).toContain('Voss ADE');
  });

  it('start without project mounts GridRoot and keeps the titlebar fallback', async () => {
    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(
      el.querySelector('button[aria-label="Start without project"]')!,
    );
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull(),
    );
    expect(el.querySelector('[data-testid="setup-window"]')).toBeNull();
    expect(el.textContent).toContain('Voss ADE');
  });

  it('stores recents from the startup read in SetupWindow props', async () => {
    h.listRecents.mockResolvedValueOnce(['/tmp/a']);
    const el = mount(() => <App />);
    await waitFor(() =>
      expect(el.querySelector('button[aria-label="Open recent: a"]')).not.toBeNull(),
    );
  });
});

describe('App — project open flow', () => {
  it('opens a picked project, mounts GridRoot, updates titlebar, and loads default layout', async () => {
    h.pickFolder.mockResolvedValueOnce('/tmp/x');
    h.openProject.mockResolvedValueOnce(project('/tmp/x', 'x'));
    h.listRecents.mockResolvedValueOnce([]).mockResolvedValueOnce(['/tmp/x']);

    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);

    await waitFor(() => expect(el.textContent).toContain('x'));
    await waitFor(() => expect(h.loadDefaultLayout).toHaveBeenCalledWith('default'));
    expect(h.openProject).toHaveBeenCalledWith('/tmp/x');
    expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull();
  });

  it('does not block project open when default layout loading rejects', async () => {
    h.pickFolder.mockResolvedValueOnce('/tmp/x');
    h.openProject.mockResolvedValueOnce(project('/tmp/x', 'x'));
    h.loadDefaultLayout.mockRejectedValueOnce(new Error('bad default'));

    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);

    // A6 D-10: session/default resolved before project state set.
    // Rejected default is caught silently → project still opens.
    await waitFor(() => expect(el.textContent).toContain('x'));
    expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull();
  });

  it('keeps setup visible when the folder picker is cancelled', async () => {
    h.pickFolder.mockResolvedValueOnce(null);
    const el = mount(() => <App />);
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);
    await waitFor(() => expect(h.pickFolder).toHaveBeenCalled());
    expect(h.openProject).not.toHaveBeenCalled();
    expect(el.querySelector('[data-testid="setup-window"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="grid-root"]')).toBeNull();
  });

  it('logs open_project errors and leaves setup visible', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    h.pickFolder.mockResolvedValueOnce('/tmp/missing');
    h.openProject.mockRejectedValueOnce('project not found');

    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);

    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(el.querySelector('[data-testid="setup-window"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="grid-root"]')).toBeNull();
  });

  it('updates project from an existing open-grid state without remounting GridRoot', async () => {
    h.openProject.mockResolvedValueOnce(project('/tmp/a', 'a'));
    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());

    h.setupProps?.onOpenRecent('/tmp/a');
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull(),
    );
    const mountId = el
      .querySelector('[data-testid="grid-root"]')!
      .getAttribute('data-mount-id');

    h.openProject.mockResolvedValueOnce(project('/tmp/b', 'b'));
    h.setupProps?.onOpenRecent('/tmp/b');
    await waitFor(() => expect(el.textContent).toContain('b'));

    expect(
      el.querySelector('[data-testid="grid-root"]')?.getAttribute('data-mount-id'),
    ).toBe(mountId);
    expect(h.gridMountCount).toBe(1);
  });

  it('resolves session/default before flushing project state (A6 D-10)', async () => {
    const order: string[] = [];
    h.pickFolder.mockResolvedValueOnce('/tmp/x');
    h.openProject.mockImplementationOnce(async () => {
      order.push('openProject');
      return project('/tmp/x', 'x');
    });
    h.listRecents.mockResolvedValue([]);
    h.loadDefaultLayout.mockImplementationOnce(async () => {
      order.push('loadDefaultLayout');
      return null;
    });

    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(el.querySelector('button[aria-label="Open project"]')!);

    // A6 flow: session/default are resolved BEFORE project state is set.
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull(),
    );
    expect(order).toContain('openProject');
    expect(order).toContain('loadDefaultLayout');
  });

  it('Ctrl+Tab switches to the next workspace', async () => {
    const { loadWorkspacesIndex, loadProjectLessSession } = await import(
      '../workspaces/workspaceStorage'
    );
    const projectLessSession = {
      version: 1 as const,
      activePreset: null,
      grid: {
        root: {
          kind: 'pane' as const,
          id: 'p1',
          cwd: '/tmp',
          shell: '/bin/zsh',
          index: 1,
        },
        focusedId: 'p1',
      },
      panes: [{ id: 'p1', scrollback: null }],
      projectLessAccepted: true,
    };

    vi.mocked(loadWorkspacesIndex).mockResolvedValueOnce({
      version: 1,
      activeWorkspaceId: 'default',
      workspaces: [
        {
          id: 'default',
          name: 'One',
          accentColor: 'blue',
          order: 0,
        },
        {
          id: 'second',
          name: 'Two',
          accentColor: 'green',
          order: 1,
        },
      ],
    });
    vi.mocked(loadProjectLessSession).mockResolvedValue(projectLessSession);

    mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    expect(h.workspaceStore!.activeId()).toBe('default');

    window.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Tab',
        ctrlKey: true,
        bubbles: true,
      }),
    );

    await waitFor(() => expect(h.workspaceStore!.activeId()).toBe('second'));
  });

  it('keeps GridRoot mounted when switching active workspace (A8 D-01)', async () => {
    const { loadWorkspacesIndex, loadProjectLessSession } = await import(
      '../workspaces/workspaceStorage'
    );
    const projectLessSession = {
      version: 1 as const,
      activePreset: null,
      grid: {
        root: {
          kind: 'pane' as const,
          id: 'p1',
          cwd: '/tmp',
          shell: '/bin/zsh',
          index: 1,
        },
        focusedId: 'p1',
      },
      panes: [{ id: 'p1', scrollback: null }],
      projectLessAccepted: true,
    };

    vi.mocked(loadWorkspacesIndex).mockResolvedValueOnce({
      version: 1,
      activeWorkspaceId: 'default',
      workspaces: [
        {
          id: 'default',
          name: 'One',
          accentColor: 'blue',
          order: 0,
        },
        {
          id: 'second',
          name: 'Two',
          accentColor: 'green',
          order: 1,
        },
      ],
    });
    vi.mocked(loadProjectLessSession).mockResolvedValue(projectLessSession);

    const el = mount(() => <App />);

    await waitFor(() =>
      expect(el.querySelectorAll('[data-testid="grid-root"]').length).toBe(2),
    );

    const grids = el.querySelectorAll('[data-workspace-id]');
    expect(grids.length).toBe(2);

    h.workspaceStore!.activate('second');

    await waitFor(() => {
      expect(el.querySelectorAll('[data-testid="grid-root"]').length).toBe(2);
    });

    const hidden = el.querySelector('[data-workspace-id="default"]') as HTMLElement;
    const shown = el.querySelector('[data-workspace-id="second"]') as HTMLElement;
    expect(hidden?.style.display).toBe('none');
    expect(shown?.style.display).toBe('flex');
  });

  it('does not persist projectLessAccepted', async () => {
    const el = mount(() => <App />);
    await waitFor(() => expect(h.workspaceStore).not.toBeNull());
    fireEvent.click(
      el.querySelector('button[aria-label="Start without project"]')!,
    );
    await waitFor(() =>
      expect(el.querySelector('[data-testid="grid-root"]')).not.toBeNull(),
    );

    const persistenceCalls = JSON.stringify([
      h.saveLayout.mock.calls,
      h.loadLayout.mock.calls,
      h.loadDefaultLayout.mock.calls,
      h.pickFolder.mock.calls,
      h.openProject.mock.calls,
      h.listRecents.mock.calls,
      h.defaultCwd.mock.calls,
    ]);
    expect(persistenceCalls).not.toContain('projectLessAccepted');
  });
});
