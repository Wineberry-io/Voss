import { afterEach, describe, expect, it } from 'vitest';
import { createEditor, languageExtension, type EditorHandle } from '../editor';

const handles: EditorHandle[] = [];
afterEach(() => {
  for (const h of handles.splice(0)) h.destroy();
  document.body.innerHTML = '';
});

function open(opts: Parameters<typeof createEditor>[1]): { host: HTMLDivElement; h: EditorHandle } {
  const host = document.createElement('div');
  document.body.appendChild(host);
  const h = createEditor(host, opts);
  handles.push(h);
  return { host, h };
}

describe('editor', () => {
  it.each(['markdown', 'typescript', 'javascript', 'python', 'rust', 'json', 'yaml', 'toml', 'plain'] as const)(
    'builds a valid extension for %s',
    (lang) => {
      const { host } = open({ doc: 'x', language: lang });
      expect(host.querySelector('.cm-editor')).not.toBeNull();
      expect(languageExtension(lang)).toBeDefined();
    },
  );

  it('reports edits through onChange and setDoc replaces the document', () => {
    const seen: string[] = [];
    const { h } = open({ doc: 'a', language: 'markdown', onChange: (t) => seen.push(t) });
    expect(h.getDoc()).toBe('a');
    h.setDoc('a\nb');
    expect(h.getDoc()).toBe('a\nb');
    expect(seen).toEqual(['a\nb']);
    h.setDoc('a\nb');
    expect(seen).toHaveLength(1);
  });

  it('read-only editors reject edits and show a gutter when asked', () => {
    const { host, h } = open({ doc: '1\n2\n3', language: 'plain', readOnly: true, gutter: true });
    expect(host.querySelector('.cm-gutters')).not.toBeNull();
    expect(host.querySelector('.cm-content')?.getAttribute('contenteditable')).toBe('false');
    h.revealLine(3);
    h.revealLine(99);
    h.focus();
    expect(h.getDoc()).toBe('1\n2\n3');
  });
});
