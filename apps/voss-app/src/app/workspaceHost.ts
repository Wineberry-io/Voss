import { invoke } from '@tauri-apps/api/core';
import { batch, createMemo, createSignal, type Accessor } from 'solid-js';
import type { CanvasController } from '../canvas/CanvasRoot';
import { applySessionFile, layoutToSession } from '../canvas/session';
import type { ActiveLayout } from '../grid/layoutPresets';
import { loadDefaultLayout, loadLayout } from '../grid/layoutStorage';
import { loadGlobalSession, loadSession, type SessionFile } from '../grid/sessionStorage';
import type { NativeSessionRecord } from '../grid/SplitNode';
import type { AgentConfig } from '../pane/pty-ipc';
import {
  defaultCwd,
  listRecents,
  openProject,
  pickFolder,
  type ProjectInfo,
} from '../project/projectStorage';
import { createWorkspaceStore, type WorkspaceRecord } from '../workspaces/workspaceStore';
import { DEFAULT_WORKSPACE_ID, loadProjectLessSession } from '../workspaces/workspaceStorage';
import {
  installAllWorkspacesCloseSave,
  installWorkspaceStructuralAutosave,
  type WorkspaceSessionContext,
} from '../workspaces/workspaceSessionPersist';
import {
  parseWorkspaceShortcut,
  workspaceIndexForFocusAction,
} from '../workspaces/workspaceShortcuts';
import type {
  NewWorkspacePickerCreatePayload,
  NewWorkspacePickerStartEmptyPayload,
} from '../components/workspace/NewWorkspacePicker';

interface AgentEntry {
  paneId: string;
  sessionId: string;
  cliBinary: string;
  cliArgs: string;
  cwd: string;
  status: string;
  lastSeen: number;
}

const LOGIN_SHELLS = new Set(['zsh', 'bash', 'sh', 'fish', 'dash', 'tcsh', 'csh', 'ksh']);

/** A terminal pane is idle (reusable for a run) when only a login shell is in it. */
export function isIdleShellProc(proc: string | undefined): boolean {
  if (!proc) return true;
  const base = (proc.split('/').pop() ?? proc).replace(/^-/, '').toLowerCase();
  return LOGIN_SHELLS.has(base);
}

async function fetchAgentConfigs(
  workspacePath: string | null,
): Promise<Record<string, AgentConfig>> {
  const entries = await invoke<AgentEntry[]>('get_active_agents', { workspacePath }).catch(
    () => [],
  );
  const out: Record<string, AgentConfig> = {};
  for (const entry of entries) {
    let cliArgs: string[] = [];
    try {
      cliArgs = JSON.parse(entry.cliArgs) as string[];
    } catch {
      cliArgs = [];
    }
    out[entry.paneId] = { cliBinary: entry.cliBinary, cliArgs, sessionId: entry.sessionId };
  }
  return out;
}

export type MountedWorkspace = {
  id: string;
  activeLayout: Accessor<ActiveLayout>;
  setActiveLayout: (next: ActiveLayout) => void;
  project: Accessor<ProjectInfo | null>;
  setProject: (next: ProjectInfo | null) => void;
  projectLessAccepted: Accessor<boolean>;
  setProjectLessAccepted: (next: boolean) => void;
  initialSession: Accessor<SessionFile | null>;
  setInitialSession: (next: SessionFile | null) => void;
  projectLessCwd: Accessor<string | undefined>;
  setProjectLessCwd: (next: string | undefined) => void;
  everMounted: Accessor<boolean>;
  setEverMounted: (next: boolean) => void;
  agentConfigByPaneId: Accessor<Record<string, AgentConfig>>;
  setAgentConfigByPaneId: (next: Record<string, AgentConfig>) => void;
  nativeSessionByPaneId: Accessor<Record<string, NativeSessionRecord>>;
  setNativeSessionByPaneId: (next: Record<string, NativeSessionRecord>) => void;
  orphanSweepDone: boolean;
  gridController?: CanvasController;
  sessionCleanup?: () => void;
};

