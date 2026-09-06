import type { LegacyPaneLeaf, LegacySplitNode, LegacyTreeNode } from '../migrate';

export function makePane(defaults?: { cwd?: string; shell?: string }): LegacyPaneLeaf {
  return {
    kind: 'pane',
    id: crypto.randomUUID(),
    cwd: defaults?.cwd ?? '',
    shell: defaults?.shell ?? '',
    index: 1,
  };
}

export function makeSplit(
  orientation: 'H' | 'V',
  left: LegacyTreeNode,
  right: LegacyTreeNode,
): LegacySplitNode {
  return { kind: 'split', orientation, ratio: 0.5, left, right };
}

export function recomputeIndices(root: LegacyTreeNode): void {
  let next = 1;
  const walk = (n: LegacyTreeNode): void => {
    if (n.kind === 'pane') {
      n.index = next++;
      return;
    }
    walk(n.left);
    walk(n.right);
  };
  walk(root);
}
