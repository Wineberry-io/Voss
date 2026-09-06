import {
  collectLeaves,
  recomputeIndices,
  type TreeNode,
} from './tree';
import type { ActiveLayout, LayoutPreset } from './layoutPresets';
import type { LayoutFile } from './layoutStorage';
import type { SessionFileV1, SessionPane } from './sessionStorage';

/**
 * A6-02 Task 2 — pure session snapshot/restore helpers.
 *
 * No DOM, no Solid, no Tauri, no xterm. The caller owns scrollback
 * extraction (xterm buffer reads) and store assignment (setStore/produce);
 * these helpers only transform tree shapes and data maps.
 *
 * Session restore differs from layout restore: session restore happens on
 * launch BEFORE live user panes exist, so saved pane ids are kept as-is
 * (no remap needed). Layout restore must remap because live panes are
 * already open.
 */

/** PER-01: scrollback cap at serialization time. */
const MAX_SCROLLBACK_LINES = 2000;

/** Result of applying a session — caller assigns to store + seeds terminals. */
export type SessionRestoreResult = {
  root: TreeNode;
  focusedId: string;
  activeLayout: ActiveLayout;
  restoredScrollbackByPaneId: Map<string, string[]>;
};

/**
 * Build a `SessionFileV1` from the current grid state.
 *
 * Whitelist-copies the tree so runtime fields (PTY session ids, process
 * names, env mutations) cannot leak into the on-disk shape (T-A6-03).
 * Scrollback arrays are capped to `MAX_SCROLLBACK_LINES`.
 */
export function buildSessionFile(
  root: TreeNode,
  focusedId: string,
  activeLayout: ActiveLayout,
  scrollbackByPaneId: Map<string, string[]>,
  projectLessAccepted: boolean,
): SessionFileV1 {
  const leaves = collectLeaves(root);
  const panes: SessionPane[] = leaves.map((leaf) => {
    const lines = scrollbackByPaneId.get(leaf.id) ?? null;
    return {
      id: leaf.id,
      scrollback: lines ? lines.slice(-MAX_SCROLLBACK_LINES) : null,
    };
  });

  return {
    version: 1,
    activePreset: activeLayout === 'custom' ? null : activeLayout,
    grid: { root: cloneCanonical(root), focusedId },
    panes,
    projectLessAccepted,
  };
}

/**
 * Apply a loaded session to produce a fresh tree + scrollback map.
 *
 * Unlike layout restore, session restore uses saved pane ids directly
 * because no live user panes exist at launch time. Indices are
 * recomputed from the tree shape.
 */
export function applySessionFile(session: SessionFileV1): SessionRestoreResult {
  const root = cloneCanonical(session.grid.root);
  recomputeIndices(root);

  const focusedId = resolveFocus(session);

  const activeLayout: ActiveLayout = session.activePreset
    ? (session.activePreset as LayoutPreset)
    : 'custom';

  const restoredScrollbackByPaneId = new Map<string, string[]>();
  const leafIds = new Set(collectLeaves(root).map((l) => l.id));
  for (const pane of session.panes) {
    if (pane.scrollback && leafIds.has(pane.id)) {
      restoredScrollbackByPaneId.set(pane.id, pane.scrollback);
    }
  }

  return { root, focusedId, activeLayout, restoredScrollbackByPaneId };
}

/**
 * Convert a LayoutFile to a SessionFileV1 for the D-10 restore priority
 * chain (session → default layout → fresh). Default layouts have no
 * scrollback, so panes get `null`.
 */
export function layoutToSession(
  layout: LayoutFile,
  projectLessAccepted: boolean,
): SessionFileV1 {
  return {
    version: 1,
    activePreset: layout.activePreset as SessionFileV1['activePreset'],
    grid: layout.grid,
    panes: collectLeaves(layout.grid.root).map((l) => ({
      id: l.id,
      scrollback: null,
    })),
    projectLessAccepted,
  };
}

// ---------------------------------------------------------------------------

/** Recursively rebuild the tree, copying ONLY canonical fields. */
function cloneCanonical(n: TreeNode): TreeNode {
  if (n.kind === 'pane') {
    return {
      kind: 'pane',
      id: n.id,
      cwd: n.cwd,
      shell: n.shell,
      index: n.index,
    };
  }
  return {
    kind: 'split',
    orientation: n.orientation,
    ratio: n.ratio,
    left: cloneCanonical(n.left),
    right: cloneCanonical(n.right),
  };
}

/** Resolve focus: direct id hit in leaves, or fallback to first leaf. */
function resolveFocus(session: SessionFileV1): string {
  const leaves = collectLeaves(session.grid.root);
  const savedId = session.grid.focusedId;
  if (leaves.some((l) => l.id === savedId)) return savedId;
  return leaves[0]!.id;
}
