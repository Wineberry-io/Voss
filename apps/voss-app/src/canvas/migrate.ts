/**
 * session.json / layout v1 (binary split tree) → canvas nodes. Each leaf
 * becomes a node at the rect the tree's ratios gave it inside `box`.
 */
import type { GridStore, TreeNode } from '../grid/tree';
import {
  MIN_NODE_H,
  MIN_NODE_W,
  NODE_GAP,
  defaultView,
  recomputeIndices,
  type CanvasNode,
  type CanvasState,
} from './model';
import type { Size } from './geometry';

export const MIGRATION_BOX: Size = { w: 1600, h: 1000 };

export function treeToNodes(root: TreeNode, box: Size = MIGRATION_BOX): CanvasNode[] {
  const out: CanvasNode[] = [];
  const walk = (n: TreeNode, x: number, y: number, w: number, h: number) => {
    if (n.kind === 'pane') {
      out.push({
        id: n.id,
        kind: 'terminal',
        x: Math.round(x),
        y: Math.round(y),
        w: Math.max(MIN_NODE_W, Math.round(w - NODE_GAP)),
        h: Math.max(MIN_NODE_H, Math.round(h - NODE_GAP)),
        z: out.length + 1,
        index: n.index,
        cwd: n.cwd,
        shell: n.shell,
      });
      return;
    }
    if (n.orientation === 'H') {
      const lw = w * n.ratio;
      walk(n.left, x, y, lw, h);
      walk(n.right, x + lw, y, w - lw, h);
    } else {
      const th = h * n.ratio;
      walk(n.left, x, y, w, th);
      walk(n.right, x, y + th, w, h - th);
    }
  };
  walk(root, 0, 0, box.w + NODE_GAP, box.h + NODE_GAP);
  recomputeIndices(out);
  return out;
}

export function gridToCanvas(grid: GridStore, box: Size = MIGRATION_BOX): CanvasState {
  const nodes = treeToNodes(grid.root, box);
  const focusedId = nodes.some((n) => n.id === grid.focusedId)
    ? grid.focusedId
    : nodes[0]!.id;
  return { nodes, view: defaultView(), focusedId };
}
