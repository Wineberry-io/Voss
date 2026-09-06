/**
 * Free-floating canvas model (S1). Every pane is a node with world-space
 * geometry; there is no split tree. Field names are the wire contract: the
 * Rust mirror (`canvas.rs`) and `session.json` v2 round-trip these keys.
 */
export type NodeKind = 'terminal' | 'native' | 'note' | 'file';

export type NotePayload = { text: string };
export type FilePayload = { path: string; line?: number };

export type CanvasNode = {
  id: string;
  kind: NodeKind;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  /** Geometric reading order (row by row, left to right), 1-based. */
  index: number;
  cwd: string;
  shell: string;
  note?: NotePayload;
  file?: FilePayload;
};

export type CanvasView = {
  x: number;
  y: number;
  zoom: number;
};

export type CanvasState = {
  nodes: CanvasNode[];
  view: CanvasView;
  focusedId: string;
};

export const DEFAULT_NODE_W = 720;
export const DEFAULT_NODE_H = 440;
export const NODE_GAP = 16;

export const HEADER_PX = 22;
export const FLOOR_COLS = 20;
export const FLOOR_ROWS = 5;
export const CELL_W = 8;
export const CELL_H = 20;
export const MIN_NODE_W = FLOOR_COLS * CELL_W;
export const MIN_NODE_H = FLOOR_ROWS * CELL_H + HEADER_PX;

export const DEFAULT_NOTE_W = 360;
export const DEFAULT_NOTE_H = 240;
export const DEFAULT_FILE_W = 640;
export const DEFAULT_FILE_H = 480;

export const ZOOM_MIN = 0.25;
export const ZOOM_MAX = 2.5;

export const ROW_BAND_PX = 24;

export function makeNode(defaults?: {
  cwd?: string;
  shell?: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  kind?: NodeKind;
  note?: NotePayload;
  file?: FilePayload;
}): CanvasNode {
  const node: CanvasNode = {
    id: crypto.randomUUID(),
    kind: defaults?.kind ?? 'terminal',
    x: defaults?.x ?? 0,
    y: defaults?.y ?? 0,
    w: defaults?.w ?? DEFAULT_NODE_W,
    h: defaults?.h ?? DEFAULT_NODE_H,
    z: 1,
    index: 1,
    cwd: defaults?.cwd ?? '',
    shell: defaults?.shell ?? '',
  };
  if (defaults?.note) node.note = { text: defaults.note.text };
  if (defaults?.file) node.file = { path: defaults.file.path, ...(defaults.file.line != null ? { line: defaults.file.line } : {}) };
  return node;
}

export function defaultSizeFor(kind: NodeKind): { w: number; h: number } {
  if (kind === 'note') return { w: DEFAULT_NOTE_W, h: DEFAULT_NOTE_H };
  if (kind === 'file') return { w: DEFAULT_FILE_W, h: DEFAULT_FILE_H };
  return { w: DEFAULT_NODE_W, h: DEFAULT_NODE_H };
}

export function defaultView(): CanvasView {
  return { x: 0, y: 0, zoom: 1 };
}

export function createCanvasState(defaults?: {
  cwd?: string;
  shell?: string;
}): CanvasState {
  const node = makeNode(defaults);
  return { nodes: [node], view: defaultView(), focusedId: node.id };
}

/**
 * Reading order: nodes are grouped into rows whose top edges lie within
 * ROW_BAND_PX of the row's first node, rows sorted top to bottom, nodes
 * within a row left to right. Assigns 1-based `index` in place and returns
 * the nodes in that order.
 */
export function recomputeIndices(nodes: CanvasNode[]): CanvasNode[] {
  const byY = [...nodes].sort((a, b) => a.y - b.y || a.x - b.x);
  const rows: CanvasNode[][] = [];
  for (const n of byY) {
    const row = rows[rows.length - 1];
    if (row && Math.abs(n.y - row[0].y) <= ROW_BAND_PX) row.push(n);
    else rows.push([n]);
  }
  const ordered: CanvasNode[] = [];
  for (const row of rows) {
    row.sort((a, b) => a.x - b.x);
    ordered.push(...row);
  }
  ordered.forEach((n, i) => {
    n.index = i + 1;
  });
  return ordered;
}

export function orderedNodes(state: CanvasState): CanvasNode[] {
  return [...state.nodes].sort((a, b) => a.index - b.index);
}

export function findNode(
  state: CanvasState,
  id: string,
): CanvasNode | undefined {
  return state.nodes.find((n) => n.id === id);
}

export function maxZ(nodes: readonly CanvasNode[]): number {
  return nodes.reduce((m, n) => Math.max(m, n.z), 0);
}
