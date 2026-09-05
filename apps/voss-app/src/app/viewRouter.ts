import { createEffect, createMemo, createSignal } from 'solid-js';
import { showToast } from '../command-palette/toast';
import { attentionQueue } from '../org/attention/attentionQueue';
import type { RunMode } from '../org/cockpit/runIntake';
import {
  openInGridRequest,
  openInReviewRequest,
  setOpenInGridRequest,
  setOpenInReviewRequest,
} from '../org/selection';
import { openOrchestrationConsole, type OrchestrationView } from '../orchestration/window';
import type { PortalView } from '../portal/portalTypes';
import type { WorkspaceHost } from './workspaceHost';

const RUNMODE_TO_SAFETY: Record<RunMode, 'Read only' | 'Can edit' | 'Autopilot'> = {
  Plan: 'Read only',
  Edit: 'Can edit',
  Auto: 'Autopilot',
};

function persistedToggle(key: string) {
  const [value, setValue] = createSignal(localStorage.getItem(key) === 'true');
  const toggle = () =>
    setValue((prev) => {
      const next = !prev;
      localStorage.setItem(key, String(next));
      return next;
    });
  return [value, toggle] as const;
}

export function createViewRouter(ws: WorkspaceHost) {
  const [activeView, setActiveView] = createSignal<PortalView>('grid');
  const [composerOpen, setComposerOpen] = createSignal(false);
  const [currentTaskMode, setCurrentTaskMode] = createSignal<RunMode | undefined>(undefined);
  const currentSafetyMode = () => {
    const m = currentTaskMode();
    return m ? RUNMODE_TO_SAFETY[m] : undefined;
  };
  const [attentionOpen, setAttentionOpen] = createSignal(false);
  const attentionBlocking = createMemo(() =>
    attentionQueue().some((i) => i.kind === 'permission' || i.kind === 'signoff'),
  );
  const [contextPanelOpen, toggleContextPanel] = persistedToggle('voss:contextPanelOpen');
  const [sidebarCollapsed, toggleSidebar] = persistedToggle('voss:sidebarCollapsed');
  const [portalExpanded, togglePortalExpanded] = persistedToggle('voss:portalExpanded');

  const openConsole = async (view: OrchestrationView = 'review', cardId?: string) => {
    const cwd = ws.activeMounted()?.project()?.path;
    if (!cwd) {
      showToast('warning', 'Open a project workspace to use Voss orchestration.');
      return;
    }
    try {
      await openOrchestrationConsole(cwd, view, cardId);
    } catch (cause) {
      showToast(
        'error',
        cause instanceof Error ? cause.message : 'Could not open Voss orchestration.',
      );
    }
  };

  const navigatePortal = (view: PortalView): void => {
    if (view === 'review' || view === 'swarm-map' || view === 'memory') {
      void openConsole(view);
      return;
    }
    setActiveView(view);
  };

  createEffect(() => {
    const paneId = openInGridRequest();
    if (!paneId) return;
    setActiveView('grid');
    ws.gridController()?.focusPaneById(paneId);
    setOpenInGridRequest(null);
  });

  createEffect(() => {
    const cardId = openInReviewRequest();
    if (!cardId) return;
    void openConsole('review', cardId);
    setOpenInReviewRequest(null);
  });

  return {
    activeView,
    setActiveView,
    composerOpen,
    setComposerOpen,
    currentTaskMode,
    setCurrentTaskMode,
    currentSafetyMode,
    attentionOpen,
    setAttentionOpen,
    attentionBlocking,
    contextPanelOpen,
    toggleContextPanel,
    sidebarCollapsed,
    toggleSidebar,
    portalExpanded,
    togglePortalExpanded,
    openConsole,
    navigatePortal,
  };
}

export type ViewRouter = ReturnType<typeof createViewRouter>;
