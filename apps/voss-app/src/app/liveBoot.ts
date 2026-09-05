import { createSignal, onCleanup } from 'solid-js';
import { orderedNodes } from '../canvas/model';
import { devlog } from '../devlog';
import type { NativeSessionRecord } from '../grid/SplitNode';
import { setLiveServer, setLiveServerConnector } from '../org/live/liveServer';
import { startVossServe } from '../org/live/sidecarClient';
import { destroyProtocolSession } from '../org/live/protocolSessions';
import {
  buildVossClientFromHandle,
  type BuiltVossClient,
} from '../org/live/vossClientBuild';
import type { RunNativeClient, SpawnAgentFn } from '../org/cockpit/RunCommandBar';
import { agentPaneById } from '../pane/agentPaneRegistry';
import { registerPaneDestroyHook } from '../pane/paneSessionRegistry';
import { procByPaneId } from '../pane/procRegistry';
import type { AgentConfig } from '../pane/pty-ipc';
import { isIdleShellProc, type MountedWorkspace, type WorkspaceHost } from './workspaceHost';

let openAttachedPaneImpl: ((record: NativeSessionRecord) => void) | null = null;

/** Open a structured pane for an existing server session (attach seam). */
export function openAttachedPane(record: NativeSessionRecord): void {
  openAttachedPaneImpl?.(record);
}

export function createLiveBoot(ws: WorkspaceHost, view: { setActiveView: (v: 'grid') => void }) {
  const [vossClient, setVossClient] = createSignal<BuiltVossClient | null>(null);
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
    setLiveServer({ sidecarId: built.sidecarId, cwd, followUpClient: built.followUpClient });
    return built;
  };

  const bindNativePane = (
    mounted: MountedWorkspace,
    paneId: string,
    record: NativeSessionRecord,
  ): void => {
    mounted.setNativeSessionByPaneId({ ...mounted.nativeSessionByPaneId(), [paneId]: record });
    registerPaneDestroyHook(paneId, () => {
      const map = { ...mounted.nativeSessionByPaneId() };
      delete map[paneId];
      mounted.setNativeSessionByPaneId(map);
      const stillBound = Object.values(map).some((r) => r.sessionId === record.sessionId);
      if (!stillBound) destroyProtocolSession(record.sessionId);
    });
  };

  /**
   * Place a native run: reuse the first idle terminal node in reading order,
   * else grow a new node beside the first one.
   */
  const openNativePane = (record: NativeSessionRecord): void => {
    const mounted = ws.activeMounted();
    const ctrl = mounted?.gridController;
    if (!mounted || !ctrl) return;
    view.setActiveView('grid');

    const nodes = orderedNodes(ctrl.snapshot());
    const nativeMap = mounted.nativeSessionByPaneId();
    const agentCfgs = mounted.agentConfigByPaneId();
    const latched = agentPaneById();
    const procs = procByPaneId();
    const reusable = nodes.find(
      (n) => !nativeMap[n.id] && !agentCfgs[n.id] && !latched[n.id] && isIdleShellProc(procs[n.id]),
    );
    devlog('info', 'run.pane', 'placement', {
      nodes: nodes.map((n) => ({ id: n.id.slice(0, 6), proc: procs[n.id] ?? null })),
      reusableId: reusable?.id?.slice(0, 6) ?? null,
    });
    if (reusable) {
      bindNativePane(mounted, reusable.id, record);
      ctrl.focusPaneById(reusable.id);
      devlog('info', 'run.pane', 'reused pane', { paneId: reusable.id.slice(0, 6) });
      return;
    }
    ctrl.focusPaneById(nodes[0]!.id);
    const before = ctrl.snapshot().focusedId;
    ctrl.splitFocused('H');
    const newId = ctrl.snapshot().focusedId;
    if (newId === before) {
      devlog('warn', 'run.pane', 'split rejected');
      return;
    }
    bindNativePane(mounted, newId, record);
    devlog('info', 'run.pane', 'split new pane', { paneId: newId.slice(0, 6) });
  };
  openAttachedPaneImpl = openNativePane;
  onCleanup(() => {
    if (openAttachedPaneImpl === openNativePane) openAttachedPaneImpl = null;
  });

  const runBarNativeClient: RunNativeClient = {
    createSession: async (spec) => {
      const cwd = ws.workspacePath() ?? '';
      devlog('info', 'run.native', 'createSession begin', { cwd });
      const built = await ensureVossClient(cwd);
      let r: { id: string };
      try {
        devlog('info', 'run.native', 'create session');
        r = await built.runNativeClient.createSession(spec);
      } catch (e) {
        devlog('error', 'run.native', 'createSession fetch failed', e);
        throw e;
      }
      devlog('info', 'run.native', 'session created', { sessionId: r.id });
      openNativePane({ sessionId: r.id, sidecarId: built.sidecarId });
      try {
        devlog('info', 'run.native', 'POST first message (start turn)', { mode: spec.mode });
        await built.client.postMessage(r.id, spec.goal, spec.mode.toLowerCase());
        devlog('info', 'run.native', 'turn started');
      } catch (e) {
        devlog('error', 'run.native', 'first message failed', e);
        throw e;
      }
      return r;
    },
  };

  const runBarResolvePaneId = (): string => {
    const mounted = ws.activeMounted();
    const ctrl = mounted?.gridController;
    if (!mounted || !ctrl) throw new Error('No workspace is open to place the run in.');
    const before = ctrl.snapshot().focusedId;
    ctrl.splitFocused('H');
    const newId = ctrl.snapshot().focusedId;
    if (newId === before) throw new Error('Could not open a pane for the run.');
    return newId;
  };

  const runBarSpawnAgent: SpawnAgentFn = async (o) => {
    const mounted = ws.activeMounted();
    if (!mounted) return;
    const cfg: AgentConfig = {
      cliBinary: o.cliBinary,
      cliArgs: o.cliArgs,
      sessionId: o.sessionId,
      managed: false,
      tier: 'C',
    };
    mounted.setAgentConfigByPaneId({ ...mounted.agentConfigByPaneId(), [o.paneId]: cfg });
  };

  const install = () => {
    setLiveServerConnector(async () => {
      const cwd = ws.workspacePath();
      if (!cwd) return;
      await ensureVossClient(cwd);
    });
  };
  const dispose = () => setLiveServerConnector(null);

  return {
    vossClient,
    ensureVossClient,
    openNativePane,
    runBarNativeClient,
    runBarResolvePaneId,
    runBarSpawnAgent,
    install,
    dispose,
  };
}

export type LiveBoot = ReturnType<typeof createLiveBoot>;
