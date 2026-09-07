import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';

const h = vi.hoisted(() => ({
  invoke: vi.fn().mockResolvedValue(undefined),
  mounts: new Map<string, number>(),
}));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));
vi.mock('../editor', () => ({
  languageForPath: () => 'plain',
  createEditor: () => ({ getDoc: () => '', setDoc: () => {}, revealLine: () => {}, focus: () => {}, destroy: () => {} }),
}));
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
import { getPaneSession, trackPaneSession, __resetPaneSessions, type PaneSession } from '../../pane/paneSessionRegistry';

function fakeSession(paneId: string, lines: string[]): PaneSession {
  const hostEl = document.createElement('div');
  const term = {
    buffer: { active: { length: lines.length, getLine: (y: number) => ({ translateToString: () => lines[y] }) } },
    dispose: () => {},
  };
  const s = {
    paneId,
    hostEl,
    term,
    fitAddon: {},
    searchAddon: {},
    transport: { kill: () => {} },
    sink: {},
    owner: null,
    opened: true,
    spawned: true,
    firstInputFired: false,
    lastOscTitleAt: 0,
    dot: 'running',
    lastExitCode: null,
    lastBudget: null,
    lastProc: 'top',
    cfg: {},
  } as unknown as PaneSession;
  trackPaneSession(s);
  return s;
}

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
  document.documentElement.classList.add('reduced-motion');
});
afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  document.documentElement.classList.remove('reduced-motion');
  __resetPaneSessions();
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
    ctrl().setView({ x: 300, y: -100, zoom: 0.7 });
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

  it('AC-S2-1: dragging B toward A snaps its left edge to A right edge with a guide; ⌥ disables snap', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    const [a, b] = ctrl().snapshot().nodes;
    const header = nodeEls(el)[1].querySelector('.pane-header-bar') as HTMLElement;
    const target = a.x + a.w + 5;
    header.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 1000, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 1000 + (target - b.x), clientY: 10 }));
    expect(ctrl().snapshot().nodes[1].x).toBe(a.x + a.w);
    expect(el.querySelector('[data-guide="x"]')).not.toBeNull();
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 1000 + (target - b.x), clientY: 10 }));
    expect(el.querySelector('[data-guide]')).toBeNull();
    expect(ctrl().snapshot().nodes[1].x).toBe(a.x + a.w);

    header.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 1000, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 1005, clientY: 10, altKey: true }));
    expect(ctrl().snapshot().nodes[1].x).toBe(a.x + a.w + 5);
    expect(el.querySelector('[data-guide]')).toBeNull();
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 1005, clientY: 10, altKey: true }));
  });

  it('shift-drag on the plane draws a marquee that selects; dragging a selected node moves the group', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    const [a, b] = ctrl().snapshot().nodes;
    const plane = el.querySelector('.canvas-plane') as HTMLElement;
    plane.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, shiftKey: true, clientX: 5, clientY: 5 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: a.x + a.w + 40, clientY: 40, shiftKey: true }));
    expect(el.querySelector('[data-marquee]')).not.toBeNull();
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: a.x + a.w + 40, clientY: 40, shiftKey: true }));
    expect(el.querySelector('[data-marquee]')).toBeNull();
    expect(el.querySelectorAll('[data-selected]')).toHaveLength(2);

    const header = nodeEls(el)[0].querySelector('.pane-header-bar') as HTMLElement;
    header.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 10, clientY: 310, altKey: true }));
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 10, clientY: 310, altKey: true }));
    const after = ctrl().snapshot().nodes;
    expect(after.find((n) => n.id === a.id)!.y).toBe(a.y + 300);
    expect(after.find((n) => n.id === b.id)!.y).toBe(b.y + 300);

    plane.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 5, clientY: 5 }));
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 5, clientY: 5 }));
    expect(el.querySelectorAll('[data-selected]')).toHaveLength(0);
  });

  it('west and north handles move the origin while resizing', () => {
    const { el, ctrl } = mountCanvas();
    const before = ctrl().snapshot().nodes[0];
    const handle = el.querySelector('[data-resize-handle="nw"]') as HTMLElement;
    handle.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 0, clientY: 0 }));
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 20, clientY: 30 }));
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 20, clientY: 30 }));
    const after = ctrl().snapshot().nodes[0];
    expect(after).toMatchObject({ x: before.x + 20, y: before.y + 30, w: before.w - 20, h: before.h - 30 });
    expect(el.querySelectorAll('[data-resize-handle]')).toHaveLength(8);
  });

  it('placement mode: a ghost follows the pointer, click places a node there, Esc cancels', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().placeNode('terminal');
    expect(el.querySelector('[data-placement-ghost="terminal"]')).not.toBeNull();
    const root = el.querySelector('.canvas-root') as HTMLElement;
    root.dispatchEvent(new MouseEvent('pointermove', { bubbles: true, clientX: 900, clientY: 700 }));
    const ghost = el.querySelector('[data-placement-ghost]') as HTMLElement;
    const g = rectOf(ghost);
    expect(g.x).toBe(Math.round(900 - g.w / 2));
    expect(g.y).toBe(Math.round(700 - g.h / 2));
    root.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 900, clientY: 700 }));
    expect(el.querySelector('[data-placement-ghost]')).toBeNull();
    const nodes = ctrl().snapshot().nodes;
    expect(nodes).toHaveLength(2);
    expect(nodes[1]).toMatchObject({ x: g.x, y: g.y, kind: 'terminal' });
    expect(ctrl().snapshot().focusedId).toBe(nodes[1].id);

    ctrl().placeNode('terminal');
    expect(root.hasAttribute('data-placing')).toBe(true);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(root.hasAttribute('data-placing')).toBe(false);
    expect(ctrl().snapshot().nodes).toHaveLength(2);
  });

  it('AC-S2-7: focusDirection pans to an off-screen node instantly under reduced motion', () => {
    const { ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    ctrl().focusIndex(1);
    const before = ctrl().snapshot();
    const far = before.nodes[1];
    ctrl().setView({ x: 0, y: 0, zoom: 1 });
    ctrl().focusDirection('right');
    const after = ctrl().snapshot();
    expect(after.focusedId).toBe(far.id);
    expect(after.view.x).toBeLessThan(0);
    expect(after.view.x + (far.x + far.w)).toBeLessThanOrEqual(window.innerWidth);
  });

  it('camera moves tween over at most 200 ms when motion is allowed', () => {
    document.documentElement.classList.remove('reduced-motion');
    vi.useFakeTimers();
    const { ctrl } = mountCanvas();
    ctrl().setView({ x: 0, y: 0, zoom: 1 });
    ctrl().zoomFit();
    const start = ctrl().snapshot().view;
    expect(start).toEqual({ x: 0, y: 0, zoom: 1 });
    vi.advanceTimersByTime(250);
    const end = ctrl().snapshot().view;
    expect(end.zoom).toBeLessThanOrEqual(1);
    expect(end).not.toEqual(start);
  });

  it('AC-S2-2: below zoom 0.6 every node is a chip; zooming back restores the same xterm without a respawn', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    const ids = ctrl().snapshot().nodes.map((n) => n.id);
    const sessions = ids.map((id) => fakeSession(id, ['$ top', 'PID USER', '1 root']));
    expect(ids.map((id) => h.mounts.get(id))).toEqual([1, 1]);

    ctrl().setView({ x: 0, y: 0, zoom: 0.4 });
    expect(el.querySelector('.canvas-root')?.hasAttribute('data-lod')).toBe(true);
    expect(el.querySelectorAll('[data-terminal-chip]')).toHaveLength(2);
    expect(el.querySelectorAll('[data-mock-pane-id]')).toHaveLength(0);
    const chip = el.querySelector(`[data-terminal-chip="${ids[0]}"]`)!;
    expect(chip.textContent).toContain('top');
    expect(chip.textContent).toContain('1 root');

    ctrl().setView({ x: 0, y: 0, zoom: 1 });
    expect(el.querySelectorAll('[data-terminal-chip]')).toHaveLength(0);
    expect(el.querySelectorAll('[data-mock-pane-id]')).toHaveLength(2);
    ids.forEach((id, i) => {
      expect(getPaneSession(id)).toBe(sessions[i]);
      expect(getPaneSession(id)!.term).toBe(sessions[i].term);
    });
    expect(ids.map((id) => h.mounts.get(id))).toEqual([2, 2]);
  });

  it('typing into a chip-rendered focused node snaps the camera to it at zoom 1', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().setView({ x: 0, y: 0, zoom: 0.3 });
    expect(el.querySelector('.canvas-root')?.hasAttribute('data-lod')).toBe(true);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'l' }));
    expect(ctrl().snapshot().view.zoom).toBe(1);
    expect(el.querySelector('.canvas-root')?.hasAttribute('data-lod')).toBe(false);
  });

  it('minimap appears from three nodes and a click centres the view', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().splitFocused('H');
    expect(el.querySelector('[data-minimap]')).toBeNull();
    ctrl().splitFocused('V');
    const map = el.querySelector('[data-minimap]') as HTMLElement;
    expect(map).not.toBeNull();
    expect(map.querySelectorAll('[data-minimap-node]')).toHaveLength(3);
    const before = { ...ctrl().snapshot().view };
    map.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 0, clientY: 0 }));
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 0, clientY: 0 }));
    const after = ctrl().snapshot().view;
    expect(after.zoom).toBe(before.zoom);
    expect(after).not.toEqual(before);
  });

  it('openFile adds a file node beside the focused node once and refocuses it with a new line afterwards', () => {
    h.invoke.mockResolvedValue({ path: 'src/a.ts', content: '', language: 'typescript', size: 0 });
    const { el, ctrl } = mountCanvas({ workspacePath: '/ws' });
    const term = ctrl().snapshot().nodes[0];
    ctrl().openFile('src/a.ts', 7);
    let nodes = ctrl().snapshot().nodes;
    expect(nodes).toHaveLength(2);
    expect(nodes[1]).toMatchObject({ kind: 'file', file: { path: 'src/a.ts', line: 7 }, x: term.x + term.w + NODE_GAP });
    expect(ctrl().snapshot().focusedId).toBe(nodes[1].id);
    expect(el.querySelector('[data-file-node="src/a.ts"]')).not.toBeNull();
    expect(el.querySelectorAll('[data-mock-pane-id]')).toHaveLength(1);

    ctrl().focusIndex(1);
    ctrl().openFile('src/a.ts', 30);
    nodes = ctrl().snapshot().nodes;
    expect(nodes).toHaveLength(2);
    expect(nodes[1].file).toEqual({ path: 'src/a.ts', line: 30 });
    expect(ctrl().snapshot().focusedId).toBe(nodes[1].id);
  });

  it('a placed note starts empty and updateNote persists text to the snapshot and mirror', () => {
    const { el, ctrl } = mountCanvas();
    ctrl().placeNode('note');
    const root = el.querySelector('.canvas-root') as HTMLElement;
    root.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 400, clientY: 300 }));
    const note = ctrl().snapshot().nodes[1];
    expect(note).toMatchObject({ kind: 'note', note: { text: '' } });
    expect(el.querySelector('[data-note-node]')).not.toBeNull();
    h.invoke.mockClear();
    ctrl().updateNote(note.id, '# hi');
    expect(ctrl().snapshot().nodes[1].note).toEqual({ text: '# hi' });
    expect(syncCalls().at(-1)![1].newState.nodes[1].note).toEqual({ text: '# hi' });
  });

  it('applyLoadedLayout and applySession remap live nodes, reap orphans, and report the layout', () => {
    const layouts: string[] = [];
    const { ctrl } = mountCanvas({ onLayoutChange: (l) => layouts.push(l) });
    const live = ctrl().snapshot().nodes[0].id;
    fakeSession(live, []);
    ctrl().applyLoadedLayout({
      version: 2,
      activePreset: 'pipeline',
      nodes: [
        { ...ctrl().snapshot().nodes[0], id: 'saved-a', x: 0, y: 0, w: 300, h: 200, z: 1, index: 1 },
        { ...ctrl().snapshot().nodes[0], id: 'saved-b', x: 400, y: 0, w: 300, h: 200, z: 2, index: 2 },
      ],
      view: { x: 5, y: 6, zoom: 1 },
      focusedId: 'saved-b',
    });
    let nodes = ctrl().snapshot().nodes;
    expect(nodes.map((n) => n.id)[0]).toBe(live);
    expect(nodes).toHaveLength(2);
    expect(nodes[0]).toMatchObject({ x: 0, w: 300 });
    expect(ctrl().snapshot().view).toEqual({ x: 5, y: 6, zoom: 1 });
    expect(layouts.at(-1)).toBe('pipeline');
    expect(getPaneSession(live)).toBeDefined();

    const gone = nodes[1].id;
    fakeSession(gone, []);
    ctrl().applySession({
      version: 2,
      activePreset: null,
      canvas: { nodes: [{ ...nodes[0], id: 'only', x: 10, y: 20, w: 400, h: 300, z: 1, index: 1 }], view: { x: 0, y: 0, zoom: 1 }, focusedId: 'only' },
      panes: [{ id: 'only', scrollback: ['hello'] }],
      projectLessAccepted: true,
    });
    nodes = ctrl().snapshot().nodes;
    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe(live);
    expect(nodes[0]).toMatchObject({ x: 10, y: 20, w: 400, h: 300 });
    expect(nodes[1].id).toBe(gone);
    expect(getPaneSession(gone)).toBeDefined();
    expect(layouts.at(-1)).toBe('custom');
  });

  it('cycleLayout follows the preset order from the active layout', () => {
    const layouts: string[] = [];
    let active = 'custom';
    const { ctrl } = mountCanvas({ activeLayout: () => active as 'custom', onLayoutChange: (l) => { active = l; layouts.push(l); } });
    ctrl().splitFocused('H');
    ctrl().cycleLayout();
    ctrl().cycleLayout();
    expect(layouts.filter((l) => l !== 'custom')).toEqual(['fanout', 'pipeline']);
  });

  it('ctrl-wheel zooms around the cursor; plain wheel on the background pans; right button pans', () => {
    const { el, ctrl } = mountCanvas();
    const root = el.querySelector('.canvas-root') as HTMLElement;
    root.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, ctrlKey: true, deltaY: 500, clientX: 0, clientY: 0 }));
    expect(ctrl().snapshot().view.zoom).toBeLessThan(1);
    ctrl().zoomReset();
    root.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaX: 30, deltaY: 40 }));
    expect(ctrl().snapshot().view).toEqual({ x: -30, y: -40, zoom: 1 });
    const inside = el.querySelector('.canvas-node') as HTMLElement;
    inside.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: 40 }));
    expect(ctrl().snapshot().view).toEqual({ x: -30, y: -40, zoom: 1 });

    inside.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 2, clientX: 100, clientY: 100 }));
    expect(root.hasAttribute('data-panning')).toBe(true);
    const ctx = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });
    root.dispatchEvent(ctx);
    expect(ctx.defaultPrevented).toBe(true);
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 150, clientY: 120 }));
    window.dispatchEvent(new MouseEvent('pointerup', { clientX: 150, clientY: 120 }));
    expect(root.hasAttribute('data-panning')).toBe(false);
    expect(ctrl().snapshot().view).toEqual({ x: 20, y: -20, zoom: 1 });
  });

  it('agent config colours the chip and the minimap by role; native nodes still host a pane', () => {
    const { el, ctrl } = mountCanvas({ moveMode: true });
    ctrl().splitFocused('H');
    ctrl().splitFocused('H');
    const ids = ctrl().snapshot().nodes.map((n) => n.id);
    dispose?.();
    dispose = undefined;
    document.body.innerHTML = '';
    const session = {
      version: 2 as const,
      activePreset: null,
      canvas: {
        nodes: ids.map((id, i) => ({ id, kind: (i === 2 ? 'native' : 'terminal') as 'native' | 'terminal', x: i * 800, y: 0, w: 720, h: 440, z: i + 1, index: i + 1, cwd: '/p', shell: 'zsh' })),
        view: { x: 0, y: 0, zoom: 1 },
        focusedId: ids[0],
      },
      panes: [],
      projectLessAccepted: true,
    };
    const cfg = { [ids[0]]: { cliBinary: 'claude', cliArgs: [], sessionId: 's1' }, [ids[1]]: { cliBinary: 'gemini', cliArgs: [], sessionId: 's2' } };
    const { el: el2, ctrl: ctrl2 } = mountCanvas({ initialSession: session, agentConfigByPaneId: cfg, moveMode: true, nativeSessionByPaneId: { [ids[2]]: { sessionId: 's', sidecarId: 'c' } } });
    void el;
    expect(el2.querySelector('[data-mode-badge="move"]')).not.toBeNull();
    const mapNodes = [...el2.querySelectorAll<HTMLElement>('[data-minimap-node]')];
    expect(mapNodes.map((n) => n.style.background)).toEqual(['var(--role-planner)', 'var(--role-reviewer)', 'var(--accent-cyan)']);
    expect(el2.querySelectorAll('[data-mock-pane-id]')).toHaveLength(3);
    ctrl2().setView({ x: 0, y: 0, zoom: 0.3 });
    const chip = el2.querySelector(`[data-terminal-chip="${ids[0]}"]`) as HTMLElement;
    expect(chip.style.getPropertyValue('--chip-role')).toBe('var(--role-planner)');
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
