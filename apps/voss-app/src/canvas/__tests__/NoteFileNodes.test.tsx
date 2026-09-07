import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';
import { createSignal } from 'solid-js';

const h = vi.hoisted(() => ({
  invoke: vi.fn(),
  editors: [] as { doc: string; opts: Record<string, unknown>; destroyed: boolean; revealed: number[]; onChange?: (t: string) => void }[],
}));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));
vi.mock('../editor', async () => {
  const langs = await import('../editorLanguages');
  return {
    languageForPath: langs.languageForPath,
    createEditor: (
      _host: HTMLElement,
      opts: { doc: string; language: string; readOnly?: boolean; gutter?: boolean; onChange?: (t: string) => void },
    ) => {
      const rec = { doc: opts.doc, opts, destroyed: false, revealed: [] as number[], onChange: opts.onChange };
      h.editors.push(rec);
      return {
        getDoc: () => rec.doc,
        setDoc: (t: string) => (rec.doc = t),
        revealLine: (n: number) => rec.revealed.push(n),
        focus: () => {},
        destroy: () => (rec.destroyed = true),
      };
    },
  };
});

import NoteNode from '../NoteNode';
import FileNode from '../FileNode';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown) {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}
beforeEach(() => {
  h.invoke.mockReset();
  h.editors.length = 0;
});
afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  vi.useRealTimers();
});

describe('NoteNode', () => {
  it('shows a rendered preview when unfocused and an editor when focused; edits debounce to onChange', () => {
    vi.useFakeTimers();
    const [focused, setFocused] = createSignal(false);
    const [text, setText] = createSignal('# Hello\n\n- item');
    const onChange = vi.fn((t: string) => setText(t));
    const el = mount(() => <NoteNode text={text()} focused={focused()} onChange={onChange} />);
    expect(el.querySelector('[data-note-preview]')?.innerHTML).toBe('<h1>Hello</h1><ul><li>item</li></ul>');
    expect(h.editors).toHaveLength(0);

    setFocused(true);
    expect(el.querySelector('[data-note-editor]')).not.toBeNull();
    expect(h.editors).toHaveLength(1);
    expect(h.editors[0].opts.language).toBe('markdown');
    h.editors[0].onChange!('# Changed');
    expect(onChange).not.toHaveBeenCalled();
    vi.advanceTimersByTime(350);
    expect(onChange).toHaveBeenCalledWith('# Changed');

    setFocused(false);
    expect(h.editors[0].destroyed).toBe(true);
    expect(el.querySelector('[data-note-preview]')?.innerHTML).toBe('<h1>Changed</h1>');
  });

  it('flushes a pending edit when blurred before the debounce', () => {
    vi.useFakeTimers();
    const [focused, setFocused] = createSignal(true);
    const onChange = vi.fn();
    mount(() => <NoteNode text="" focused={focused()} onChange={onChange} />);
    h.editors[0].onChange!('quick');
    setFocused(false);
    expect(onChange).toHaveBeenCalledWith('quick');
  });
});

describe('FileNode', () => {
  it('reads the file through read_project_file, opens a read-only editor, and reveals the line', async () => {
    h.invoke.mockResolvedValue({ path: 'src/a.ts', content: 'let a = 1;\nlet b = 2;', language: 'typescript', size: 22 });
    const [line, setLine] = createSignal<number | undefined>(2);
    const el = mount(() => <FileNode path="src/a.ts" line={line()} workspacePath="/ws" />);
    await Promise.resolve();
    await Promise.resolve();
    expect(h.invoke).toHaveBeenCalledWith('read_project_file', { workspacePath: '/ws', relPath: 'src/a.ts', maxBytes: 2 * 1024 * 1024 });
    expect(h.editors).toHaveLength(1);
    expect(h.editors[0].opts).toMatchObject({ readOnly: true, gutter: true, language: 'typescript' });
    expect(h.editors[0].revealed).toEqual([2]);
    expect(el.querySelector('[data-file-error]')).toBeNull();
    setLine(1);
    expect(h.editors[0].revealed).toEqual([2, 1]);
  });

  it('AC-S2-5: a rejected read shows the error text instead of an editor', async () => {
    h.invoke.mockRejectedValue('path is outside the workspace');
    const el = mount(() => <FileNode path="../../etc/passwd" workspacePath="/ws" />);
    await Promise.resolve();
    await Promise.resolve();
    expect(el.querySelector('[data-file-error]')?.textContent).toBe('path is outside the workspace');
    expect(h.editors).toHaveLength(0);
  });
});
