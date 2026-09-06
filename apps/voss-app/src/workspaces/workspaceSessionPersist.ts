import { invoke } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { subscribeStructuralChange } from '../canvas/sync';
import { buildSessionFile } from '../canvas/session';
import { saveSession } from '../grid/sessionStorage';
import { getScrollbackSnapshot } from '../pane/scrollbackRegistry';
import type { CanvasController } from '../canvas/CanvasRoot';
import type { ActiveLayout } from '../canvas/arrange';
import type { WorkspacesIndex } from './workspaceStorage';
import { saveProjectLessSession } from './workspaceStorage';

/**
 * A8-02 — multi-workspace session lifecycle.
 *
 * One app-level close handler saves every mounted workspace controller,
 * then persists workspaces.json. Per-workspace structural autosave mirrors
 * A6 `sessionPersist.ts` but routes project-less saves to
 * `sessions/<workspaceId>.json`.
 */

export type WorkspaceSessionContext = {
  workspaceId: string;
  getController: () => CanvasController | undefined;
  getActiveLayout: () => ActiveLayout;
  getProjectLessAccepted: () => boolean;
  /** null = project-less session target for this workspace id. */
  projectPath: string | null;
};

const AUTOSAVE_DEBOUNCE_MS = 2000;

async function saveWorkspaceSession(
  ctx: WorkspaceSessionContext,
  scrollbackByPaneId: Map<string, string[]>,
): Promise<void> {
  const controller = ctx.getController();
  if (!controller) return;

  const session = buildSessionFile(
    controller.snapshot(),
    ctx.getActiveLayout(),
    scrollbackByPaneId,
    ctx.getProjectLessAccepted(),
  );

  if (ctx.projectPath) {
    await saveSession(ctx.workspaceId, session);
  } else {
    await saveProjectLessSession(ctx.workspaceId, session);
  }
}

/**
 * Debounced tree-only save for one mounted workspace.
 */
export function installWorkspaceStructuralAutosave(
  ctx: WorkspaceSessionContext,
): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;

  const flush = () => {
    void saveWorkspaceSession(ctx, new Map()).catch((e) => {
      console.error(
        `[voss-app] workspace ${ctx.workspaceId} session autosave failed:`,
        e,
      );
    });
  };

  const unsub = subscribeStructuralChange(() => {
    if (timer != null) clearTimeout(timer);
    timer = setTimeout(flush, AUTOSAVE_DEBOUNCE_MS);
  });

  return () => {
    if (timer != null) clearTimeout(timer);
    unsub();
  };
}

/**
 * Install a single close-request handler that snapshots every workspace,
 * saves each session and the workspace index, then closes with reentry guard.
 */
export async function installAllWorkspacesCloseSave(
  getContexts: () => WorkspaceSessionContext[],
  getIndex: () => WorkspacesIndex,
  saveIndex: (index: WorkspacesIndex) => Promise<void>,
  getWorkspacePath?: () => string | null,
): Promise<() => void> {
  let isClosingAfterSave = false;

  const QUIT_SAVE_TIMEOUT_MS = 5000;

  const unlisten = await getCurrentWindow().onCloseRequested(async (event) => {
    if (isClosingAfterSave) return;
    event.preventDefault();

    try {
      const scrollback = getScrollbackSnapshot(2000);
      const contexts = getContexts();

      await Promise.race([
        (async () => {
          for (const ctx of contexts) {
            await saveWorkspaceSession(ctx, scrollback);
          }
          await saveIndex(getIndex());
          await invoke('update_agents_last_seen', {
            workspacePath: getWorkspacePath?.() ?? null,
          }).catch((e) =>
            console.error('[voss-app] agent registry quit update failed:', e),
          );
        })(),
        new Promise<void>((_, reject) =>
          setTimeout(() => reject(new Error('quit save timed out')), QUIT_SAVE_TIMEOUT_MS),
        ),
      ]);
    } catch (e) {
      console.error(
        '[voss-app] all-workspace quit save failed — closing anyway:',
        e,
      );
    }

    isClosingAfterSave = true;
    await getCurrentWindow().close();
  });

  return unlisten;
}
