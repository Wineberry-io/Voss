import { invoke } from '@tauri-apps/api/core';
import { Show, createEffect, createSignal, on, onCleanup } from 'solid-js';
import { createEditor, languageForPath, type EditorHandle } from './editor';

export const MAX_FILE_BYTES = 2 * 1024 * 1024;

export type ProjectFile = {
  path: string;
  content: string;
  language: string;
  size: number;
};

export function readProjectFile(workspacePath: string, relPath: string): Promise<ProjectFile> {
  return invoke<ProjectFile>('read_project_file', { workspacePath, relPath, maxBytes: MAX_FILE_BYTES });
}

/** Read-only file view at a path (and optional line) inside the workspace. */
export default function FileNode(props: {
  path: string;
  line?: number;
  workspacePath?: string;
}) {
  const [error, setError] = createSignal<string | null>(null);
  const [loaded, setLoaded] = createSignal<ProjectFile | null>(null);
  let editor: EditorHandle | undefined;
  let host: HTMLDivElement | undefined;

  const mountEditor = (el: HTMLDivElement) => {
    host = el;
  };

  const showFile = (file: ProjectFile) => {
    editor?.destroy();
    editor = undefined;
    if (!host) return;
    editor = createEditor(host, {
      doc: file.content,
      language: languageForPath(file.path),
      readOnly: true,
      gutter: true,
    });
    if (props.line != null) editor.revealLine(props.line);
  };

  createEffect(
    on(
      () => [props.workspacePath, props.path] as const,
      ([wp, path]) => {
        setLoaded(null);
        setError(null);
        if (!wp) {
          setError('no workspace open');
          return;
        }
        readProjectFile(wp, path)
          .then((file) => {
            setLoaded(file);
            showFile(file);
          })
          .catch((e: unknown) => setError(typeof e === 'string' ? e : (e as Error)?.message ?? 'could not read file'));
      },
    ),
  );
  createEffect(
    on(
      () => props.line,
      (line) => {
        if (line != null && editor) editor.revealLine(line);
      },
      { defer: true },
    ),
  );
  onCleanup(() => editor?.destroy());

  return (
    <div class="file-node" data-file-node={props.path}>
      <Show when={error()}>
        {(msg) => <div class="file-node__error" data-file-error="">{msg()}</div>}
      </Show>
      <div class="file-node__editor" data-file-editor="" ref={mountEditor} hidden={!loaded()} />
    </div>
  );
}
