import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';

const h = vi.hoisted(() => ({
  invoke: vi.fn().mockResolvedValue(undefined),
  mounts: new Map<string, number>(),
}));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));
vi.mock('../../pane/PaneComponent', () => ({
  default: (p: { id: string; index?: number; restoredScrollback?: string[] }) => {
    h.mounts.set(p.id, (h.mounts.get(p.id) ?? 0) + 1);
    const d = document.createElement('div');
    d.setAttribute('data-testid', 'pane');
    d.setAttribute('data-mock-pane-id', String(p.id));
    d.setAttribute('data-idx', String(p.index ?? 1));
    return d;
  },
}));

import { makePane, makeSplit, recomputeIndices as treeIndices } from './legacyTree';
import type { SessionFileV1 } from '../../grid/sessionStorage';
import CanvasRoot, { type CanvasController } from '../CanvasRoot';
import { NODE_GAP } from '../model';
import { isCanvasDragInFlight } from '../sync';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown) {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}
beforeEach(() => {
  h.invoke.mockClear();
  h.mounts.clear();
});
afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  vi.useRealTimers();
});

const FOCUS = '.grid-pane-leaf--focused';
const nodeEls = (el: HTMLElement) => [...el.querySelectorAll<HTMLElement>('[data-pane-id]')];
const rectOf = (el: HTMLElement) => {
  const m = /translate\((-?[\d.]+)px, (-?[\d.]+)px\)/.exec(el.style.transform);
  return { x: Number(m?.[1]), y: Number(m?.[2]), w: parseFloat(el.style.width), h: parseFloat(el.style.height) };
};
const syncCalls = () => h.invoke.mock.calls.filter((c) => c[0] === 'sync_canvas');

function mountCanvas(props: Partial<Parameters<typeof CanvasRoot>[0]> = {}) {
  let ctrl!: CanvasController;
  const el = mount(() => (
    <CanvasRoot projectCwd="/proj" controllerRef={(c) => (ctrl = c)} externalKeymap {...props} />
  ));
  return { el, ctrl: () => ctrl };
}

