/**
 * A7-04 Task 1 — tmux ⌘B prefix state machine (D-10/D-11).
 *
 * Timed 1.5s prefix window. Press ⌘B → enter prefix. Next bare key
 * dispatches mapped command. Timeout / Esc / unknown key cancels.
 * Active only under `tmux` profile. Pure — no DOM or Solid state.
 */

import type { KeymapProfile } from './keymapStorage';

const PREFIX_TIMEOUT_MS = 1500;

/** tmux prefix key → registry command id. */
const PREFIX_MAP: Record<string, string> = {
  '%': 'pane.splitBelow',   // tmux % = vertical split (new pane below)
  '"': 'pane.splitRight',   // tmux " = horizontal split (new pane right)
  o: 'pane.focusNext',
  x: 'pane.close',
  c: 'pane.splitRight',     // tmux c = new pane (maps to split right in L1)
  m: 'canvas.moveMode',
  z: 'canvas.zoomFit',
  '0': 'canvas.zoomReset',
  f: 'canvas.zoomToFocused',
};

export type PrefixResult =
  | { action: 'consumed'; commandId: string }
  | { action: 'cancel' }
  | { action: 'passthrough'; key: string };

export interface PrefixState {
  active: boolean;
  /** Clear the prefix window. */
  cancel: () => void;
}

/**
 * Create a prefix mode controller.
 *
 * - `onActivate` / `onDeactivate`: called when prefix enters/exits.
 * - `dispatch`: called with the matched command id.
 * - `setTimeout` / `clearTimeout`: injected for testability.
 */
export function createPrefixMode(opts: {
  onActivate: () => void;
  onDeactivate: () => void;
  dispatch: (commandId: string) => void;
  setTimeout: (fn: () => void, ms: number) => number;
  clearTimeout: (id: number) => void;
}): {
  /** Try to enter prefix mode. Returns true if ⌘B was consumed. */
  tryEnter: (profile: KeymapProfile) => boolean;
  /** Handle a bare key during prefix mode. Returns the result. */
  handleKey: (key: string) => PrefixResult;
  /** Whether prefix is currently active. */
  isActive: () => boolean;
  /** Cancel prefix (Esc, timeout, or external). */
  cancel: () => void;
} {
  let active = false;
  let timerId: number | undefined;

  const deactivate = () => {
    if (!active) return;
    active = false;
    if (timerId != null) {
      opts.clearTimeout(timerId);
      timerId = undefined;
    }
    opts.onDeactivate();
  };

  return {
    tryEnter(profile: KeymapProfile): boolean {
      if (profile !== 'tmux') return false;
      if (active) {
        deactivate();
        return true;
      }
      active = true;
      opts.onActivate();
      timerId = opts.setTimeout(() => deactivate(), PREFIX_TIMEOUT_MS);
      return true;
    },

    handleKey(key: string): PrefixResult {
      if (!active) return { action: 'cancel' };

      deactivate();

      if (key === 'Escape') {
        return { action: 'cancel' };
      }

      const commandId = PREFIX_MAP[key];
      if (commandId) {
        opts.dispatch(commandId);
        return { action: 'consumed', commandId };
      }

      return { action: 'passthrough', key };
    },

    isActive: () => active,
    cancel: deactivate,
  };
}
