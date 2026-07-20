// V24-11 (VADE2-11) — MemorySurface: live data when a server is present, honest
// fallback when not. fetchMemory is mocked so no real server is needed.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';

const fetchMemoryMock = vi.fn();
vi.mock('../../../org/live/memoryClient', () => ({
  fetchMemory: (...args: unknown[]) => fetchMemoryMock(...args),
}));

import MemorySurface from '../MemorySurface';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown): HTMLElement {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}

afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  fetchMemoryMock.mockReset();
});

const flush = () => new Promise((r) => setTimeout(r, 0));

describe('MemorySurface', () => {
  it('renders the honest fallback with no live server (prop-less)', () => {
    const el = mount(() => <MemorySurface />);
    expect(el.querySelector('[role="tabpanel"][aria-label="Memory"]')).toBeTruthy();
    expect(el.textContent).toContain('/memory');
    expect(el.querySelector('.memory-search')).toBeNull();
    expect(fetchMemoryMock).not.toHaveBeenCalled();
  });

  it('loads the summary when an opaque sidecar handle is present', async () => {
    fetchMemoryMock.mockResolvedValue({
      v: 1,
      summary: '# Memory\n5 files',
      query: null,
      hits: [],
    });

    const el = mount(() => (
      <MemorySurface sidecarId="test-sidecar" />
    ));
    await flush();

    expect(fetchMemoryMock).toHaveBeenCalledWith('test-sidecar', undefined);
    expect(el.querySelector('.memory-search')).toBeTruthy();
    expect(el.querySelector('.memory-summary')?.textContent).toContain('5 files');
  });

  it('renders recall hits returned by the server', async () => {
    fetchMemoryMock.mockResolvedValue({
      v: 1,
      summary: '# Memory',
      query: 'rollout',
      hits: [
        {
          source: 'notes',
          locator: 'notes/abc',
          score: 0.9,
          excerpt: 'blue-green rollout',
          session_id: null,
          ts: null,
          line_start: null,
          line_end: null,
        },
      ],
    });

    const el = mount(() => (
      <MemorySurface sidecarId="test-sidecar" />
    ));
    await flush();

    expect(el.querySelectorAll('.memory-hit').length).toBe(1);
    expect(el.textContent).toContain('blue-green rollout');
    expect(el.textContent).toContain('notes/abc');
  });
});
