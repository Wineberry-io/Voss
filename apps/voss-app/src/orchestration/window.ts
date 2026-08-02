import { invoke } from '@tauri-apps/api/core';

export type OrchestrationView = 'review' | 'swarm-map' | 'memory';

export interface OrchestrationContext {
  cwd: string;
  initialView: OrchestrationView;
  cardId?: string;
}

export function openOrchestrationConsole(
  cwd: string,
  initialView: OrchestrationView = 'review',
  cardId?: string,
): Promise<void> {
  return invoke('open_orchestration_console', {
    cwd,
    initialView,
    cardId,
  });
}

export function getOrchestrationContext(): Promise<OrchestrationContext> {
  return invoke<OrchestrationContext>('get_orchestration_context');
}
