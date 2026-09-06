import { type Component, createEffect, createSignal, For, Show } from 'solid-js';
import { invoke } from '@tauri-apps/api/core';

type DirEntry = {
  name: string;
  is_dir: boolean;
  children?: DirEntry[];
};

export interface FileTreeProps {
  projectPath: string | null;
  /** Click on a file; receives the workspace-relative path. */
  onOpenFile?: (relPath: string) => void;
}

function TreeNode(props: { entry: DirEntry; depth: number; parentPath: string; expandedPaths: Set<string>; onToggle: (path: string) => void; onOpenFile?: (fullPath: string) => void }) {
  const fullPath = () => `${props.parentPath}/${props.entry.name}`;
  const isExpanded = () => props.expandedPaths.has(fullPath());

  return (
    <div>
      <div
        style={{
          display: 'flex',
          'align-items': 'center',
          'padding-left': `${props.depth * 12}px`,
          padding: `2px 8px 2px ${props.depth * 12 + 8}px`,
          gap: '4px',
          cursor: props.entry.is_dir || props.onOpenFile ? 'pointer' : 'default',
        }}
        data-file-entry={props.entry.is_dir ? undefined : fullPath()}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-2)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
        onClick={() => {
          if (props.entry.is_dir) props.onToggle(fullPath());
          else props.onOpenFile?.(fullPath());
        }}
      >
        <span style={{
          'font-family': "'JetBrains Mono', ui-monospace, monospace",
          'font-size': '11px',
          color: 'var(--fg-3)',
          width: '12px',
          'flex-shrink': '0',
          'text-align': 'center',
        }}>
          {props.entry.is_dir ? (isExpanded() ? '▾' : '▸') : '●'}
        </span>
        <span style={{
          'font-family': "'Inter', system-ui, sans-serif",
          'font-size': '12px',
          color: props.entry.is_dir ? 'var(--fg-1)' : 'var(--fg-2)',
          'white-space': 'nowrap',
          overflow: 'hidden',
          'text-overflow': 'ellipsis',
        }}>
          {props.entry.name}
        </span>
      </div>
      <Show when={props.entry.is_dir && isExpanded() && props.entry.children}>
        <For each={props.entry.children}>
          {(child) => (
            <TreeNode
              entry={child}
              depth={props.depth + 1}
              parentPath={fullPath()}
              expandedPaths={props.expandedPaths}
              onToggle={props.onToggle}
              onOpenFile={props.onOpenFile}
            />
          )}
        </For>
      </Show>
    </div>
  );
}

const FileTree: Component<FileTreeProps> = (props) => {
  const [entries, setEntries] = createSignal<DirEntry[]>([]);
  const [expandedPaths, setExpandedPaths] = createSignal<Set<string>>(new Set());
  const [loaded, setLoaded] = createSignal(false);

  createEffect(() => {
    const path = props.projectPath;
    if (!path) {
      setEntries([]);
      setLoaded(false);
      return;
    }
    invoke<DirEntry[]>('list_dir', { path })
      .then((result) => {
        setEntries(result);
        setLoaded(true);
        // Auto-expand first-level dirs
        const initial = new Set<string>();
        for (const e of result) {
          if (e.is_dir) initial.add(`${path}/${e.name}`);
        }
        setExpandedPaths(initial);
      })
      .catch(() => {
        setEntries([]);
        setLoaded(true);
      });
  });

  const toggleExpand = (path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  return (
    <Show
      when={props.projectPath}
      fallback={<div class="sidebar-empty">No project open</div>}
    >
      <Show
        when={entries().length > 0}
        fallback={
          loaded()
            ? <div class="sidebar-empty">Empty directory</div>
            : <div class="sidebar-empty">Loading...</div>
        }
      >
        <For each={entries()}>
          {(entry) => (
            <TreeNode
              entry={entry}
              depth={0}
              parentPath={props.projectPath!}
              expandedPaths={expandedPaths()}
              onToggle={toggleExpand}
              onOpenFile={(full) => {
                const root = props.projectPath!;
                props.onOpenFile?.(full.startsWith(`${root}/`) ? full.slice(root.length + 1) : full);
              }}
            />
          )}
        </For>
      </Show>
    </Show>
  );
};

export default FileTree;