export function createMountedWorkspace(id: string): MountedWorkspace {
  const [activeLayout, setActiveLayout] = createSignal<ActiveLayout>('custom');
  const [project, setProject] = createSignal<ProjectInfo | null>(null);
  const [projectLessAccepted, setProjectLessAccepted] = createSignal(false);
  const [initialSession, setInitialSession] = createSignal<SessionFile | null>(null);
  const [projectLessCwd, setProjectLessCwd] = createSignal<string | undefined>();
  const [everMounted, setEverMounted] = createSignal(false);
  const [agentConfigByPaneId, setAgentConfigByPaneId] = createSignal<Record<string, AgentConfig>>({});
  const [nativeSessionByPaneId, setNativeSessionByPaneId] = createSignal<
    Record<string, NativeSessionRecord>
  >({});
  return {
    id,
    activeLayout,
    setActiveLayout,
    project,
    setProject,
    projectLessAccepted,
    setProjectLessAccepted,
    initialSession,
    setInitialSession,
    projectLessCwd,
    setProjectLessCwd,
    everMounted,
    setEverMounted,
    agentConfigByPaneId,
    setAgentConfigByPaneId,
    nativeSessionByPaneId,
    setNativeSessionByPaneId,
    orphanSweepDone: false,
  };
}

export function workspaceIsReady(ws: MountedWorkspace): boolean {
  return ws.project() !== null || ws.projectLessAccepted();
}

function sessionContextFor(ws: MountedWorkspace): WorkspaceSessionContext {
  return {
    workspaceId: ws.id,
    getController: () => ws.gridController,
    getActiveLayout: () => ws.activeLayout(),
    getProjectLessAccepted: () => ws.projectLessAccepted(),
    projectPath: ws.project()?.path ?? null,
  };
}

function seedMountedMap(records: readonly WorkspaceRecord[]): Map<string, MountedWorkspace> {
  const next = new Map<string, MountedWorkspace>();
  for (const record of records) next.set(record.id, createMountedWorkspace(record.id));
  return next;
}

function sessionPaneIds(session: SessionFile): string[] {
  return applySessionFile(session).canvas.nodes.map((n) => n.id);
}

export interface WorkspaceHostDeps {
  /** Fires whenever a project path is opened for a workspace (keymap watch). */
  onProjectOpened: (path: string) => void;
  onCloseBlocked: () => void;
}

