import { invoke } from '@tauri-apps/api/core';
import { For, Show } from 'solid-js';
import CanvasRoot from '../canvas/CanvasRoot';
import AgentContextMenu from '../components/sidebar/AgentContextMenu';
import AgentSidebar from '../components/sidebar/AgentSidebar';
import BoardSummaryStrip from '../components/BoardSummaryStrip';
import ContextPanel from '../components/ContextPanel';
import AdoptAgentModal from '../components/modal/AdoptAgentModal';
import AgentLaunchModal from '../components/modal/AgentLaunchModal';
import SetupWindow from '../components/setup/SetupWindow';
import StatusBar from '../components/StatusBar';
import TopChrome from '../components/titlebar/TopChrome';
import NewWorkspacePicker from '../components/workspace/NewWorkspacePicker';
import WorkspaceTabBar, { COPY_LAST_WORKSPACE_BLOCKED } from '../components/workspace/WorkspaceTabBar';
import '../components/workspace/workspace.css';
import CommandPalette from '../command-palette/CommandPalette';
import ToastStack, { showToast } from '../command-palette/toast';
import VossComposer from '../composer/VossComposer';
import AttentionPanel from '../org/attention/AttentionPanel';
import { attentionQueue } from '../org/attention/attentionQueue';
import { dispatchRunSpec } from '../org/cockpit/RunCommandBar';
import { attachSession } from '../org/cockpit/serverSessions';
import { liveLabel } from '../org/live/sseClient';
import { currentRunId } from '../org/orgStore';
import OrgViewShell from '../org/OrgViewShell';
import { registerAdoption } from '../pane/adoptionRegistry';
import { budgetByPaneId } from '../pane/budgetRegistry';
import { contextByPaneId } from '../pane/contextRegistry';
import PortalRail from '../portal/PortalRail';
import PortalShell from '../portal/PortalShell';
import { PORTAL_ITEMS } from '../portal/portalTypes';
import ContextSurface from '../surfaces/context/ContextSurface';
import MemorySurface from '../surfaces/memory/MemorySurface';
import type { LayoutPreset } from '../grid/layoutPresets';
import type { AgentHost } from './agentHost';
import type { KeymapHost } from './keymapHost';
import type { LiveBoot } from './liveBoot';
import type { ViewRouter } from './viewRouter';
import { workspaceIsReady, type WorkspaceHost } from './workspaceHost';

export interface AppShellProps {
  ws: WorkspaceHost;
  view: ViewRouter;
  live: LiveBoot;
  agents: AgentHost;
  keys: KeymapHost;
}