describe('CanvasRoot', () => {
  it('AC-S1-7: boots to one node at the world origin, focused', () => {
    const { el } = mountCanvas();
    const nodes = nodeEls(el);
    expect(nodes).toHaveLength(1);
    expect(rectOf(nodes[0])).toMatchObject({ x: 0, y: 0 });
    expect(el.querySelectorAll(FOCUS)).toHaveLength(1);
    expect(el.querySelector('[data-mock-pane-id]')).not.toBeNull();
  });

  it('AC-S1-1: a v1 split session restores as proportional nodes with scrollback', () => {
    const a = makePane({ cwd: '/a', shell: 'zsh' });
    const b = makePane({ cwd: '/b', shell: 'zsh' });
    const c = makePane({ cwd: '/c', shell: 'zsh' });
    const root = makeSplit('H', a, makeSplit('V', b, c));
    treeIndices(root);
    const session: SessionFileV1 = {
      version: 1,
      activePreset: null,
      grid: { root, focusedId: b.id },
      panes: [{ id: a.id, scrollback: ['one', 'two'] }, { id: b.id, scrollback: null }, { id: c.id, scrollback: null }],
      projectLessAccepted: true,
    };
    const { el, ctrl } = mountCanvas({ initialSession: session });
    const nodes = nodeEls(el);
    expect(nodes.map((n) => n.getAttribute('data-pane-id'))).toEqual([a.id, b.id, c.id]);
    const ra = rectOf(nodes[0]);
    const rb = rectOf(nodes[1]);
    const rc = rectOf(nodes[2]);
    expect(rb.x).toBeGreaterThan(ra.x + ra.w - 1);
    expect(rc.y).toBeGreaterThan(rb.y + rb.h - 1);
    expect(el.querySelector(FOCUS)?.getAttribute('data-pane-id')).toBe(b.id);
    expect(el.querySelector('[data-testid="restore-banner"]')?.textContent).toContain('2 lines');
    const snap = ctrl().snapshot();
    expect(snap.nodes).toHaveLength(3);
    expect(snap.view).toEqual({ x: 0, y: 0, zoom: 1 });
  });

  it('AC-S1-3: ⌘D places a same-size node snapped to the right; ⌘⇧D below', () => {
    const { el, ctrl } = mountCanvas();
    const first = rectOf(nodeEls(el)[0]);
    ctrl().splitFocused('H');
    let nodes = nodeEls(el);
    expect(nodes).toHaveLength(2);
    const right = rectOf(nodes[1]);
    expect(right).toMatchObject({ x: first.x + first.w + NODE_GAP, y: first.y, w: first.w, h: first.h });
    expect(el.querySelector(FOCUS)?.getAttribute('data-pane-id')).toBe(nodes[1].getAttribute('data-pane-id'));
    ctrl().splitFocused('V');
    nodes = nodeEls(el);
    expect(nodes).toHaveLength(3);
    expect(rectOf(nodes[2])).toMatchObject({ x: right.x, y: right.y + right.h + NODE_GAP });
  });

  it('AC-S1-4: dragging a node far left makes it index 1 for ⌘1', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    const [first, second] = nodeEls(el).map((n) => n.getAttribute('data-pane-id')!);
    expect(ctrl().snapshot().nodes.find((n) => n.id === second)!.index).toBe(2);

    const header = nodeEls(el)[1].querySelector('.pane-header-bar') as HTMLElement;
    header.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 800, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: -1200, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: -1200, clientY: 10 }));

    const moved = ctrl().snapshot().nodes.find((n) => n.id === second)!;
    expect(moved.x).toBeLessThan(0);
    expect(moved.index).toBe(1);
    ctrl().focusIndex(1);
    expect(el.querySelector(FOCUS)?.getAttribute('data-pane-id')).toBe(second);
    ctrl().focusIndex(2);
    expect(el.querySelector(FOCUS)?.getAttribute('data-pane-id')).toBe(first);
  });

  it('AC-S1-2: pan, zoom, move, and resize never remount a pane', () => {
    const { el, ctrl } = mountCanvas();
    const id = nodeEls(el)[0].getAttribute('data-pane-id')!;
    expect(h.mounts.get(id)).toBe(1);
    ctrl().setView({ x: 300, y: -100, zoom: 0.5 });
    ctrl().zoomReset();
    ctrl().resizeDirection('right');
    ctrl().resizeDirection('down');
    ctrl().equalizePanes();
    ctrl().applyPreset('fanout');
    expect(h.mounts.get(id)).toBe(1);
    expect(nodeEls(el)[0].getAttribute('data-pane-id')).toBe(id);
  });

  it('AC-S1-5: view changes reach the Rust mirror after the debounce', () => {
    vi.useFakeTimers();
    const { ctrl } = mountCanvas();
    h.invoke.mockClear();
    ctrl().setView({ x: 42, y: -7, zoom: 1.5 });
    expect(syncCalls()).toHaveLength(0);
    vi.advanceTimersByTime(300);
    const last = syncCalls().at(-1)!;
    expect(last[1].newState.view).toEqual({ x: 42, y: -7, zoom: 1.5 });
  });

  it('closing the last node respawns a fresh one in place; focus and count reported', () => {
    const focus: string[] = [];
    const counts: number[] = [];
    const { el, ctrl } = mountCanvas({ onFocusChange: (id) => focus.push(id), onLeafCountChange: (c) => counts.push(c) });
    const before = nodeEls(el)[0].getAttribute('data-pane-id')!;
    ctrl().closeFocused();
    const after = nodeEls(el);
    expect(after).toHaveLength(1);
    expect(after[0].getAttribute('data-pane-id')).not.toBe(before);
    expect(focus.at(-1)).toBe(after[0].getAttribute('data-pane-id'));
    expect(counts.at(-1)).toBe(1);
  });

  it('close is gated by a busy foreground process', () => {
    const { el, ctrl } = mountCanvas({ closeUI: { isFg: () => true, fgName: () => 'sleep' } });
    ctrl().closeFocused();
    expect(nodeEls(el)).toHaveLength(1);
    expect(el.querySelector('[role="alertdialog"]')?.textContent).toContain('"sleep" is running');
  });

  it('zoomFit frames every node and zoomToFocused centres at zoom 1', () => {
    const { ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    ctrl().splitFocused('V');
    ctrl().zoomFit();
    expect(ctrl().snapshot().view.zoom).toBeLessThanOrEqual(1);
    ctrl().zoomToFocused();
    expect(ctrl().snapshot().view.zoom).toBe(1);
  });

  it('pointercancel settles a header drag and clears the in-flight flag', () => {
    const { el, ctrl } = mountCanvas();
    const id = nodeEls(el)[0].getAttribute('data-pane-id')!;
    const header = nodeEls(el)[0].querySelector('.pane-header-bar') as HTMLElement;
    header.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 210, clientY: 10 }));
    expect(isCanvasDragInFlight()).toBe(true);
    window.dispatchEvent(new MouseEvent('pointercancel', { clientX: 210, clientY: 10 }));
    expect(isCanvasDragInFlight()).toBe(false);
    expect(ctrl().snapshot().nodes.find((n) => n.id === id)!.x).toBe(200);
    expect(nodeEls(el)[0].hasAttribute('data-dragging')).toBe(false);
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 900, clientY: 10 }));
    expect(ctrl().snapshot().nodes.find((n) => n.id === id)!.x).toBe(200);
  });

  it('unmounting mid-drag clears the in-flight flag', () => {
    const { el } = mountCanvas();
    const header = nodeEls(el)[0].querySelector('.pane-header-bar') as HTMLElement;
    header.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 50, clientY: 10 }));
    expect(isCanvasDragInFlight()).toBe(true);
    dispose?.();
    dispose = undefined;
    expect(isCanvasDragInFlight()).toBe(false);
  });
});
