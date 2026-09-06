/**
 * Canvas ↔ session.json / layout file helpers. Pure: no DOM, Solid, Tauri,
 * or xterm. Callers own scrollback extraction and store assignment.
 */
import { isLayoutPreset, type ActiveLayout } from './arrange';
import type { LayoutFile } from '../grid/layoutStorage';
import type { SessionFile, SessionFileV2, SessionPane } from '../grid/sessionStorage';

/** A v2 file this module wrote: `canvas` is always present. */
export type CanvasSessionFile = SessionFileV2 & { canvas: CanvasState };
import { gridToCanvas, type LegacyGridStore } from './migrate';
import {
  defaultView,
  makeNode,
  orderedNodes,
  recomputeIndices,
  type CanvasNode,
  type CanvasState,
} from './model';

const MAX_SCROLLBACK_LINES = 2000;

export type CanvasRestoreResult = {
  canvas: CanvasState;
  activeLayout: ActiveLayout;
  restoredScrollbackByPaneId: Map<string, string[]>;
};

function cloneNode(n: CanvasNode): CanvasNode {
  const out: CanvasNode = {
    id: n.id,
    kind: n.kind,
    x: n.x,
    y: n.y,
    w: n.w,
    h: n.h,
    z: n.z,
    index: n.index,
    cwd: n.cwd,
    shell: n.shell,
  };
  if (n.note) out.note = { text: n.note.text };
  if (n.file) out.file = { path: n.file.path, ...(n.file.line != null ? { line: n.file.line } : {}) };
  return out;
}

/** Whitelist copy: runtime fields can never reach disk. */
export function cloneCanvas(state: CanvasState): CanvasState {
  return {
    nodes: state.nodes.map(cloneNode),
    view: { x: state.view.x, y: state.view.y, zoom: state.view.zoom },
    focusedId: state.focusedId,
  };
}

function sessionGrid(session: SessionFile): LegacyGridStore {
  if (session.version === 1) return session.grid;
  if (session.grid) return session.grid;
  throw new Error('session file has neither canvas nor grid');
}

function activeLayoutOf(preset: string | null): ActiveLayout {
  return isLayoutPreset(preset) ? preset : 'custom';
}

function resolveFocus(state: CanvasState): string {
  if (state.nodes.some((n) => n.id === state.focusedId)) return state.focusedId;
  return orderedNodes(state)[0]!.id;
}

export function buildSessionFile(
  state: CanvasState,
  activeLayout: ActiveLayout,
  scrollbackByPaneId: Map<string, string[]>,
  projectLessAccepted: boolean,
): CanvasSessionFile {
  const canvas = cloneCanvas(state);
  const panes: SessionPane[] = orderedNodes(canvas).map((n) => {
    const lines = scrollbackByPaneId.get(n.id) ?? null;
    return { id: n.id, scrollback: lines ? lines.slice(-MAX_SCROLLBACK_LINES) : null };
  });
  return {
    version: 2,
    activePreset: activeLayout === 'custom' ? null : activeLayout,
    canvas,
    panes,
    projectLessAccepted,
  };
}

/** Load either version. v1 trees become nodes via the migration box. */
export function applySessionFile(session: SessionFile): CanvasRestoreResult {
  const canvas =
    session.version === 2 && session.canvas
      ? cloneCanvas(session.canvas)
      : gridToCanvas(sessionGrid(session));
  recomputeIndices(canvas.nodes);
  canvas.focusedId = resolveFocus(canvas);
  const ids = new Set(canvas.nodes.map((n) => n.id));
  const restoredScrollbackByPaneId = new Map<string, string[]>();
  for (const pane of session.panes) {
    if (pane.scrollback && ids.has(pane.id)) {
      restoredScrollbackByPaneId.set(pane.id, pane.scrollback);
    }
  }
  return { canvas, activeLayout: activeLayoutOf(session.activePreset), restoredScrollbackByPaneId };
}

/** Nodes a layout describes: its own canvas geometry, else its migrated tree. */
export function layoutCanvas(layout: LayoutFile): CanvasState {
  if (layout.nodes && layout.nodes.length > 0) {
    const nodes = layout.nodes.map(cloneNode);
    recomputeIndices(nodes);
    const saved = layout.focusedId ?? layout.grid?.focusedId;
    const focusedId = saved && nodes.some((n) => n.id === saved) ? saved : nodes[0]!.id;
    return { nodes, view: layout.view ?? defaultView(), focusedId };
  }
  if (!layout.grid) throw new Error('layout file has neither nodes nor grid');
  return gridToCanvas(layout.grid);
}

export function layoutToSession(
  layout: LayoutFile,
  projectLessAccepted: boolean,
): CanvasSessionFile {
  const canvas = layoutCanvas(layout);
  return {
    version: 2,
    activePreset: layout.activePreset,
    canvas,
    panes: orderedNodes(canvas).map((n) => ({ id: n.id, scrollback: null })),
    projectLessAccepted,
  };
}

export function serializeLayout(
  state: CanvasState,
  activeLayout: ActiveLayout,
): LayoutFile {
  const canvas = cloneCanvas(state);
  return {
    version: 2,
    activePreset: activeLayout === 'custom' ? null : activeLayout,
    nodes: orderedNodes(canvas),
    view: canvas.view,
    focusedId: canvas.focusedId,
  };
}

export type LayoutApplyResult = {
  canvas: CanvasState;
  activeLayout: ActiveLayout;
};

/**
 * Apply a saved layout to live nodes without destroying any. Existing nodes
 * take the saved rects in reading order; extra saved slots spawn fresh nodes
 * with the saved cwd/shell; extra live nodes keep their place.
 */
export function applyLayoutToCanvas(
  current: CanvasState,
  layout: LayoutFile,
): LayoutApplyResult {
  const savedCanvas = layoutCanvas(layout);
  const saved = orderedNodes(savedCanvas);
  const live = orderedNodes(cloneCanvas(current));
  const next: CanvasNode[] = [];
  const count = Math.max(saved.length, live.length);
  for (let i = 0; i < count; i += 1) {
    const s = saved[i];
    const l = live[i];
    if (s && l) {
      next.push({ ...l, x: s.x, y: s.y, w: s.w, h: s.h, z: s.z });
    } else if (s) {
      next.push({ ...makeNode({ kind: s.kind, cwd: s.cwd, shell: s.shell, x: s.x, y: s.y, w: s.w, h: s.h, note: s.note, file: s.file }), z: s.z });
    } else if (l) {
      next.push(l);
    }
  }
  recomputeIndices(next);
  const savedFocus = savedCanvas.focusedId;
  const focusedId =
    next.some((n) => n.id === savedFocus)
      ? savedFocus
      : next.some((n) => n.id === current.focusedId)
        ? current.focusedId
        : next[0]!.id;
  return {
    canvas: { nodes: next, view: layout.view ?? current.view, focusedId },
    activeLayout: activeLayoutOf(layout.activePreset),
  };
}
