import { describe, expect, it } from 'vitest';
import { renderMarkdown } from '../markdown';

describe('renderMarkdown', () => {
  it('renders headings, lists, paragraphs, and inline marks', () => {
    const html = renderMarkdown('# Title\n\n- one\n- **two**\n\n1. a\n2. `b`\n\nSome _text_ with [a link](https://x.y).');
    expect(html).toBe(
      '<h1>Title</h1><ul><li>one</li><li><strong>two</strong></li></ul><ol><li>a</li><li><code>b</code></li></ol>' +
        '<p>Some <em>text</em> with <a href="https://x.y" target="_blank" rel="noreferrer">a link</a>.</p>',
    );
  });

  it('escapes html and keeps fenced code verbatim', () => {
    const html = renderMarkdown('<img onerror=x>\n\n```\nif (a < b) {}\n```');
    expect(html).toBe('<p>&lt;img onerror=x&gt;</p><pre><code>if (a &lt; b) {}</code></pre>');
  });

  it('only turns http(s) targets into links', () => {
    expect(renderMarkdown('[x](javascript:alert(1))')).toBe('<p>[x](javascript:alert(1))</p>');
  });
});
