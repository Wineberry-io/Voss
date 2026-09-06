import { minimalSetup } from 'codemirror';
import { EditorState, type Extension } from '@codemirror/state';
import { EditorView, lineNumbers } from '@codemirror/view';
import { StreamLanguage } from '@codemirror/language';
import { markdown } from '@codemirror/lang-markdown';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { rust } from '@codemirror/lang-rust';
import { json } from '@codemirror/lang-json';
import { yaml } from '@codemirror/lang-yaml';
import { toml } from '@codemirror/legacy-modes/mode/toml';
import type { EditorLanguage } from './editorLanguages';

export type { EditorLanguage } from './editorLanguages';
export { languageForPath } from './editorLanguages';

export function languageExtension(lang: EditorLanguage): Extension {
  switch (lang) {
    case 'markdown':
      return markdown();
    case 'typescript':
      return javascript({ typescript: true, jsx: true });
    case 'javascript':
      return javascript({ jsx: true });
    case 'python':
      return python();
    case 'rust':
      return rust();
    case 'json':
      return json();
    case 'yaml':
      return yaml();
    case 'toml':
      return StreamLanguage.define(toml);
    default:
      return [];
  }
}

const theme = EditorView.theme({
  '&': { height: '100%', backgroundColor: 'var(--bg-0)', color: 'var(--fg-0)', fontSize: '12px' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.45' },
  '.cm-content': { caretColor: 'var(--fg-0)' },
  '.cm-gutters': { backgroundColor: 'var(--bg-1)', color: 'var(--fg-3)', border: 'none' },
  '.cm-activeLine': { backgroundColor: 'color-mix(in srgb, var(--focus) 10%, transparent)' },
  '.cm-activeLineGutter': { backgroundColor: 'color-mix(in srgb, var(--focus) 10%, transparent)' },
  '&.cm-focused': { outline: 'none' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: 'color-mix(in srgb, var(--focus) 30%, transparent)' },
});

export interface EditorHandle {
  getDoc(): string;
  setDoc(text: string): void;
  revealLine(line: number): void;
  focus(): void;
  destroy(): void;
}

export function createEditor(
  host: HTMLElement,
  opts: {
    doc: string;
    language: EditorLanguage;
    readOnly?: boolean;
    gutter?: boolean;
    onChange?: (text: string) => void;
  },
): EditorHandle {
  const extensions: Extension[] = [minimalSetup, theme, languageExtension(opts.language), EditorView.lineWrapping];
  if (opts.gutter) extensions.push(lineNumbers());
  if (opts.readOnly) extensions.push(EditorState.readOnly.of(true), EditorView.editable.of(false));
  if (opts.onChange) {
    const onChange = opts.onChange;
    extensions.push(
      EditorView.updateListener.of((u) => {
        if (u.docChanged) onChange(u.state.doc.toString());
      }),
    );
  }
  const view = new EditorView({ state: EditorState.create({ doc: opts.doc, extensions }), parent: host });
  return {
    getDoc: () => view.state.doc.toString(),
    setDoc: (text) => {
      if (text === view.state.doc.toString()) return;
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
    },
    revealLine: (line) => {
      const n = Math.max(1, Math.min(line, view.state.doc.lines));
      const pos = view.state.doc.line(n).from;
      view.dispatch({ selection: { anchor: pos }, effects: EditorView.scrollIntoView(pos, { y: 'center' }) });
    },
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