export default function AppShell(props: AppShellProps) {
  const { ws, view, live, agents, keys } = props;

  const onLayoutSelect = (preset: LayoutPreset) => {
    const ctrl = ws.gridController();
    if (!ctrl) {
      console.warn('[voss-app] onLayoutSelect: controller unavailable');
      return;
    }
    ctrl.applyPreset(preset);
  };

  const togglePin = (paneId: string | undefined, path: string, pinned: boolean) => {
    const ctx = paneId ? contextByPaneId()[paneId] : null;
    if (!ctx) return;
    const currentPinned = ctx.files.filter((f) => f.pinned).map((f) => f.path);
    const next = pinned
      ? [...new Set([...currentPinned, path])]
      : currentPinned.filter((p) => p !== path);
    const wp = ws.activeMounted()?.project()?.path;
    if (wp) {
      void invoke('write_context_pins', { workspacePath: wp, pinnedPaths: next }).catch(
        (e: unknown) => console.error('[voss-app] write_context_pins failed:', e),
      );
    }
  };
  const isAgentPane = (paneId: string | undefined) =>
    !!paneId && ws.activeMounted()?.agentConfigByPaneId()?.[paneId] != null;

  return (
    <div style={{ display: 'flex', 'flex-direction': 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <TopChrome
        projectName={ws.activeMounted()?.project()?.name}
        gitBranch={ws.activeMounted()?.project()?.gitBranch}
        sectionLabel={(
          PORTAL_ITEMS.find((item) => item.id === view.activeView())?.label ?? 'Workspaces'
        ).toUpperCase()}
        liveState={liveLabel()}
        currentSafetyMode={view.currentSafetyMode()}
        onOpenComposer={() => void view.openConsole('review')}
      />
      <div style={{ flex: '1', 'min-height': '0', display: 'flex', 'flex-direction': 'column', overflow: 'hidden' }}>
        <Show
          when={ws.showGrid()}
          fallback={
            <SetupWindow
              recents={ws.recents()}
              onOpenProject={ws.handleOpenFolder}
              onOpenRecent={ws.handleOpenRecent}
              onStartProjectLess={ws.handleStartProjectLess}
            />
          }
        >
          <div style={{ flex: '1', 'min-height': '0', background: 'var(--bg-0)', display: 'flex', 'flex-direction': 'row', position: 'relative' }}>
            <PortalRail
              activeView={view.activeView()}
              onNavTo={view.navigatePortal}
              expanded={view.portalExpanded()}
              onToggleExpanded={view.togglePortalExpanded}
              activeLayout={ws.activeMounted()?.activeLayout() ?? 'custom'}
              onLayoutSelect={onLayoutSelect}
              onOpenComposer={() => void view.openConsole('review')}
            />
            <AgentSidebar
              collapsed={view.sidebarCollapsed()}
              onToggle={view.toggleSidebar}
              agents={agents.agentListForSidebar()}
              focusedPaneId={ws.focusedPaneId()}
              onAgentClick={(paneId) => ws.gridController()?.focusPaneById(paneId)}
              onAgentContextMenu={(paneId, e) => {
                e.preventDefault();
                agents.setContextMenuState({
                  paneId,
                  anchor: e.currentTarget as HTMLElement,
                  costUsd: budgetByPaneId()[paneId]?.cost_usd ?? 0,
                });
              }}
              onLaunchAgent={() => agents.setAgentModalOpen(true)}
              activityEvents={agents.activityLog()}
              usageEntries={agents.usageEntries()}
              workspacePath={ws.workspacePath() ?? null}
            />
            <div style={{ flex: '1', 'min-height': '0', 'min-width': '0', display: 'flex', 'flex-direction': 'column', position: 'relative' }}>
              <WorkspaceTabBar
                class="workspace-tabbar--grid"
                workspaces={ws.workspaceStore.workspaces()}
                activeId={ws.activeId()}
                onActivate={ws.handleActivateWorkspace}
                onNew={ws.handleNewWorkspace}
                onRename={ws.handleRenameWorkspace}
                onColor={ws.handleColorWorkspace}
                onClose={ws.handleCloseWorkspace}
                onReorder={ws.handleReorderWorkspaces}
                closeGuardFor={(id) => ws.workspaceStore.closeGuardFor(id)}
                onCloseBlocked={() => showToast('info', COPY_LAST_WORKSPACE_BLOCKED)}
                onCloseConfirm={ws.handleCloseWorkspace}
              />
              <div style={{ flex: '1', 'min-height': '0', 'min-width': '0', display: view.activeView() === 'grid' ? 'flex' : 'none', 'flex-direction': 'column', position: 'relative' }}>
                <BoardSummaryStrip onOpen={() => void view.openConsole('review')} />
                <For each={ws.workspaceIds()}>
                  {(workspaceId) => {
                    const mounted = () => ws.mountedById().get(workspaceId);
                    const shouldMount = () => {
                      const m = mounted();
                      return m != null && (m.everMounted() || workspaceIsReady(m));
                    };
                    return (
                      <Show when={shouldMount()}>
                        <div
                          data-workspace-id={workspaceId}
                          style={{ display: ws.activeId() === workspaceId ? 'flex' : 'none', flex: '1', 'min-height': '0', 'flex-direction': 'column' }}
                        >
                          <CanvasRoot
                            active={() => ws.activeId() === workspaceId}
                            activeLayout={mounted()!.activeLayout}
                            onLayoutChange={(next) => mounted()!.setActiveLayout(next)}
                            controllerRef={(c) => ws.bindController(mounted()!, c)}
                            projectCwd={mounted()!.project()?.path ?? mounted()!.projectLessCwd()}
                            initialSession={mounted()!.initialSession() ?? undefined}
                            externalKeymap={true}
                            prefixActive={keys.prefixActive()}
                            prefixReserved={keys.keymapProfile() === 'tmux'}
                            agentConfigByPaneId={mounted()!.agentConfigByPaneId()}
                            nativeSessionByPaneId={mounted()!.nativeSessionByPaneId()}
                            workspacePath={mounted()!.project()?.path ?? undefined}
                            onFocusChange={(id) => {
                              if (ws.activeId() === workspaceId) ws.setFocusedPaneId(id);
                            }}
                            onLeafCountChange={(count) => {
                              if (ws.activeId() === workspaceId) ws.setPaneCount(count);
                            }}
                          />
                        </div>
                      </Show>
                    );
                  }}
                </For>
                <ContextPanel
                  open={view.contextPanelOpen()}
                  context={(() => {
                    const id = ws.focusedPaneId();
                    return id ? contextByPaneId()[id] ?? null : null;
                  })()}
                  isAgentPane={isAgentPane(ws.focusedPaneId())}
                  onTogglePin={(path, pinned) => togglePin(ws.focusedPaneId(), path, pinned)}
                />
              </div>
              <PortalShell
                activeView={view.activeView()}
                onNavTo={view.navigatePortal}
                projectName={ws.activeMounted()?.project()?.name ?? ''}
                projectPath={ws.activeMounted()?.project()?.path ?? null}
                gitBranch={ws.activeMounted()?.project()?.gitBranch ?? null}
                onNewSession={ws.handleNewWorkspace}
                onNewTask={() => void view.openConsole('review')}
                contextSlot={() => {
                  const id = ws.focusedPaneId();
                  return (
                    <ContextSurface
                      context={id ? contextByPaneId()[id] ?? null : null}
                      isAgentPane={isAgentPane(id)}
                      onTogglePin={(path, pinned) => togglePin(id, path, pinned)}
                    />
                  );
                }}
                memorySlot={() => <MemorySurface sidecarId={live.vossClient()?.sidecarId} />}
                reviewSlot={() => (
                  <OrgViewShell
                    cwd={ws.workspacePath() ?? ''}
                    cliBinary="voss"
                    onClose={() => view.setActiveView('grid')}
                    followUpClient={live.vossClient()?.followUpClient}
                    vossClient={live.vossClient()?.client}
                    onAttach={(sessionId) =>
                      void attachSession({
                        cwd: ws.workspacePath() ?? '',
                        sessionId,
                        ensureClient: async (cwd) => {
                          const built = await live.ensureVossClient(cwd);
                          return { sidecarId: built.sidecarId, client: built.client };
                        },
                        openAttachedPane: (r) =>
                          live.openNativePane({ sessionId: r.sessionId, sidecarId: r.sidecarId }),
                      })
                    }
                  />
                )}
              />
            </div>
          </div>
          <StatusBar
            workspaceName={ws.workspaceStore.workspaces().find((w) => w.id === ws.activeId())?.name}
            paneCount={ws.paneCount()}
            focusedPaneId={ws.focusedPaneId()}
            gitBranch={ws.activeMounted()?.project()?.gitBranch}
            contextPanelOpen={view.contextPanelOpen()}
            onToggleContextPanel={view.toggleContextPanel}
            agentCount={agents.agentListForSidebar().length}
            totalCost={agents.totalCost()}
            budgetSpent={agents.runBudgetTotals().spent}
            budgetLimit={agents.runBudgetTotals().limit}
            onToggleSidebar={view.toggleSidebar}
            orgViewOpen={view.activeView() !== 'grid'}
            onToggleOrgView={() => void view.openConsole('review')}
            attentionCount={attentionQueue().length}
            attentionBlocking={view.attentionBlocking()}
            onToggleAttention={() => view.setAttentionOpen((p) => !p)}
          />
          <AttentionPanel open={view.attentionOpen()} onClose={() => view.setAttentionOpen(false)} />
        </Show>
      </div>

      <Show when={ws.newWorkspacePickerOpen()}>
        <NewWorkspacePicker
          onDismiss={() => ws.setNewWorkspacePickerOpen(false)}
          onCreate={ws.handleCreateWorkspace}
          onStartEmpty={ws.handleStartEmptyWorkspace}
        />
      </Show>

      <ToastStack />

      <Show when={agents.agentModalOpen()}>
        <AgentLaunchModal onDismiss={() => agents.setAgentModalOpen(false)} onLaunch={agents.handleLaunchAgent} />
      </Show>

      <Show when={agents.contextMenuState() != null}>
        <AgentContextMenu
          anchor={agents.contextMenuState()!.anchor}
          paneId={agents.contextMenuState()!.paneId}
          costUsd={agents.contextMenuState()!.costUsd}
          onClose={() => agents.setContextMenuState(null)}
          onFocusPane={(id) => ws.gridController()?.focusPaneById(id)}
          onStopAgent={(id) => void invoke('pty_kill', { sessionId: id })}
          onRestartAgent={() => {}}
          onDetachAgent={() => {}}
          onManageAgent={(id) => {
            const cfg = ws.activeMounted()?.agentConfigByPaneId()[id];
            agents.setAdoptTarget({ paneId: id, cliBinary: cfg?.cliBinary ?? '' });
          }}
        />
      </Show>

      <Show when={agents.adoptTarget()}>
        <AdoptAgentModal
          paneId={agents.adoptTarget()!.paneId}
          cliBinary={agents.adoptTarget()!.cliBinary}
          runId={currentRunId() ?? null}
          harnessAdoptAvailable={true}
          onDismiss={() => agents.setAdoptTarget(null)}
          onAdopt={(res) => {
            if (!res.disabled) {
              registerAdoption(res.paneId, { cardId: res.cardId, budgetUsd: res.budget, tier: res.tier });
            }
            agents.setAdoptTarget(null);
          }}
        />
      </Show>

      <Show when={keys.paletteMode() !== null}>
        <CommandPalette
          mode={keys.paletteMode()!}
          commands={keys.registry().all()}
          quickItems={keys.quickItems()}
          recentCommandIds={keys.recentCommandIds()}
          onExecute={keys.handlePaletteExecute}
          onDismiss={keys.dismissPalette}
        />
      </Show>

      <VossComposer
        open={view.composerOpen()}
        onClose={() => view.setComposerOpen(false)}
        onCreated={async (spec) => {
          view.setCurrentTaskMode(spec.mode);
          await dispatchRunSpec(spec, {
            cliBinary: 'voss',
            cwd: ws.workspacePath() ?? '',
            client: live.runBarNativeClient,
            spawnAgent: live.runBarSpawnAgent,
            resolvePaneId: live.runBarResolvePaneId,
          });
        }}
      />
    </div>
  );
}
