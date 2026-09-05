import { createEffect, createMemo, createSignal } from 'solid-js';
import { registerTerminalCard } from '../org/model/bridge';
import { hookCapableCli, resolveTier } from '../org/capabilityTier';
import { adoptionByPaneId } from '../pane/adoptionRegistry';
import { isKnownAgentCli } from '../pane/agentDetect';
import { agentPaneById } from '../pane/agentPaneRegistry';
import { budgetByPaneId } from '../pane/budgetRegistry';
import { procByPaneId } from '../pane/procRegistry';
import type { AgentConfig } from '../pane/pty-ipc';
import type { WorkspaceHost } from './workspaceHost';

export interface LaunchAgentConfig {
  cliBinary: string;
  cliArgs: string[];
  taskPrompt: string;
  placement?: 'right' | 'below' | 'newtab';
  managed?: boolean;
  tier?: 'A' | 'B' | 'C';
  kind?: 'agent' | 'terminal';
  scope?: string;
  budgetUsd?: number;
}

export type SidebarAgent = {
  paneId: string;
  cliBinary: string;
  model: string;
  role: string;
  costUsd: number;
  isStreaming: boolean;
  tokensUsed: number;
  tokenLimit: number | null;
  taskPrompt: string;
};

function mapRole(cli: string): string {
  return cli === 'claude'
    ? 'planner'
    : cli === 'codex' || cli === 'aider'
      ? 'executor'
      : cli === 'gemini'
        ? 'reviewer'
        : 'user';
}

function modelFromArgs(cliArgs: string[]): string {
  const i = cliArgs.findIndex((a) => a === '--model' || a.startsWith('--model='));
  if (i < 0) return 'default';
  const a = cliArgs[i];
  return a.includes('=') ? a.slice(a.indexOf('=') + 1) : (cliArgs[i + 1] ?? 'default');
}

export function createAgentHost(ws: WorkspaceHost) {
  const [agentModalOpen, setAgentModalOpen] = createSignal(false);
  const [contextMenuState, setContextMenuState] = createSignal<{
    paneId: string;
    anchor: HTMLElement;
    costUsd: number;
  } | null>(null);
  const [adoptTarget, setAdoptTarget] = createSignal<{ paneId: string; cliBinary: string } | null>(
    null,
  );

  /**
   * Synchronous by design: the new pane's mount reads the config map before
   * this returns, so the map must be set before the split's effects flush.
   */
  const handleLaunchAgent = (config: LaunchAgentConfig) => {
    setAgentModalOpen(false);
    const mounted = ws.activeMounted();
    if (!mounted) return;
    const ctrl = mounted.gridController;
    if (!ctrl) return;
    const before = ctrl.snapshot().focusedId;
    ctrl.splitFocused(config.placement === 'below' ? 'V' : 'H');
    const newId = ctrl.snapshot().focusedId;
    if (newId === before) return;
    if (config.kind === 'terminal') return;

    const cardId = registerTerminalCard(newId);
    const scope = config.scope ?? ws.workspacePath() ?? undefined;
    const managed = config.managed === true && !!scope;
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
    mounted.setAgentConfigByPaneId({ ...mounted.agentConfigByPaneId(), [newId]: cfg });
  };

  const agentListForSidebar = createMemo<SidebarAgent[]>(() => {
    const mounted = ws.activeMounted();
    if (!mounted) return [];
    const configs = mounted.agentConfigByPaneId();
    const budgets = budgetByPaneId();
    const procs = procByPaneId();
    const seen = new Set<string>();
    const result: SidebarAgent[] = [];
    const push = (paneId: string, cliBinary: string, model: string, taskPrompt: string) => {
      const b = budgets[paneId];
      seen.add(paneId);
      result.push({
        paneId,
        cliBinary,
        model,
        role: mapRole(cliBinary),
        costUsd: b?.cost_usd ?? 0,
        isStreaming: b ? Date.now() - b.lastSeenMs < 3000 : false,
        tokensUsed: b?.tokens_used ?? 0,
        tokenLimit: b?.token_limit ?? null,
        taskPrompt,
      });
    };
    for (const [paneId, cfg] of Object.entries(configs)) {
      if (!isKnownAgentCli(cfg.cliBinary)) continue;
      push(paneId, cfg.cliBinary, modelFromArgs(cfg.cliArgs), cfg.cliArgs.find((a) => !a.startsWith('-')) ?? '');
    }
    for (const [paneId, proc] of Object.entries(procs)) {
      if (seen.has(paneId) || !isKnownAgentCli(proc)) continue;
      push(paneId, proc, budgets[paneId]?.model ?? 'default', '');
    }
    for (const [paneId, agent] of Object.entries(agentPaneById())) {
      if (seen.has(paneId)) continue;
      push(paneId, agent.cliBinary, budgets[paneId]?.model ?? 'default', '');
    }
    return result;
  });

  const [activityLog, setActivityLog] = createSignal<
    { id: string; type: 'completion' | 'error'; description: string; timestamp: number }[]
  >([]);
  const prevAgentPaneIdsByWorkspace = new Map<string, Set<string>>();
  createEffect(() => {
    const mounted = ws.activeMounted();
    if (!mounted) return;
    const configs = mounted.agentConfigByPaneId();
    const currentIds = new Set(Object.keys(configs));
    const prevAgentPaneIds = prevAgentPaneIdsByWorkspace.get(mounted.id) ?? new Set<string>();
    for (const id of currentIds) {
      if (!prevAgentPaneIds.has(id)) {
        const cfg = configs[id];
        setActivityLog((prev) => [
          { id, type: 'completion' as const, description: `${cfg.cliBinary} started`, timestamp: Date.now() },
          ...prev,
        ]);
      }
    }
    for (const id of prevAgentPaneIds) {
      if (!currentIds.has(id)) {
        setActivityLog((prev) => [
          { id: `${id}-stop`, type: 'completion' as const, description: 'agent stopped', timestamp: Date.now() },
          ...prev,
        ]);
      }
    }
    prevAgentPaneIdsByWorkspace.set(mounted.id, currentIds);
  });

  const runBudgetTotals = createMemo(() => {
    const configs = ws.activeMounted()?.agentConfigByPaneId() ?? {};
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
    const mounted = ws.activeMounted();
    if (!mounted) return [];
    const configs = mounted.agentConfigByPaneId();
    return Object.entries(budgets)
      .filter(([paneId]) => configs[paneId] && isKnownAgentCli(configs[paneId].cliBinary))
      .map(([paneId, b]) => ({
        name: configs[paneId].cliBinary.charAt(0).toUpperCase() + configs[paneId].cliBinary.slice(1),
        tokensUsed: b.tokens_used,
      }));
  });

  const totalCost = () =>
    Object.values(budgetByPaneId()).reduce((sum, b) => sum + b.cost_usd, 0);

  return {
    agentModalOpen,
    setAgentModalOpen,
    contextMenuState,
    setContextMenuState,
    adoptTarget,
    setAdoptTarget,
    handleLaunchAgent,
    agentListForSidebar,
    activityLog,
    runBudgetTotals,
    usageEntries,
    totalCost,
  };
}

export type AgentHost = ReturnType<typeof createAgentHost>;
