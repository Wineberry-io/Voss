import { getCurrentWindow } from '@tauri-apps/api/window';
import { subscribeStructuralChange } from './sync';
import { buildSessionFile } from './sessionCommands';
import { saveSession, saveGlobalSession } from './sessionStorage';
import { getScrollbackSnapshot } from '../pane/scrollbackRegistry';
import type { TreeNode } from './tree';
import type { ActiveLayout } from './layoutPresets';

/**
 * A6-04 — session lifecycle orchestration.
 *
 * Two install functions:
 * - `installStructuralSessionAutosave`: debounced tree-only save on structural
 *   changes (D-04). No xterm scrollback — just tree/focus/preset/cwd/shell.
 * - `installCloseSessionSave`: quit handler that captures scrollback once,
 *   saves the full session, then allows the window to close (D-05).
 */

/** Callbacks the session lifecycle reads on each save. */
export type SessionContext = {
  workspaceId: string;
  getRoot: () => TreeNode;
  getFocusedId: () => string;
  getActiveLayout: () => ActiveLayout;
  getProjectLessAccepted: () => boolean;
  /** null = global/project-less session target. */
  projectPath: string | null;
};

const AUTOSAVE_DEBOUNCE_MS = 2000;

// --- Structural autosave (D-04/D-06) ----------------------------------------

/**
 * Subscribe to structural changes and debounce a tree-only session save.
 * Returns a cleanup function that clears the timer and unsubscribes.
 */
export function installStructuralSessionAutosave(
  ctx: SessionContext,
): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;

  const flush = () => {
    const session = buildSessionFile(
      ctx.getRoot(),
      ctx.getFocusedId(),
      ctx.getActiveLayout(),
      new Map(), // D-04: no scrollback on structural autosave
      ctx.getProjectLessAccepted(),
    );
    if (ctx.projectPath) {
      void saveSession(ctx.workspaceId, session).catch((e) => {
        console.error('[voss-app] session autosave failed:', e);
      });
    } else {
      void saveGlobalSession(session).catch((e) => {
        console.error('[voss-app] global session autosave failed:', e);
      });
    }
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

// --- Quit full save (D-05) ---------------------------------------------------

/**
 * Install a close-request handler that captures scrollback and saves
 * before allowing the window to close. Returns an unlisten function.
 *
 * Reentry guard (T-A6-06): after a successful save, the handler sets a
 * flag and re-issues `close()`. The second close-request passes through
 * because the flag is set, breaking the infinite loop.
 */
export async function installCloseSessionSave(
  ctx: SessionContext,
): Promise<() => void> {
  let isClosingAfterSave = false;

  const unlisten = await getCurrentWindow().onCloseRequested(async (event) => {
    if (isClosingAfterSave) return; // reentry — let the second close through
    event.preventDefault();

    try {
      const scrollback = getScrollbackSnapshot(2000);
      const session = buildSessionFile(
        ctx.getRoot(),
        ctx.getFocusedId(),
        ctx.getActiveLayout(),
        scrollback,
        ctx.getProjectLessAccepted(),
      );

      if (ctx.projectPath) {
        await saveSession(ctx.workspaceId, session);
      } else {
        await saveGlobalSession(session);
      }

      isClosingAfterSave = true;
      await getCurrentWindow().close();
    } catch (e) {
      console.error('[voss-app] quit save failed — window kept open:', e);
      // Window stays open. User can retry quit or force-kill.
    }
  });

  return unlisten;
}