export function createWorkspaceHost(deps: WorkspaceHostDeps) {
  const workspaceStore = createWorkspaceStore();
  const [mountedById, setMountedById] = createSignal<Map<string, MountedWorkspace>>(
    seedMountedMap(workspaceStore.workspaces()),
  );
  const [recents, setRecents] = createSignal<string[]>([]);
  const [newWorkspacePickerOpen, setNewWorkspacePickerOpen] = createSignal(false);
  const [focusedPaneId, setFocusedPaneId] = createSignal<string | undefined>();
  const [paneCount, setPaneCount] = createSignal(0);
  const [controllerTick, setControllerTick] = createSignal(0);
  let closeSaveUnlisten: (() => void) | undefined;

  const activeId = () => workspaceStore.activeId();
  let cachedWorkspaceIds: string[] = [];
  const workspaceIds = createMemo(() => {
    const next = workspaceStore.workspaces().map((w) => w.id);
    if (
      next.length === cachedWorkspaceIds.length &&
      next.every((id, i) => id === cachedWorkspaceIds[i])
    ) {
      return cachedWorkspaceIds;
    }
    cachedWorkspaceIds = next;
    return next;
  });
  const activeMounted = createMemo(() => {
    const id = activeId();
    return id ? mountedById().get(id) : undefined;
  });
  const gridController = () => {
    controllerTick();
    return activeMounted()?.gridController;
  };
  const workspacePath = () => {
    const ws = activeMounted();
    return ws?.project()?.path ?? ws?.projectLessCwd();
  };
  const showGrid = () => {
    const ws = activeMounted();
    return ws != null && workspaceIsReady(ws);
  };

  const restoreWorkspaceFromRecord = async (
    ws: MountedWorkspace,
    record: WorkspaceRecord,
  ): Promise<void> => {
    if (record.projectPath) {
      try {
        const info = await openProject(record.projectPath);
        const agentConfigs = await fetchAgentConfigs(info.path);
        let session: SessionFile | null = await loadSession(record.id).catch(() => null);
        if (!session) {
          const layout = await loadDefaultLayout(record.id).catch(() => null);
          if (layout) session = layoutToSession(layout, false);
        }
        batch(() => {
          ws.setAgentConfigByPaneId(agentConfigs);
          ws.setInitialSession(session);
          ws.setProject(info);
          ws.setProjectLessAccepted(true);
          ws.setEverMounted(true);
        });
        workspaceStore.setProjectPath(record.id, info.path);
        deps.onProjectOpened(info.path);
      } catch (e) {
        console.error('restore workspace project failed:', e);
      }
      return;
    }

    let session: SessionFile | null = await loadProjectLessSession(record.id).catch(() => null);
    if (!session && record.id === DEFAULT_WORKSPACE_ID) {
      session = await loadGlobalSession().catch(() => null);
    }
    if (session?.projectLessAccepted) {
      const agentConfigs = await fetchAgentConfigs(null);
      batch(() => {
        ws.setAgentConfigByPaneId(agentConfigs);
        ws.setInitialSession(session);
        ws.setProjectLessAccepted(true);
        ws.setEverMounted(true);
      });
    }
  };

  const bootstrapWorkspaceProject = async (
    ws: MountedWorkspace,
    workspaceId: string,
    path: string,
    layoutName?: string | null,
  ): Promise<void> => {
    try {
      const info = await openProject(path);
      setRecents(await listRecents());
      const agentConfigs = await fetchAgentConfigs(info.path);
      let session: SessionFile | null = await loadSession(workspaceId).catch(() => null);
      if (!session && layoutName) {
        const layout = await loadLayout(workspaceId, layoutName).catch(() => null);
        if (layout) session = layoutToSession(layout, false);
      }
      if (!session) {
        const layout = await loadDefaultLayout(workspaceId).catch(() => null);
        if (layout) session = layoutToSession(layout, false);
      }
      batch(() => {
        ws.setAgentConfigByPaneId(agentConfigs);
        ws.setInitialSession(session);
        ws.setProject(info);
        ws.setProjectLessAccepted(true);
        ws.setEverMounted(true);
      });
      workspaceStore.setProjectPath(workspaceId, info.path);
      deps.onProjectOpened(info.path);
      void defaultCwd(info.path)
        .then(ws.setProjectLessCwd)
        .catch(() => ws.setProjectLessCwd(undefined));
    } catch (e) {
      console.error('bootstrap workspace project failed:', e);
    }
  };

  const openSelectedProject = async (path: string, errorPrefix: string): Promise<void> => {
    const ws = activeMounted();
    if (!ws) return;
    try {
      const info = await openProject(path);
      setRecents(await listRecents());
      workspaceStore.setProjectPath(ws.id, info.path);
      await workspaceStore.persist();
      let session: SessionFile | null = await loadSession(ws.id).catch(() => null);
      if (!session) {
        const layout = await loadDefaultLayout(ws.id).catch(() => null);
        if (layout) session = layoutToSession(layout, false);
      }
      const agentConfigs = !ws.everMounted() ? await fetchAgentConfigs(info.path) : {};
      batch(() => {
        if (!ws.everMounted()) {
          ws.setAgentConfigByPaneId(agentConfigs);
          ws.setInitialSession(session);
        }
        ws.setProject(info);
        ws.setProjectLessAccepted(true);
        ws.setEverMounted(true);
      });
      deps.onProjectOpened(info.path);
    } catch (e) {
      console.error(errorPrefix, e);
    }
  };

  const handleOpenFolder = async () => {
    const picked = await pickFolder();
    if (!picked) return;
    await openSelectedProject(picked, 'open_project failed:');
  };
  const handleOpenRecent = (path: string) => {
    void openSelectedProject(path, 'open_recent failed:');
  };
  const handleStartProjectLess = () => {
    const ws = activeMounted();
    if (!ws) return;
    batch(() => {
      ws.setProjectLessAccepted(true);
      ws.setEverMounted(true);
    });
  };

  const ensureMountedRecord = (id: string): MountedWorkspace => {
    const existing = mountedById().get(id);
    if (existing) return existing;
    const ws = createMountedWorkspace(id);
    setMountedById((prev) => new Map(prev).set(id, ws));
    return ws;
  };

  const handleNewWorkspace = () => setNewWorkspacePickerOpen(true);

  const handleCreateWorkspace = async (payload: NewWorkspacePickerCreatePayload) => {
    setNewWorkspacePickerOpen(false);
    const record = workspaceStore.add({
      name: payload.name,
      projectPath: payload.folderPath,
      accentColor: payload.accentColor,
    });
    const ws = ensureMountedRecord(record.id);
    await workspaceStore.persist();
    if (payload.folderPath) {
      await bootstrapWorkspaceProject(ws, record.id, payload.folderPath, payload.layoutName);
    }
  };

  const handleStartEmptyWorkspace = async (payload: NewWorkspacePickerStartEmptyPayload) => {
    setNewWorkspacePickerOpen(false);
    const record = workspaceStore.add({ name: payload.name, accentColor: payload.accentColor });
    const ws = ensureMountedRecord(record.id);
    batch(() => {
      ws.setProjectLessAccepted(true);
      ws.setEverMounted(true);
    });
    void defaultCwd(null)
      .then(ws.setProjectLessCwd)
      .catch(() => ws.setProjectLessCwd(undefined));
    void workspaceStore.persist();
  };

  const handleActivateWorkspace = (id: string) => {
    workspaceStore.activate(id);
    void workspaceStore.persist();
  };
  const handleRenameWorkspace = (id: string, name: string) => {
    workspaceStore.rename(id, name);
    void workspaceStore.persist();
  };
  const handleColorWorkspace = (id: string, color: string) => {
    workspaceStore.setAccentColor(id, color);
    void workspaceStore.persist();
  };
  const handleReorderWorkspaces = (fromIndex: number, toIndex: number) => {
    workspaceStore.reorder(fromIndex, toIndex);
    void workspaceStore.persist();
  };
  const handleCloseWorkspace = (id: string) => {
    if (!workspaceStore.canClose(id)) return;
    const ws = mountedById().get(id);
    ws?.sessionCleanup?.();
    if (ws) ws.gridController = undefined;
    setControllerTick((t) => t + 1);
    setMountedById((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
    workspaceStore.remove(id);
    void workspaceStore.persist();
  };
  const handleNextWorkspace = () => {
    const list = workspaceStore.workspaces();
    const current = activeId();
    if (!current || list.length === 0) return;
    const idx = list.findIndex((w) => w.id === current);
    if (idx < 0) return;
    handleActivateWorkspace(list[(idx + 1) % list.length]!.id);
  };
  const handlePrevWorkspace = () => {
    const list = workspaceStore.workspaces();
    const current = activeId();
    if (!current || list.length === 0) return;
    const idx = list.findIndex((w) => w.id === current);
    if (idx < 0) return;
    handleActivateWorkspace(list[(idx - 1 + list.length) % list.length]!.id);
  };
  const handleFocusWorkspaceByIndex = (index: number) => {
    const list = workspaceStore.workspaces();
    if (index < 0 || index >= list.length) return;
    handleActivateWorkspace(list[index]!.id);
  };
  const handleCloseActiveWorkspace = () => {
    const id = activeId();
    if (!id) return;
    if (!workspaceStore.canClose(id)) {
      deps.onCloseBlocked();
      return;
    }
    handleCloseWorkspace(id);
  };
  const handleRenameActiveWorkspace = () => {
    const id = activeId();
    if (!id) return;
    const current = workspaceStore.workspaces().find((w) => w.id === id);
    const name = window.prompt('Rename workspace', current?.name ?? '');
    const trimmed = name?.trim();
    if (trimmed) handleRenameWorkspace(id, trimmed);
  };
  const handleColorActiveWorkspace = () => {
    const id = activeId();
    if (!id) return;
    const tab = document.querySelector(`[data-workspace-tab="${id}"]`) as HTMLElement | null;
    tab?.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
  };
  const handleWorkspaceShortcut = (
    action: NonNullable<ReturnType<typeof parseWorkspaceShortcut>>,
  ) => {
    if (action === 'next') return handleNextWorkspace();
    if (action === 'prev') return handlePrevWorkspace();
    const index = workspaceIndexForFocusAction(action);
    if (index != null) handleFocusWorkspaceByIndex(index);
  };

  const allSessionContexts = (): WorkspaceSessionContext[] =>
    [...mountedById().values()].map(sessionContextFor);

  const bindController = (ws: MountedWorkspace, c: CanvasController) => {
    ws.gridController = c;
    setControllerTick((t) => t + 1);
    ws.sessionCleanup?.();
    ws.sessionCleanup = installWorkspaceStructuralAutosave(sessionContextFor(ws));
    if (!ws.orphanSweepDone) {
      ws.orphanSweepDone = true;
      const session = ws.initialSession();
      if (session) {
        const wp = ws.project()?.path ?? null;
        void invoke('sweep_orphan_agents', {
          validPaneIds: sessionPaneIds(session),
          workspacePath: wp,
        }).catch((e) => console.error('[voss-app] agent orphan sweep failed:', e));
      }
    }
  };

  const boot = async () => {
    void listRecents()
      .then(setRecents)
      .catch(() => setRecents([]));
    await workspaceStore.load();
    const nextMounted = new Map(mountedById());
    for (const record of workspaceStore.workspaces()) {
      if (!nextMounted.has(record.id)) nextMounted.set(record.id, createMountedWorkspace(record.id));
    }
    setMountedById(nextMounted);
    for (const record of workspaceStore.workspaces()) {
      const ws = nextMounted.get(record.id);
      if (!ws) continue;
      void defaultCwd(record.projectPath ?? null)
        .then(ws.setProjectLessCwd)
        .catch(() => ws.setProjectLessCwd(undefined));
      void restoreWorkspaceFromRecord(ws, record);
    }
    closeSaveUnlisten = await installAllWorkspacesCloseSave(
      allSessionContexts,
      () => workspaceStore.snapshotIndex(),
      async () => {
        await workspaceStore.persist();
      },
      () => activeMounted()?.project()?.path ?? null,
    );
  };

  const dispose = () => {
    closeSaveUnlisten?.();
    for (const ws of mountedById().values()) ws.sessionCleanup?.();
  };

  return {
    workspaceStore,
    mountedById,
    recents,
    setRecents,
    newWorkspacePickerOpen,
    setNewWorkspacePickerOpen,
    focusedPaneId,
    setFocusedPaneId,
    paneCount,
    setPaneCount,
    activeId,
    workspaceIds,
    activeMounted,
    gridController,
    workspacePath,
    showGrid,
    openSelectedProject,
    handleOpenFolder,
    handleOpenRecent,
    handleStartProjectLess,
    handleNewWorkspace,
    handleCreateWorkspace,
    handleStartEmptyWorkspace,
    handleActivateWorkspace,
    handleRenameWorkspace,
    handleColorWorkspace,
    handleReorderWorkspaces,
    handleCloseWorkspace,
    handleNextWorkspace,
    handlePrevWorkspace,
    handleFocusWorkspaceByIndex,
    handleCloseActiveWorkspace,
    handleRenameActiveWorkspace,
    handleColorActiveWorkspace,
    handleWorkspaceShortcut,
    bindController,
    boot,
    dispose,
  };
}

export type WorkspaceHost = ReturnType<typeof createWorkspaceHost>;
