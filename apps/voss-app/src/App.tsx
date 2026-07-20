import { invoke } from '@tauri-apps/api/core';
import {
  batch,
  createEffect,
  createMemo,
  createSignal,
  onMount,
  onCleanup,
  Show,
  For,
  type Accessor,
} from 'solid-js';
import TopChrome from './components/titlebar/TopChrome';
import WorkspaceTabBar, {
  COPY_LAST_WORKSPACE_BLOCKED,
} from './components/workspace/WorkspaceTabBar';
import NewWorkspacePicker, {
  type NewWorkspacePickerCreatePayload,
  type NewWorkspacePickerStartEmptyPayload,
} from './components/workspace/NewWorkspacePicker';
import './components/workspace/workspace.css';
import GridRoot, { type GridController } from './grid/GridRoot';
import type { NativeSessionRecord } from './grid/SplitNode';
import StatusBar from './components/StatusBar';
import ContextPanel from './components/ContextPanel';
import OrgViewShell from './org/OrgViewShell';
import PortalRail from './portal/PortalRail';
import VossComposer from './composer/VossComposer';
import { devlog } from './devlog';
import PortalShell from './portal/PortalShell';
import ContextSurface from './surfaces/context/ContextSurface';
import MemorySurface from './surfaces/memory/MemorySurface';
import { setLiveServer, setLiveServerConnector } from './org/live/liveServer';
import { PORTAL_ITEMS, type PortalView } from './portal/portalTypes';
import AttentionPanel from './org/attention/AttentionPanel';
import { attentionQueue } from './org/attention/attentionQueue';
import { registerTerminalCard } from './org/model/bridge';
import { resolveTier, hookCapableCli } from './org/capabilityTier';
import RunCommandBar, {
  dispatchRunSpec,
  type RunNativeClient,
  type SpawnAgentFn,
} from './org/cockpit/RunCommandBar';
import type { RunMode } from './org/cockpit/runIntake';
import { liveLabel } from './org/live/sseClient';
import {
  buildVossClientFromHandle,
  type BuiltVossClient,
} from './org/live/vossClientBuild';
import { startVossServe } from './org/live/sidecarClient';
import { attachSession } from './org/cockpit/serverSessions';
import { registerPaneDestroyHook } from './pane/paneSessionRegistry';
import { destroyProtocolSession } from './org/live/protocolSessions';
import AdoptAgentModal from './components/modal/AdoptAgentModal';
import { registerAdoption, adoptionByPaneId } from './pane/adoptionRegistry';
import { currentRunId } from './org/orgStore';
import {
  openInGridRequest,
  setOpenInGridRequest,
  openInReviewRequest,
  setOpenInReviewRequest,
  setSelectedCardId,
} from './org/selection';
import BoardSummaryStrip from './components/BoardSummaryStrip';
import { collectLeaves } from './grid/tree';
import type { AgentConfig } from './pane/pty-ipc';
import { contextByPaneId } from './pane/contextRegistry';
import { procByPaneId } from './pane/procRegistry';
import { budgetByPaneId } from './pane/budgetRegistry';
import { isKnownAgentCli } from './pane/agentDetect';
import { agentPaneById } from './pane/agentPaneRegistry';
import AgentSidebar from './components/sidebar/AgentSidebar';
import AgentLaunchModal from './components/modal/AgentLaunchModal';
import { loadModelPrefs } from './agents/modelPrefs';
import AgentContextMenu from './components/sidebar/AgentContextMenu';
import SetupWindow from './components/setup/SetupWindow';
import CommandPalette from './command-palette/CommandPalette';
import ToastStack from './command-palette/toast';
import {
  createCommandRegistry,
  v0Commands,
  workspaceCommands,
  appearanceCommands,
  type AppContext,
  type KeyBindingOverrides,
} from './command-palette/registry';
import { normalizeChord, normalizePrefixKey } from './command-palette/chords';
import {
  loadKeymapProfile,
  saveKeymapProfile,
  watchWorkspaceKeymap,
  type KeymapProfile,
  type KeymapUpdatePayload,
} from './command-palette/keymapStorage';
import { createPrefixMode } from './command-palette/prefixMode';
import { setAsAppMenu } from './command-palette/nativeMenu';
import { showToast } from './command-palette/toast';
import { applyWindowEffects } from './appearance/windowEffects';
import { buildQuickOpenItems } from './command-palette/quickOpen';
import type {
  ActiveLayout,
  LayoutPreset,
} from './grid/layoutPresets';
import { serializeLayout } from './grid/layoutCommands';
import { layoutToSession } from './grid/sessionCommands';
import {
  listLayouts,
  loadDefaultLayout,
  loadLayout,
  saveLayout,
} from './grid/layoutStorage';
import {
  loadSession,
  loadGlobalSession,
  type SessionFile,
} from './grid/sessionStorage';
import {
  defaultCwd,
  listRecents,
  openProject,
  pickFolder,
  type ProjectInfo,
} from './project/projectStorage';
import {
  createWorkspaceStore,
  type WorkspaceRecord,
} from './workspaces/workspaceStore';
import {
  DEFAULT_WORKSPACE_ID,
  loadProjectLessSession,
} from './workspaces/workspaceStorage';
import {
  installAllWorkspacesCloseSave,
  installWorkspaceStructuralAutosave,
  type WorkspaceSessionContext,
} from './workspaces/workspaceSessionPersist';
import {
  parseWorkspaceShortcut,
  workspaceIndexForFocusAction,
} from './workspaces/workspaceShortcuts';

/**
 * App composition root (A4-02, A8-02).
 *
 * Owns the workspace index, one mounted `GridRoot` per workspace (hidden via
 * CSS when inactive — D-01), and a single all-workspace close-save handler.
 */

interface AgentEntry {
  paneId: string;
  sessionId: string;
  cliBinary: string;
  cliArgs: string;
  cwd: string;
  status: string;
  lastSeen: number;
}

// Login shells a pane's foreground process can be while idle (poll may return
// the login-dash form, e.g. "-zsh", or an absolute path).
const LOGIN_SHELLS = new Set([
  'zsh',
  'bash',
  'sh',
  'fish',
  'dash',
  'tcsh',
  'csh',
  'ksh',
]);

/** A terminal pane is "idle" (reusable for a run) when nothing is running in
 *  it — no foreground process recorded, or just a plain login shell. */
function isIdleShellProc(proc: string | undefined): boolean {
  if (!proc) return true;
  const base = (proc.split('/').pop() ?? proc).replace(/^-/, '').toLowerCase();
  return LOGIN_SHELLS.has(base);
}

