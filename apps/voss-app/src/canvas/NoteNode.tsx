import { Show, createEffect, onCleanup } from 'solid-js';
import { createEditor, type EditorHandle } from './editor';
import { renderMarkdown } from './markdown';

const SAVE_DEBOUNCE_MS = 300;

/** Markdown note: CodeMirror while focused, rendered preview otherwise. */
export default function NoteNode(props: {
  text: string;
  focused: boolean;
  onChange: (text: string) => void;
}) {
  let editor: EditorHandle | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let pending: string | null = null;

  const flush = () => {
    if (timer) clearTimeout(timer);
    timer = undefined;
    if (pending != null && pending !== props.text) props.onChange(pending);
    pending = null;
  };

  const mountEditor = (el: HTMLDivElement) => {
    editor = createEditor(el, {
      doc: props.text,
      language: 'markdown',
      onChange: (text) => {
        pending = text;
        if (timer) clearTimeout(timer);
        timer = setTimeout(flush, SAVE_DEBOUNCE_MS);
      },
    });
    editor.focus();
  };

  createEffect(() => {
    if (!props.focused) {
      flush();
      editor?.destroy();
      editor = undefined;
    }
  });
  createEffect(() => {
    const text = props.text;
    if (editor && pending == null) editor.setDoc(text);
  });
  onCleanup(() => {
    flush();
    editor?.destroy();
  });

  return (
    <div class="note-node" data-note-node="">
      <Show
        when={props.focused}
        fallback={<div class="note-node__preview" data-note-preview="" innerHTML={props.text.trim() ? renderMarkdown(props.text) : '<p class="note-node__empty">Empty note</p>'} />}
      >
        <div class="note-node__editor" data-note-editor="" ref={mountEditor} />
      </Show>
    </div>
  );
}