async function fetchAgentConfigs(
  workspacePath: string | null,
): Promise<Record<string, AgentConfig>> {
  const entries = await invoke<AgentEntry[]>('get_active_agents', {
    workspacePath,
  }).catch(() => []);
  const out: Record<string, AgentConfig> = {};
  for (const entry of entries) {
    let cliArgs: string[] = [];
    try {
      cliArgs = JSON.parse(entry.cliArgs) as string[];
    } catch {
      cliArgs = [];
    }
    out[entry.paneId] = {
      cliBinary: entry.cliBinary,
      cliArgs,
      sessionId: entry.sessionId,
    };
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
  /** Once true, GridRoot stays mounted when switching away (D-01). */
  everMounted: Accessor<boolean>;
  setEverMounted: (next: boolean) => void;
  agentConfigByPaneId: Accessor<Record<string, AgentConfig>>;
  setAgentConfigByPaneId: (next: Record<string, AgentConfig>) => void;
  /** V15-03: per-pane native server session — pane renders ProtocolPane. */
  nativeSessionByPaneId: Accessor<Record<string, NativeSessionRecord>>;
  setNativeSessionByPaneId: (
    next: Record<string, NativeSessionRecord>,
  ) => void;
  orphanSweepDone: boolean;
  gridController?: GridController;
  sessionCleanup?: () => void;
};

function createMountedWorkspace(id: string): MountedWorkspace {
  const [activeLayout, setActiveLayout] =
    createSignal<ActiveLayout>('custom');
  const [project, setProject] = createSignal<ProjectInfo | null>(null);
  const [projectLessAccepted, setProjectLessAccepted] = createSignal(false);
  const [initialSession, setInitialSession] = createSignal<SessionFile | null>(
    null,
  );
  const [projectLessCwd, setProjectLessCwd] = createSignal<string | undefined>();
  const [everMounted, setEverMounted] = createSignal(false);
  const [agentConfigByPaneId, setAgentConfigByPaneId] = createSignal<
    Record<string, AgentConfig>
  >({});
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

// V15-03 attach seam (Plans 04/05): module-level entry that opens a structured
// pane for an EXISTING server session — same D-02 grid insertion as a native
// run, minus createSession. The mounted App registers the implementation.
let openAttachedPaneImpl: ((record: NativeSessionRecord) => void) | null =
  null;
export function openAttachedPane(record: NativeSessionRecord): void {
  openAttachedPaneImpl?.(record);
}

function workspaceIsReady(ws: MountedWorkspace): boolean {
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

function seedMountedMap(
  records: readonly WorkspaceRecord[],
): Map<string, MountedWorkspace> {
  const next = new Map<string, MountedWorkspace>();
  for (const record of records) {
    next.set(record.id, createMountedWorkspace(record.id));
  }
  return next;
}

export default function App() {
  const workspaceStore = createWorkspaceStore();
  const [mountedById, setMountedById] = createSignal<Map<string, MountedWorkspace>>(
    seedMountedMap(workspaceStore.workspaces()),
  );

  const [recents, setRecents] = createSignal<string[]>([]);
  const [paletteMode, setPaletteMode] = createSignal<'quick' | 'full' | null>(
    null,
  );
  const [layoutNames, setLayoutNames] = createSignal<string[]>([]);
  const [keymapProfile, setKeymapProfile] = createSignal<KeymapProfile>('vscode');
  const [keymapOverrides, setKeymapOverrides] =
    createSignal<KeyBindingOverrides>({});
  const [prefixActive, setPrefixActive] = createSignal(false);
  const [newWorkspacePickerOpen, setNewWorkspacePickerOpen] = createSignal(false);
  const [focusedPaneId, setFocusedPaneId] = createSignal<string | undefined>();
  const [paneCount, setPaneCount] = createSignal(0);
  // V24-02 (VADE2-02): 8-way portal navigation replaces the binary orgViewOpen
  // toggle. 'grid' is the canvas default so fresh/project-less workspaces boot to
  // the terminal grid (D-02). Canvas-swap (D-01) toggles the grid via display:none.
  const [activeView, setActiveView] = createSignal<PortalView>('grid');
  // V24-04 (VADE2-04): global "Ask Voss to…" composer open state (⌘K + rail
  // ask trigger). currentTaskMode feeds the TopChrome safety-mode chip — set to
  // the most-recently-created Task's RunMode, mapped back to its humane label.
  const [composerOpen, setComposerOpen] = createSignal(false);
  const [currentTaskMode, setCurrentTaskMode] = createSignal<RunMode | undefined>(
    undefined,
  );
  const RUNMODE_TO_SAFETY: Record<RunMode, 'Read only' | 'Can edit' | 'Autopilot'> = {
    Plan: 'Read only',
    Edit: 'Can edit',
    Auto: 'Autopilot',
  };
  const currentSafetyMode = () => {
    const m = currentTaskMode();
    return m ? RUNMODE_TO_SAFETY[m] : undefined;
  };
  // VCKP-04 AttentionQueue (D-05/D-06). Open/close state lives here (mirrors
  // orgViewOpen/contextPanelOpen) and flows to StatusBar + AttentionPanel props.
  const [attentionOpen, setAttentionOpen] = createSignal(false);
  const attentionBlocking = createMemo(() =>
    attentionQueue().some((i) => i.kind === 'permission' || i.kind === 'signoff'),
  );
  const [contextPanelOpen, setContextPanelOpen] = createSignal(
    localStorage.getItem('voss:contextPanelOpen') === 'true',
  );
  const toggleContextPanel = () => {
    setContextPanelOpen((prev) => {
      const next = !prev;
      localStorage.setItem('voss:contextPanelOpen', String(next));
      return next;
    });
  };
  const [sidebarCollapsed, setSidebarCollapsed] = createSignal(
    localStorage.getItem('voss:sidebarCollapsed') === 'true',
  );
  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('voss:sidebarCollapsed', String(next));
      return next;
    });
  };
  const [portalExpanded, setPortalExpanded] = createSignal(
    localStorage.getItem('voss:portalExpanded') === 'true',
  );
  const togglePortalExpanded = () => {
    setPortalExpanded((prev) => {
      const next = !prev;
      localStorage.setItem('voss:portalExpanded', String(next));
      return next;
    });
  };
  const [agentModalOpen, setAgentModalOpen] = createSignal(false);
  const [contextMenuState, setContextMenuState] = createSignal<{
    paneId: string;
    anchor: HTMLElement;
    costUsd: number;
  } | null>(null);

  // V14-08 Task 1 — real agent spawn via Bridge B. Must be fully SYNCHRONOUS:
  // the new PaneComponent's onMount (queued createEffect) flushes only after
  // this handler returns, and reads props.agentConfig live. Setting the
  // per-workspace agentConfigByPaneId map BEFORE returning guarantees doSpawn
  // takes the spawnAgent branch — no plain-shell race. NO await anywhere.
  const handleLaunchAgent = (config: {
    cliBinary: string;
    cliArgs: string[];
    taskPrompt: string;
    placement?: 'right' | 'below' | 'newtab';
    managed?: boolean;
    tier?: 'A' | 'B' | 'C';
    kind?: 'agent' | 'terminal';
    scope?: string;
    budgetUsd?: number;
  }) => {
    setAgentModalOpen(false);
    const ws = activeMounted();
    if (!ws) return;
    const ctrl = ws.gridController;
    if (!ctrl) return;

    // GRD-05 guard: insertSibling silently no-ops on a min-size violation,
    // leaving store.focusedId unchanged. Compare before/after so we don't
    // overwrite the existing focused pane's config or spawn into it.
    // NOTE: `placement` is carried in the config but not yet honored — App
    // always splits horizontally; honoring right/below/newtab is a follow-up.
    const before = ctrl.snapshot().focusedId;
    ctrl.splitFocused('H');
    const newId = ctrl.snapshot().focusedId;
    if (newId === before) return; // split rejected — abort agent wiring.

    // Terminal preset: plain shell. Leave agentConfigByPaneId unset so
    // PaneComponent.doSpawn takes the plain transport.spawn() branch. The split
    // already happened above (new focused pane), so the shell lands there.
    if (config.kind === 'terminal') return;

    // Bridge B: mint the cardId and carry it as sessionId for correlation. The
    // task prompt is already encoded into config.cliArgs by buildConfig — do
    // NOT re-append it.
    const cardId = registerTerminalCard(newId);

    // VCKP-13: a managed launch needs a sandbox scope; default to the
    // workspace root. With no resolvable scope the sandbox cannot be built —
    // fall back to an UNMANAGED spawn so the recorded tier stays honest.
    const scope = config.scope ?? workspacePath() ?? undefined;
    const managed = config.managed === true && !!scope;

    // The recorded tier reflects the command actually invoked (resolveTier),
    // NEVER the modal's static value: managed → A/B, unmanaged → C.
    const tier = resolveTier({
      cli: config.cliBinary,
      managed,
      hookCapable: hookCapableCli(config.cliBinary),
      adopted: false,
    });

    const cfg: AgentConfig = {
      cliBinary: config.cliBinary,
      cliArgs: config.cliArgs,
      sessionId: cardId,
      managed,
      tier,
      ...(managed ? { scope } : {}),
      ...(config.budgetUsd != null ? { budgetUsd: config.budgetUsd } : {}),
    };
    ws.setAgentConfigByPaneId({ ...ws.agentConfigByPaneId(), [newId]: cfg });
  };

  // V14-12 gap-fix (D-03): the RunCommandBar terminal launch in Live Work
  // splits a REAL grid pane and routes through the per-pane agentConfig map
  // (PaneComponent spawns it), instead of the bar's default direct
  // spawn_agent invoke — which would create a PTY bound to no visible pane.
  const runBarResolvePaneId = (): string => {
    const ws = activeMounted();
    const ctrl = ws?.gridController;
    if (!ws || !ctrl) return crypto.randomUUID();
    const before = ctrl.snapshot().focusedId;
    ctrl.splitFocused('H');
    const newId = ctrl.snapshot().focusedId;
    return newId === before ? crypto.randomUUID() : newId;
  };
  const runBarSpawnAgent: SpawnAgentFn = async (o) => {
    const ws = activeMounted();
    if (!ws) return;
    const cfg: AgentConfig = {
      cliBinary: o.cliBinary,
      cliArgs: o.cliArgs,
      sessionId: o.sessionId, // bar-minted cardId (Bridge B)
      managed: false,
      tier: 'C', // unmanaged spawn — observe-only (resolveTier rule)
    };
    ws.setAgentConfigByPaneId({ ...ws.agentConfigByPaneId(), [o.paneId]: cfg });
  };

  // V15-02 (VLIVE-02/03): lazy per-workspace voss client. The first native
  // start spawns the sidecar (Plan 01 — reuse-if-alive per cwd) and builds the
  // V13.1 client; the token lives only in this non-exported signal (T-V15-10).
  const [vossClient, setVossClient] = createSignal<BuiltVossClient | null>(
    null,
  );
  let vossClientCwd: string | null = null;
  const ensureVossClient = async (cwd: string): Promise<BuiltVossClient> => {
    const existing = vossClient();
    if (existing && vossClientCwd === cwd) return existing;
    devlog('info', 'sidecar.serve', 'start_voss_serve', { cwd });
    let handle;
    try {
      handle = await startVossServe(cwd);
    } catch (e) {
      devlog('error', 'sidecar.serve', 'start_voss_serve failed', e);
      throw e;
    }
    devlog('info', 'sidecar.serve', 'sidecar ready');
    const built = buildVossClientFromHandle(handle);
    vossClientCwd = cwd;
    setVossClient(built);
    // Expose the live server to prop-less surfaces (swarm snapshot fetch +
    // command-bar directing) — token rides the Authorization header only.
    setLiveServer({
      sidecarId: built.sidecarId,
      cwd,
      followUpClient: built.followUpClient,
    });
    return built;
  };

  // V15-03 (D-01/D-02/D-03): open a structured pane for a native session —
  // flip Run Review → Live Work, place the run, and bind the pane id to the
  // session record (SplitNode renders ProtocolPane for a bound leaf).
  //
  // Placement (user pref): reuse the LEFTMOST clean/idle terminal pane rather
  // than splitting the focused pane (which dropped the run in the middle). A
  // pane is reusable when it is NOT already a run, NOT an agent (spawned,
  // latched, or detected-by-proc), and its foreground process is empty or a
  // plain shell. If none is reusable, grow a fresh pane from the LEFT by
  // splitting the leftmost leaf.
  // Also the attach seam Plans 04/05 consume (openAttachedPane export).
  const bindNativePane = (
    ws: MountedWorkspace,
    paneId: string,
    record: NativeSessionRecord,
  ): void => {
    ws.setNativeSessionByPaneId({
      ...ws.nativeSessionByPaneId(),
      [paneId]: record,
    });
    // Real pane close (⌘W / reap / workspace teardown) tears the protocol
    // session down with it: drop the pane binding and — refcounted, another
    // attached pane may share the server session — abort the stream + state.
    registerPaneDestroyHook(paneId, () => {
      const map = { ...ws.nativeSessionByPaneId() };
      delete map[paneId];
      ws.setNativeSessionByPaneId(map);
      const stillBound = Object.values(map).some(
        (r) => r.sessionId === record.sessionId,
      );
      if (!stillBound) destroyProtocolSession(record.sessionId);
    });
  };
  const openNativePane = (record: NativeSessionRecord): void => {
    const ws = activeMounted();
    const ctrl = ws?.gridController;
    if (!ws || !ctrl) return;
    setActiveView('grid'); // D-01: native work lives in the Live Work grid

    const leaves = collectLeaves(ctrl.snapshot().root); // left→right (inorder)
    const nativeMap = ws.nativeSessionByPaneId();
    const agentCfgs = ws.agentConfigByPaneId();
    const latched = agentPaneById();
    const procs = procByPaneId();
    const reusable = leaves.find(
      (l) =>
        !nativeMap[l.id] &&
        !agentCfgs[l.id] &&
        !latched[l.id] &&
        isIdleShellProc(procs[l.id]),
    );

    devlog('info', 'run.pane', 'placement', {
      leaves: leaves.map((l) => ({ id: l.id.slice(0, 6), proc: procs[l.id] ?? null })),
      reusableId: reusable?.id?.slice(0, 6) ?? null,
    });

    if (reusable) {
      // Take over the clean pane in place — no split.
      bindNativePane(ws, reusable.id, record);
      ctrl.focusPaneById(reusable.id);
      devlog('info', 'run.pane', 'reused pane', { paneId: reusable.id.slice(0, 6) });
      return;
    }

    // No clean pane — grow from the left: split the leftmost leaf.
    ctrl.focusPaneById(leaves[0].id);
    const before = ctrl.snapshot().focusedId;
    ctrl.splitFocused('H');
    const newId = ctrl.snapshot().focusedId;
    if (newId === before) {
      devlog('warn', 'run.pane', 'split rejected (pane cap?)');
      return; // split rejected (e.g. pane cap)
    }
    bindNativePane(ws, newId, record);
    devlog('info', 'run.pane', 'split new pane', { paneId: newId.slice(0, 6) });
  };
  openAttachedPaneImpl = openNativePane;
  onCleanup(() => {
    if (openAttachedPaneImpl === openNativePane) openAttachedPaneImpl = null;
  });

  // RunCommandBar native seam: lazily ensure the client, create the real
  // session, then subscribe it live (AttentionQueue + overlay + liveLabel)
  // and auto-open its structured pane (D-03: one pane per native run).
  // Bridge A: the create-response session id IS the cardId. If startVossServe
  // throws, this rejects and the bar surfaces it via its block-reason path
  // (T-V15-04 — the gates stay; this only satisfies them).
  const runBarNativeClient: RunNativeClient = {
    createSession: async (spec) => {
      const cwd = workspacePath() ?? '';
      devlog('info', 'run.native', 'createSession begin', { cwd });
      const built = await ensureVossClient(cwd);
      let r: { id: string };
      try {
        devlog('info', 'run.native', 'create session');
        r = await built.runNativeClient.createSession(spec);
      } catch (e) {
        // Rust owns the loopback credential and maps proxy failures back here.
        devlog('error', 'run.native', 'createSession fetch failed', e);
        throw e;
      }
      devlog('info', 'run.native', 'session created', { sessionId: r.id });
      // The ProtocolPane owns the SINGLE live SSE stream (ensureProtocolStream
      // on mount), which feeds both the transcript AND ingest/overlay/graph.
      // The server event queue is single-consumer, so a second stream here
      // would STEAL the pane's turn events — do not open one. Just mount the
      // pane and start the turn.
      openNativePane({
        sessionId: r.id,
        sidecarId: built.sidecarId,
      });
      // createSession only mints an IDLE session — the goal must be POSTed as
      // the first message to actually start a turn (server `_run_turn`). Sent
      // AFTER the stream subscribes above so its events are captured. The
      // server PermissionGate mode is lowercase (Literal["plan","edit","auto"]),
      // so map the humane RunMode ('Plan'/'Edit'/'Auto') down.
      try {
        devlog('info', 'run.native', 'POST first message (start turn)', {
          mode: spec.mode,
        });
        await built.client.postMessage(r.id, spec.goal, spec.mode.toLowerCase());
        devlog('info', 'run.native', 'turn started');
      } catch (e) {
        devlog('error', 'run.native', 'first message failed', e);
        throw e;
      }
      return r;
    },
  };

  // VCKP-12 adopt entry point: "Manage with Voss" on a sidebar agent row.
  const [adoptTarget, setAdoptTarget] = createSignal<{
    paneId: string;
    cliBinary: string;
  } | null>(null);

  // D-07 Open-in-grid host. CardDrawer fires requestOpenInGrid(paneId) from the
  // Review plane; we flip back to the grid (activeView='grid', which swaps the
  // display:none above) and focus the bound pane. Opt-in only — never automatic.
  // Clear the request so it doesn't re-fire on unrelated re-renders.
  // setOpenInGridRequest allows caching of the choice of terminal pane window
  createEffect(() => {
    const paneId = openInGridRequest();
    if (!paneId) return;
    setActiveView('grid');
    gridController()?.focusPaneById(paneId);
    setOpenInGridRequest(null);
  });

  // V14 chunk C — the reverse jump: a pane-header card chip fires
  // requestOpenInReview(cardId); we select the card and flip to Run Review.
  // Opt-in only (chip click), mirroring the D-07 effect above.
  createEffect(() => {
    const cardId = openInReviewRequest();
    if (!cardId) return;
    setSelectedCardId(cardId);
    setActiveView('review');
    setOpenInReviewRequest(null);
  });

  const [recentCommandIds] = createSignal<Set<string>>(new Set());
  let closeSaveUnlisten: (() => void) | undefined;
  let keymapUnlisten: (() => void) | undefined;

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

  const gridController = () => activeMounted()?.gridController;

  const agentListForSidebar = createMemo(() => {
    const ws = activeMounted();
    if (!ws) return [];
    const configs = ws.agentConfigByPaneId();
    const budgets = budgetByPaneId();
    const procs = procByPaneId();
    const seen = new Set<string>();

    const mapRole = (cli: string) =>
      cli === 'claude' ? 'planner'
        : cli === 'codex' ? 'executor'
        : cli === 'gemini' ? 'reviewer'
        : cli === 'aider' ? 'executor'
        : 'user';

    const result: {
      paneId: string; cliBinary: string; model: string; role: string;
      costUsd: number; isStreaming: boolean; tokensUsed: number;
      tokenLimit: number | null; taskPrompt: string;
    }[] = [];

    // Source 1: agents launched via spawn_agent (agentConfigByPaneId)
    for (const [paneId, cfg] of Object.entries(configs)) {
      if (!isKnownAgentCli(cfg.cliBinary)) continue;
      seen.add(paneId);
      const b = budgets[paneId];
      result.push({
        paneId,
        cliBinary: cfg.cliBinary,
        model: ((): string => {
          // Handle both `--model value` (separate elements, as the launch modal
          // emits) and `--model=value` forms.
          const i = cfg.cliArgs.findIndex(
            (a) => a === '--model' || a.startsWith('--model='),
          );
          if (i < 0) return 'default';
          const a = cfg.cliArgs[i];
          return a.includes('=')
            ? a.slice(a.indexOf('=') + 1)
            : (cfg.cliArgs[i + 1] ?? 'default');
        })(),
        role: mapRole(cfg.cliBinary),
        costUsd: b?.cost_usd ?? 0,
        isStreaming: b ? Date.now() - b.lastSeenMs < 3000 : false,
        tokensUsed: b?.tokens_used ?? 0,
        tokenLimit: b?.token_limit ?? null,
        taskPrompt: cfg.cliArgs.find((a) => !a.startsWith('-')) ?? '',
      });
    }

    // Source 2: agents detected from foreground process name (manually typed)
    for (const [paneId, proc] of Object.entries(procs)) {
      if (seen.has(paneId)) continue;
      if (!isKnownAgentCli(proc)) continue;
      seen.add(paneId);
      const b = budgets[paneId];
      result.push({
        paneId,
        cliBinary: proc,
        model: b?.model ?? 'default',
        role: mapRole(proc),
        costUsd: b?.cost_usd ?? 0,
        isStreaming: b ? Date.now() - b.lastSeenMs < 3000 : false,
        tokensUsed: b?.tokens_used ?? 0,
        tokenLimit: b?.token_limit ?? null,
        taskPrompt: '',
      });
    }

    // Source 3: latched agent detection (catches agents whose proc name
    // changed from "claude" to "node" after pgid poll override)
    const latched = agentPaneById();
    for (const [paneId, agent] of Object.entries(latched)) {
      if (seen.has(paneId)) continue;
      const b = budgets[paneId];
      result.push({
        paneId,
        cliBinary: agent.cliBinary,
        model: b?.model ?? 'default',
        role: mapRole(agent.cliBinary),
        costUsd: b?.cost_usd ?? 0,
        isStreaming: b ? Date.now() - b.lastSeenMs < 3000 : false,
        tokensUsed: b?.tokens_used ?? 0,
        tokenLimit: b?.token_limit ?? null,
        taskPrompt: '',
      });
    }

    return result;
  });

  const [activityLog, setActivityLog] = createSignal<
    { id: string; type: 'completion' | 'error'; description: string; timestamp: number }[]
  >([]);

  // Track agent sessions — detect new and removed agents
  let prevAgentPaneIds = new Set<string>();
  createEffect(() => {
    const ws = activeMounted();
    if (!ws) return;
    const configs = ws.agentConfigByPaneId();
    const currentIds = new Set(Object.keys(configs));

    // New agents = in current but not in prev
    for (const id of currentIds) {
      if (!prevAgentPaneIds.has(id)) {
        const cfg = configs[id];
        setActivityLog((prev) => [
          {
            id,
            type: 'completion' as const,
            description: `${cfg.cliBinary} started`,
            timestamp: Date.now(),
          },
          ...prev,
        ]);
      }
    }

    // Stopped agents = in prev but not in current
    for (const id of prevAgentPaneIds) {
      if (!currentIds.has(id)) {
        setActivityLog((prev) => [
          {
            id: `${id}-stop`,
            type: 'completion' as const,
            description: `agent stopped`,
            timestamp: Date.now(),
          },
          ...prev,
        ]);
      }
    }

    prevAgentPaneIds = currentIds;
  });

  // V14 chunk C — honest run-budget denominator for the StatusBar mini-bar:
  // the sum of per-agent budgetUsd limits (launch configs + adopted agents).
  // `spent` counts ONLY panes that carry a limit so the fraction compares like
  // with like. No limits set anywhere → limit 0 → StatusBar keeps the plain
  // mono cost text and renders NO percentage bar (nothing faked).
  const runBudgetTotals = createMemo(() => {
    const configs = activeMounted()?.agentConfigByPaneId() ?? {};
    const adoptions = adoptionByPaneId();
    const budgets = budgetByPaneId();
    let limit = 0;
    let spent = 0;
    const counted = new Set<string>();
    for (const [paneId, cfg] of Object.entries(configs)) {
      if (cfg.budgetUsd == null || cfg.budgetUsd <= 0) continue;
      counted.add(paneId);
      limit += cfg.budgetUsd;
      spent += budgets[paneId]?.cost_usd ?? 0;
    }
    for (const [paneId, entry] of Object.entries(adoptions)) {
      if (counted.has(paneId) || entry.budgetUsd <= 0) continue;
      limit += entry.budgetUsd;
      spent += budgets[paneId]?.cost_usd ?? 0;
    }
    return { limit, spent };
  });

  const usageEntries = createMemo(() => {
    const budgets = budgetByPaneId();
    const ws = activeMounted();
    if (!ws) return [];
    const configs = ws.agentConfigByPaneId();
    return Object.entries(budgets)
      .filter(([paneId]) => configs[paneId] && isKnownAgentCli(configs[paneId].cliBinary))
      .map(([paneId, b]) => ({
        name: configs[paneId].cliBinary.charAt(0).toUpperCase() + configs[paneId].cliBinary.slice(1),
        tokensUsed: b.tokens_used,
      }));
  });

  // --- Command registry (D-01) -----------------------------------------------
  const baseCommands = [
    ...v0Commands(),
    ...workspaceCommands(),
    ...appearanceCommands(),
  ];
  const registry = createMemo(() =>
    createCommandRegistry(baseCommands, keymapOverrides()),
  );
  const knownCommandIds = () => baseCommands.map((cmd) => cmd.id);
  const knownChords = () =>
    baseCommands.flatMap((cmd) => [
      ...(cmd.keybinding ? [cmd.keybinding] : []),
      ...(cmd.aliases ?? []),
    ]);

  const onLayoutSelect = (preset: LayoutPreset) => {
    // Read controller directly from the mounted workspace to avoid
    // stale memo / optional-chaining swallowing undefined silently.
    const id = activeId();
    const ws = id ? mountedById().get(id) : undefined;
    const ctrl = ws?.gridController;
    console.log('[voss-app] onLayoutSelect called', {
      preset,
      activeId: id,
      hasMounted: !!ws,
      hasCtrl: !!ctrl,
      mountedKeys: [...mountedById().keys()],
    });
    if (!ctrl) {
      console.warn(
        '[voss-app] onLayoutSelect: gridController unavailable',
        { activeId: id, hasMounted: !!ws, hasCtrl: !!ctrl },
      );
      return;
    }
    ctrl.applyPreset(preset);
  };

  const showGrid = () => {
    const ws = activeMounted();
    return ws != null && workspaceIsReady(ws);
  };

  const workspacePath = () => {
    const ws = activeMounted();
    return ws?.project()?.path ?? ws?.projectLessCwd();
  };

  const saveCurrentLayout = async (
    path: string,
    name: string,
  ): Promise<void> => {
    const ctrl = gridController();
    const ws = activeMounted();
    if (!ctrl || !ws) return;
    const snap = ctrl.snapshot();
    const file = serializeLayout(snap.root, snap.focusedId, ws.activeLayout());
    await saveLayout(path, name, file);
  };

  const loadLayoutByName = async (
    path: string,
    name: string,
  ): Promise<void> => {
    const ctrl = gridController();
    if (!ctrl) return;
    const file = await loadLayout(path, name);
    ctrl.applyLoadedLayout(file);
  };

  const restoreWorkspaceFromRecord = async (
    ws: MountedWorkspace,
    record: WorkspaceRecord,
  ): Promise<void> => {
    if (record.projectPath) {
      try {
        const info = await openProject(record.projectPath);
        const agentConfigs = await fetchAgentConfigs(info.path);
        let session: SessionFile | null = null;
        session = await loadSession(info.path).catch(() => null);
        if (!session) {
          const layout = await loadDefaultLayout(info.path).catch(() => null);
          if (layout) {
            session = layoutToSession(layout, false);
          }
        }
        batch(() => {
          ws.setAgentConfigByPaneId(agentConfigs);
          ws.setInitialSession(session);
          ws.setProject(info);
          ws.setProjectLessAccepted(true);
          ws.setEverMounted(true);
        });
        workspaceStore.setProjectPath(record.id, info.path);
        void installWorkspaceKeymap(info.path);
      } catch (e) {
        console.error('restore workspace project failed:', e);
      }
      return;
    }

    let session: SessionFile | null = await loadProjectLessSession(
      record.id,
    ).catch(() => null);

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

      let session: SessionFile | null = await loadSession(info.path).catch(
        () => null,
      );
      if (!session && layoutName) {
        const layout = await loadLayout(info.path, layoutName).catch(() => null);
        if (layout) {
          session = layoutToSession(layout, false);
        }
      }
      if (!session) {
        const layout = await loadDefaultLayout(info.path).catch(() => null);
        if (layout) {
          session = layoutToSession(layout, false);
        }
      }

      batch(() => {
        ws.setAgentConfigByPaneId(agentConfigs);
        ws.setInitialSession(session);
        ws.setProject(info);
        ws.setProjectLessAccepted(true);
        ws.setEverMounted(true);
      });
      workspaceStore.setProjectPath(workspaceId, info.path);
      void installWorkspaceKeymap(info.path);
      void defaultCwd(info.path)
        .then(ws.setProjectLessCwd)
        .catch(() => ws.setProjectLessCwd(undefined));
    } catch (e) {
      console.error('bootstrap workspace project failed:', e);
    }
  };

  const openSelectedProject = async (
    path: string,
    errorPrefix: string,
  ): Promise<void> => {
    const ws = activeMounted();
    if (!ws) return;
    try {
      const info = await openProject(path);
      setRecents(await listRecents());

      let session: SessionFile | null = null;
      session = await loadSession(info.path).catch(() => null);
      if (!session) {
        const layout = await loadDefaultLayout(info.path).catch(() => null);
        if (layout) {
          session = layoutToSession(layout, false);
        }
      }

      const agentConfigs = !ws.everMounted()
        ? await fetchAgentConfigs(info.path)
        : {};

      batch(() => {
        if (!ws.everMounted()) {
          ws.setAgentConfigByPaneId(agentConfigs);
          ws.setInitialSession(session);
        }
        ws.setProject(info);
        ws.setProjectLessAccepted(true);
        ws.setEverMounted(true);
      });
      workspaceStore.setProjectPath(ws.id, info.path);
      void installWorkspaceKeymap(info.path);
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

  const handleNewWorkspace = () => {
    setNewWorkspacePickerOpen(true);
  };

  const handleCreateWorkspace = async (
    payload: NewWorkspacePickerCreatePayload,
  ) => {
    setNewWorkspacePickerOpen(false);
    const record = workspaceStore.add({
      name: payload.name,
      projectPath: payload.folderPath,
      accentColor: payload.accentColor,
    });
    const ws = ensureMountedRecord(record.id);
    if (payload.folderPath) {
      await bootstrapWorkspaceProject(
        ws,
        record.id,
        payload.folderPath,
        payload.layoutName,
      );
    }
    void workspaceStore.persist();
  };

  const handleStartEmptyWorkspace = async (
    payload: NewWorkspacePickerStartEmptyPayload,
  ) => {
    setNewWorkspacePickerOpen(false);
    const record = workspaceStore.add({
      name: payload.name,
      accentColor: payload.accentColor,
    });
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
    if (ws) {
      ws.gridController = undefined;
    }
    setMountedById((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
    workspaceStore.remove(id);
    void workspaceStore.persist();
  };

  const handleCloseBlocked = () => {
    showToast('info', COPY_LAST_WORKSPACE_BLOCKED);
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
      handleCloseBlocked();
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
    const tab = document.querySelector(
      `[data-workspace-tab="${id}"]`,
    ) as HTMLElement | null;
    tab?.dispatchEvent(
      new MouseEvent('contextmenu', { bubbles: true, cancelable: true }),
    );
  };

  const handleWorkspaceShortcut = (
    action: NonNullable<ReturnType<typeof parseWorkspaceShortcut>>,
  ) => {
    if (action === 'next') {
      handleNextWorkspace();
      return;
    }
    if (action === 'prev') {
      handlePrevWorkspace();
      return;
    }
    const index = workspaceIndexForFocusAction(action);
    if (index != null) handleFocusWorkspaceByIndex(index);
  };

  const openPalette = (mode: 'quick' | 'full') => {
    setPaletteMode(mode);
    const path = workspacePath();
    if (mode === 'quick' && path) {
      void listLayouts(path)
        .then(setLayoutNames)
        .catch(() => setLayoutNames([]));
    }
  };

  const dismissPalette = () => setPaletteMode(null);

  const quickItems = () =>
    buildQuickOpenItems(layoutNames(), recents());

  const handlePaletteExecute = (id: string) => {
    if (id.startsWith('layout:')) {
      const name = id.slice('layout:'.length);
      const path = workspacePath();
      const ctrl = gridController();
      if (path && ctrl) {
        void loadLayoutByName(path, name);
      }
    } else if (id.startsWith('recent:')) {
      const path = id.slice('recent:'.length);
      void openSelectedProject(path, 'palette open_recent failed:');
    } else {
      dispatchCommandId(id);
    }
  };

  const applyKeymapUpdate = (payload: KeymapUpdatePayload) => {
    setKeymapOverrides(payload.valid);
    for (const issue of payload.issues) {
      showToast('warning', `${issue.commandId}: ${issue.reason}`);
    }
  };

  const installWorkspaceKeymap = async (path: string) => {
    keymapUnlisten?.();
    keymapUnlisten = undefined;
    try {
      keymapUnlisten = await watchWorkspaceKeymap(
        path,
        knownCommandIds(),
        knownChords(),
        applyKeymapUpdate,
      );
    } catch (e) {
      console.error('watch_keymap_overrides failed:', e);
      setKeymapOverrides({});
      showToast('error', 'could not load keymap settings');
    }
  };

  const appCtx: AppContext = {
    splitFocused: (orientation) => gridController()?.splitFocused(orientation),
    closeFocused: () => gridController()?.closeFocused(),
    equalizePanes: () => gridController()?.equalizePanes(),
    cycleLayout: () => gridController()?.cycleLayout(),
    focusNext: () => gridController()?.focusNext(),
    focusPrev: () => gridController()?.focusPrev(),
    focusIndex: (n) => gridController()?.focusIndex(n),
    focusDirection: (dir) => gridController()?.focusDirection(dir),
    resizeDirection: (dir) => gridController()?.resizeDirection(dir),
    openQuickPalette: () => openPalette('quick'),
    openFullPalette: () => openPalette('full'),
    openProject: () => void handleOpenFolder(),
    saveLayout: () => {
      const path = workspacePath();
      if (!path) return;
      const name = window.prompt('Save layout as');
      const trimmed = name?.trim();
      if (!trimmed) return;
      void saveCurrentLayout(path, trimmed)
        .then(() => listLayouts(path))
        .then(setLayoutNames)
        .catch((e) => console.error('save_layout failed:', e));
    },
    loadLayout: () => {
      openPalette('quick');
    },
    switchProfile: () => {
      const next: KeymapProfile =
        keymapProfile() === 'tmux' ? 'vscode' : 'tmux';
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
    showKeybindings: () => {
      openPalette('full');
    },
    newWorkspace: () => handleNewWorkspace(),
    closeWorkspace: () => handleCloseActiveWorkspace(),
    nextWorkspace: () => handleNextWorkspace(),
    prevWorkspace: () => handlePrevWorkspace(),
    focusWorkspace: (index) => handleFocusWorkspaceByIndex(index),
    renameWorkspace: () => handleRenameActiveWorkspace(),
    colorWorkspace: () => handleColorActiveWorkspace(),
    switchTheme: () => openPalette('full'),
    switchFont: () => openPalette('full'),
    toggleHighContrast: () => openPalette('full'),
    setBellBehavior: () => openPalette('full'),
    toggleSidebar,
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
    dispatch: (commandId) => {
      void dispatchCommandId(commandId);
    },
    setTimeout: (fn, ms) => window.setTimeout(fn, ms),
    clearTimeout: (id) => window.clearTimeout(id),
  });

  const onAppKey = (e: KeyboardEvent) => {
    if (newWorkspacePickerOpen()) {
      if (e.key === 'Escape') return;
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    if (paletteMode() !== null) {
      if (e.metaKey) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
      return;
    }

    const workspaceAction = parseWorkspaceShortcut(e);
    if (workspaceAction) {
      handleWorkspaceShortcut(workspaceAction);
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    const chord = normalizeChord(e);

    if (prefixMode.isActive()) {
      const prefixKey = normalizePrefixKey(e);
      if (prefixKey) {
        const result = prefixMode.handleKey(prefixKey);
        if (result.action !== 'passthrough') {
          e.preventDefault();
          e.stopImmediatePropagation();
        }
        return;
      }
      if (chord === 'Cmd+B') {
        e.preventDefault();
        e.stopImmediatePropagation();
        prefixMode.tryEnter(keymapProfile());
        return;
      }
    }

    if (chord === 'Cmd+B' && prefixMode.tryEnter(keymapProfile())) {
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    // Cmd+Shift+B: toggle sidebar
    if (e.metaKey && e.shiftKey && (e.key === 'b' || e.key === 'B')) {
      toggleSidebar();
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    // Cmd+Shift+O: toggle the grid ↔ Review surface (grid stays mounted via display:none)
    if (e.metaKey && e.shiftKey && (e.key === 'o' || e.key === 'O')) {
      setActiveView((p) => (p === 'grid' ? 'review' : 'grid'));
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    // Cmd+K: toggle the global "Ask Voss to…" composer (V24-04). metaKey only,
    // no shift/alt — distinct from the ⌘1-9 pane shortcuts and ⌘⇧/⌘⌥ chords.
    if (e.metaKey && !e.shiftKey && !e.altKey && (e.key === 'k' || e.key === 'K')) {
      setComposerOpen((open) => !open);
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    // Cmd+Alt+1..8: jump to a portal surface (UI-SPEC §Canvas-Swap keyboard).
    // metaKey+altKey avoids clobbering ⌘1-9 pane focus (metaKey only).
    if (e.metaKey && e.altKey && !e.shiftKey && e.key >= '1' && e.key <= '8') {
      const idx = Number(e.key) - 1;
      const item = PORTAL_ITEMS[idx];
      if (item) {
        setActiveView(item.id);
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
    }

    // F4: toggle context panel (D-01, D-06 persisted)
    if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
      toggleContextPanel();
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }

    if (chord && registry().dispatch(chord, appCtx)) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  };

  const allSessionContexts = (): WorkspaceSessionContext[] =>
    [...mountedById().values()].map(sessionContextFor);

  onMount(() => {
    window.addEventListener('keydown', onAppKey, true);
    // On-demand live-server connect for prop-less surfaces (orchestra Launch):
    // spawn the sidecar for the active workspace folder. No folder → no-op, so
    // the store stays null and the surface keeps its honest "open a workspace"
    // gate. ensureVossClient calls setLiveServer as its side-effect.
    setLiveServerConnector(async () => {
      const cwd = workspacePath();
      if (!cwd) return;
      await ensureVossClient(cwd);
    });
    void applyWindowEffects({ enabled: true });
    void setAsAppMenu(registry(), (id) => {
      void dispatchCommandId(id);
    });
    void loadKeymapProfile()
      .then(setKeymapProfile)
      .catch(() => setKeymapProfile('vscode'));
    // V14-09: hydrate persisted per-CLI default models so AgentLaunchModal
    // pre-fills the user's last choice (rides the appearance store).
    void loadModelPrefs().catch(() => ({}));
    void listRecents()
      .then(setRecents)
      .catch(() => setRecents([]));

    void (async () => {
      await workspaceStore.load();
      const nextMounted = new Map(mountedById());
      for (const record of workspaceStore.workspaces()) {
        if (!nextMounted.has(record.id)) {
          nextMounted.set(record.id, createMountedWorkspace(record.id));
        }
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
    })();
  });

  onCleanup(() => {
    window.removeEventListener('keydown', onAppKey, true);
    setLiveServerConnector(null);
    keymapUnlisten?.();
    prefixMode.cancel();
    closeSaveUnlisten?.();
    for (const ws of mountedById().values()) {
      ws.sessionCleanup?.();
    }
  });

  const bindController = (ws: MountedWorkspace, c: GridController) => {
    ws.gridController = c;
    ws.sessionCleanup?.();
    ws.sessionCleanup = installWorkspaceStructuralAutosave(sessionContextFor(ws));
    if (!ws.orphanSweepDone) {
      ws.orphanSweepDone = true;
      const session = ws.initialSession();
      if (session) {
        const leafIds = collectLeaves(session.grid.root).map((l) => l.id);
        const wp = ws.project()?.path ?? null;
        void invoke('sweep_orphan_agents', {
          validPaneIds: leafIds,
          workspacePath: wp,
        }).catch((e) =>
          console.error('[voss-app] agent orphan sweep failed:', e),
        );
      }
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        'flex-direction': 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
      }}
    >
      {/* V24-03 (VADE2-03) — quiet chrome: identity + ⌘K + mode chip + live
          chip only. Layout presets moved to <PortalRail>'s layout menu; the
          Live Work / Run Review toggle is now the portal 'review' nav item. */}
      <TopChrome
        projectName={activeMounted()?.project()?.name}
        gitBranch={activeMounted()?.project()?.gitBranch}
        sectionLabel={(
          PORTAL_ITEMS.find((item) => item.id === activeView())?.label ?? 'Workspaces'
        ).toUpperCase()}
        liveState={liveLabel()}
        currentSafetyMode={currentSafetyMode()}
        onOpenComposer={() => setComposerOpen(true)}
      />
      <div
        style={{
          flex: '1',
          'min-height': '0',
          display: 'flex',
          'flex-direction': 'column',
          overflow: 'hidden',
        }}
      >
      <Show
        when={showGrid()}
        fallback={
          <SetupWindow
            recents={recents()}
            onOpenProject={handleOpenFolder}
            onOpenRecent={handleOpenRecent}
            onStartProjectLess={handleStartProjectLess}
          />
        }
      >
        <div
          style={{
            flex: '1',
            'min-height': '0',
            background: 'var(--bg-0)',
            display: 'flex',
            'flex-direction': 'row',
            position: 'relative',
          }}
        >
          <PortalRail
            activeView={activeView()}
            onNavTo={setActiveView}
            expanded={portalExpanded()}
            onToggleExpanded={togglePortalExpanded}
            activeLayout={activeMounted()?.activeLayout() ?? 'custom'}
            onLayoutSelect={onLayoutSelect}
            onOpenComposer={() => setComposerOpen(true)}
          />
          <AgentSidebar
            collapsed={sidebarCollapsed()}
            onToggle={toggleSidebar}
            agents={agentListForSidebar()}
            focusedPaneId={focusedPaneId()}
            onAgentClick={(paneId) => gridController()?.focusPaneById(paneId)}
            onAgentContextMenu={(paneId, e) => {
              e.preventDefault();
              setContextMenuState({
                paneId,
                anchor: e.currentTarget as HTMLElement,
                costUsd: budgetByPaneId()[paneId]?.cost_usd ?? 0,
              });
            }}
            onLaunchAgent={() => setAgentModalOpen(true)}
            activityEvents={activityLog()}
            usageEntries={usageEntries()}
            workspacePath={workspacePath() ?? null}
          />
          {/* Work-surface column: D-03 always-on RunCommandBar strip ABOVE the
              grid/cockpit swap — present in BOTH Live Work and Run Review. */}
          <div style={{ flex: '1', 'min-height': '0', 'min-width': '0', display: 'flex', 'flex-direction': 'column', position: 'relative' }}>
          <RunCommandBar
            cwd={workspacePath() ?? ''}
            cliBinary="voss"
            client={runBarNativeClient}
            resolvePaneId={runBarResolvePaneId}
            spawnAgent={runBarSpawnAgent}
          />
          <WorkspaceTabBar
            class="workspace-tabbar--grid"
            workspaces={workspaceStore.workspaces()}
            activeId={activeId()}
            onActivate={handleActivateWorkspace}
            onNew={handleNewWorkspace}
            onRename={handleRenameWorkspace}
            onColor={handleColorWorkspace}
            onClose={handleCloseWorkspace}
            onReorder={handleReorderWorkspaces}
            closeGuardFor={(id) => workspaceStore.closeGuardFor(id)}
            onCloseBlocked={handleCloseBlocked}
            onCloseConfirm={handleCloseWorkspace}
          />
          <div style={{ flex: '1', 'min-height': '0', 'min-width': '0', display: activeView() === 'grid' ? 'flex' : 'none', 'flex-direction': 'column', position: 'relative' }}>
            {/* V14 chunk C — board summary strip (Live Work only: this
                container is display:none in Run Review, where the cockpit
                shows the full board). Renders nothing until a run snapshot
                is loaded. Chip click = opt-in jump to Run Review. */}
            <BoardSummaryStrip onOpen={() => setActiveView('review')} />
            <For each={workspaceIds()}>
              {(workspaceId) => {
                const ws = () => mountedById().get(workspaceId);
                const shouldMount = () => {
                  const m = ws();
                  return m != null && (m.everMounted() || workspaceIsReady(m));
                };
                return (
                  <Show when={shouldMount()}>
                    <div
                      data-workspace-id={workspaceId}
                      style={{
                        display: activeId() === workspaceId ? 'flex' : 'none',
                        flex: '1',
                        'min-height': '0',
                        'flex-direction': 'column',
                      }}
                    >
                      <GridRoot
                        active={() => activeId() === workspaceId}
                        activeLayout={ws()!.activeLayout}
                        onLayoutChange={(next) => ws()!.setActiveLayout(next)}
                        controllerRef={(c) => bindController(ws()!, c)}
                        projectCwd={
                          ws()!.project()?.path ?? ws()!.projectLessCwd()
                        }
                        initialSession={ws()!.initialSession() ?? undefined}
                        externalKeymap={true}
                        prefixActive={prefixActive()}
                        prefixReserved={keymapProfile() === 'tmux'}
                        agentConfigByPaneId={ws()!.agentConfigByPaneId()}
                        nativeSessionByPaneId={ws()!.nativeSessionByPaneId()}
                        workspacePath={ws()!.project()?.path ?? undefined}
                        onFocusChange={(id) => {
                          if (activeId() === workspaceId) setFocusedPaneId(id);
                        }}
                        onLeafCountChange={(count) => {
                          if (activeId() === workspaceId) setPaneCount(count);
                        }}
                      />
                    </div>
                  </Show>
                );
              }}
            </For>
            {/* F4: Context heatmap side panel (D-01, D-03 overlay) */}
            <ContextPanel
              open={contextPanelOpen()}
              context={(() => {
                const id = focusedPaneId();
                return id ? contextByPaneId()[id] ?? null : null;
              })()}
              isAgentPane={(() => {
                const id = focusedPaneId();
                if (!id) return false;
                const m = activeMounted();
                return m?.agentConfigByPaneId()?.[id] != null;
              })()}
              onTogglePin={(path, pinned) => {
                const id = focusedPaneId();
                const ctx = id ? contextByPaneId()[id] : null;
                if (!ctx) return;
                const currentPinned = ctx.files.filter((f) => f.pinned).map((f) => f.path);
                const next = pinned
                  ? [...new Set([...currentPinned, path])]
                  : currentPinned.filter((p) => p !== path);
                const wp = activeMounted()?.project()?.path;
                if (wp) {
                  void invoke('write_context_pins', {
                    workspacePath: wp,
                    pinnedPaths: next,
                  }).catch((e: unknown) =>
                    console.error('[voss-app] write_context_pins failed:', e),
                  );
                }
              }}
            />
          </div>
          {/* V24-02 (VADE2-02): canvas-swap portal surface — sibling of the grid
              area; the grid stays mounted (display:none above) so PTY panes
              survive the swap (Pitfall 1). 'review' mounts the existing
              OrgViewShell (lazy thunk → only built when active). */}
          <PortalShell
            activeView={activeView()}
            onNavTo={setActiveView}
            projectName={activeMounted()?.project()?.name ?? ''}
            projectPath={activeMounted()?.project()?.path ?? null}
            gitBranch={activeMounted()?.project()?.gitBranch ?? null}
            onNewSession={handleNewWorkspace}
            onNewTask={() => setComposerOpen(true)}
            contextSlot={() => {
              const id = focusedPaneId();
              return (
                <ContextSurface
                  context={id ? contextByPaneId()[id] ?? null : null}
                  isAgentPane={(() => {
                    if (!id) return false;
                    const m = activeMounted();
                    return m?.agentConfigByPaneId()?.[id] != null;
                  })()}
                  onTogglePin={(path, pinned) => {
                    const ctx = id ? contextByPaneId()[id] : null;
                    if (!ctx) return;
                    const currentPinned = ctx.files
                      .filter((f) => f.pinned)
                      .map((f) => f.path);
                    const next = pinned
                      ? [...new Set([...currentPinned, path])]
                      : currentPinned.filter((p) => p !== path);
                    const wp = activeMounted()?.project()?.path;
                    if (wp) {
                      void invoke('write_context_pins', {
                        workspacePath: wp,
                        pinnedPaths: next,
                      }).catch((e: unknown) =>
                        console.error('[voss-app] write_context_pins failed:', e),
                      );
                    }
                  }}
                />
              );
            }}
            memorySlot={() => (
              <MemorySurface
                sidecarId={vossClient()?.sidecarId}
              />
            )}
            reviewSlot={() => (
              <OrgViewShell
                cwd={workspacePath() ?? ''}
                cliBinary="voss"
                onClose={() => setActiveView('grid')}
                followUpClient={vossClient()?.followUpClient}
                vossClient={vossClient()?.client}
                onAttach={(sessionId) =>
                  void attachSession({
                    cwd: workspacePath() ?? '',
                    sessionId,
                    ensureClient: async (cwd) => {
                      const built = await ensureVossClient(cwd);
                      return {
                        sidecarId: built.sidecarId,
                        client: built.client,
                      };
                    },
                    openAttachedPane: (r) =>
                      openNativePane({
                        sessionId: r.sessionId,
                        sidecarId: r.sidecarId,
                      }),
                  })
                }
              />
            )}
          />
          </div>
        </div>
        <StatusBar
          workspaceName={
            workspaceStore.workspaces().find((w) => w.id === activeId())?.name
          }
          paneCount={paneCount()}
          focusedPaneId={focusedPaneId()}
          gitBranch={activeMounted()?.project()?.gitBranch}
          contextPanelOpen={contextPanelOpen()}
          onToggleContextPanel={toggleContextPanel}
          agentCount={agentListForSidebar().length}
          totalCost={Object.values(budgetByPaneId()).reduce((sum, b) => sum + b.cost_usd, 0)}
          budgetSpent={runBudgetTotals().spent}
          budgetLimit={runBudgetTotals().limit}
          onToggleSidebar={toggleSidebar}
          orgViewOpen={activeView() !== 'grid'}
          onToggleOrgView={() => setActiveView((p) => (p === 'grid' ? 'review' : 'grid'))}
          attentionCount={attentionQueue().length}
          attentionBlocking={attentionBlocking()}
          onToggleAttention={() => setAttentionOpen((p) => !p)}
        />
        <AttentionPanel
          open={attentionOpen()}
          onClose={() => setAttentionOpen(false)}
        />
      </Show>
      </div>

      <Show when={newWorkspacePickerOpen()}>
        <NewWorkspacePicker
          onDismiss={() => setNewWorkspacePickerOpen(false)}
          onCreate={handleCreateWorkspace}
          onStartEmpty={handleStartEmptyWorkspace}
        />
      </Show>

      <ToastStack />

      <Show when={agentModalOpen()}>
        <AgentLaunchModal
          onDismiss={() => setAgentModalOpen(false)}
          onLaunch={handleLaunchAgent}
        />
      </Show>

      <Show when={contextMenuState() != null}>
        <AgentContextMenu
          anchor={contextMenuState()!.anchor}
          paneId={contextMenuState()!.paneId}
          costUsd={contextMenuState()!.costUsd}
          onClose={() => setContextMenuState(null)}
          onFocusPane={(id) => gridController()?.focusPaneById(id)}
          onStopAgent={(id) => { void invoke('pty_kill', { sessionId: id }); }}
          onRestartAgent={() => {}}
          onDetachAgent={() => {}}
          onManageAgent={(id) => {
            const cfg = activeMounted()?.agentConfigByPaneId()[id];
            setAdoptTarget({ paneId: id, cliBinary: cfg?.cliBinary ?? '' });
          }}
        />
      </Show>

      {/* VCKP-12: "Let Voss manage this agent" — adopt a running sidebar agent.
          Forward-only, tier C; the adoption registry drives the budget-stop. */}
      <Show when={adoptTarget()}>
        <AdoptAgentModal
          paneId={adoptTarget()!.paneId}
          cliBinary={adoptTarget()!.cliBinary}
          runId={currentRunId() ?? null}
          harnessAdoptAvailable={true}
          onDismiss={() => setAdoptTarget(null)}
          onAdopt={(res) => {
            if (!res.disabled) {
              registerAdoption(res.paneId, {
                cardId: res.cardId,
                budgetUsd: res.budget,
                tier: res.tier,
              });
            }
            setAdoptTarget(null);
          }}
        />
      </Show>

      <Show when={paletteMode() !== null}>
        <CommandPalette
          mode={paletteMode()!}
          commands={registry().all()}
          quickItems={quickItems()}
          recentCommandIds={recentCommandIds()}
          onExecute={handlePaletteExecute}
          onDismiss={dismissPalette}
        />
      </Show>

      {/* V24-04 (VADE2-04) — global "Ask Voss to…" composer (⌘K + rail trigger).
          onCreated records the new Task's mode (TopChrome safety chip) AND
          dispatches the run through the shared RunCommandBar seam. */}
      <VossComposer
        open={composerOpen()}
        onClose={() => setComposerOpen(false)}
        onCreated={async (spec) => {
          setCurrentTaskMode(spec.mode);
          await dispatchRunSpec(spec, {
            cliBinary: 'voss',
            cwd: workspacePath() ?? '',
            client: runBarNativeClient,
            spawnAgent: runBarSpawnAgent,
            resolvePaneId: runBarResolvePaneId,
          });
        }}
      />
    </div>
  );
}
