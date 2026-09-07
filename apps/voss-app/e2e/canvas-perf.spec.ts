import { test, expect } from '@playwright/test';
import { bootApp, stableRects } from './_helpers';

/**
 * S2 canvas perf gate (mock-IPC): 12 terminal nodes each receiving a flood of
 * PTY data through their mocked Channel while the plane pans for 5 s, at zoom
 * 1 and at zoom 0.5 (chips). Prints one JSON line per zoom for
 * scripts/test-canvas-perf.ts to assert against; the spec itself only checks
 * that frames were sampled.
 */

const NODE_COUNT = 12;
const PAN_MS = 5000;

function twelveNodeSession() {
  const nodes = Array.from({ length: NODE_COUNT }, (_, i) => ({
    id: `p${i + 1}`,
    kind: 'terminal',
    x: (i % 4) * 740,
    y: Math.floor(i / 4) * 460,
    w: 720,
    h: 440,
    z: i + 1,
    index: i + 1,
    cwd: '/tmp/voss-e2e-proj',
    shell: 'zsh',
  }));
  return {
    version: 2,
    activePreset: null,
    canvas: { nodes, view: { x: 0, y: 0, zoom: 1 }, focusedId: 'p1' },
    panes: nodes.map((n) => ({ id: n.id, scrollback: null })),
    projectLessAccepted: true,
  };
}

async function measure(page: import('@playwright/test').Page, zoom: number) {
  return page.evaluate(
    async ({ zoom, panMs }) => {
      type Chan = { onmessage: (ev: unknown) => void };
      const w = window as unknown as { __PTY_CHANNELS__: Chan[] };
      const root = document.querySelector('.canvas-root') as HTMLElement;
      const plane = document.querySelector('.canvas-plane') as HTMLElement;
      const line = Array.from(new TextEncoder().encode(`${'x'.repeat(76)}\r\n`.repeat(4)));
      const frames: number[] = [];
      const rect = root.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;

      const wheel = (dy: number) =>
        root.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, ctrlKey: true, deltaY: dy, clientX: cx, clientY: cy }));
      let guard = 0;
      while (Math.abs(Number(root.dataset.zoom) - zoom) > 0.02 && guard < 200) {
        wheel(Number(root.dataset.zoom) > zoom ? 60 : -60);
        guard += 1;
      }
      await new Promise((r) => setTimeout(r, 300));

      plane.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, button: 0, clientX: cx, clientY: cy }));
      const start = performance.now();
      let last = start;
      let x = cx;
      await new Promise<void>((resolve) => {
        const tick = () => {
          const now = performance.now();
          frames.push(now - last);
          last = now;
          for (const ch of w.__PTY_CHANNELS__) ch.onmessage({ type: 'data', bytes: line });
          x -= 6;
          window.dispatchEvent(new PointerEvent('pointermove', { clientX: x, clientY: cy + Math.sin(now / 300) * 40 }));
          if (now - start >= panMs) resolve();
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      window.dispatchEvent(new PointerEvent('pointerup', { clientX: x, clientY: cy }));
      const sorted = frames.slice(1).sort((a, b) => a - b);
      const p = (q: number) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))] ?? 0;
      return {
        zoom: Number(root.dataset.zoom),
        frames: sorted.length,
        chips: document.querySelectorAll('[data-terminal-chip]').length,
        period: Number(p(0.05).toFixed(2)),
        p50: Number(p(0.5).toFixed(2)),
        p95: Number(p(0.95).toFixed(2)),
        max: Number(sorted[sorted.length - 1]?.toFixed(2) ?? 0),
      };
    },
    { zoom, panMs: PAN_MS },
  );
}

/** Median rAF interval with no input and no PTY traffic: the display refresh period. */
async function measureIdle(page: import('@playwright/test').Page) {
  return page.evaluate(
    async (ms) =>
      new Promise<{ period: number; frames: number }>((resolve) => {
        const deltas: number[] = [];
        const start = performance.now();
        let last = start;
        const tick = () => {
          const now = performance.now();
          deltas.push(now - last);
          last = now;
          if (now - start >= ms) {
            const sorted = deltas.slice(1).sort((a, b) => a - b);
            resolve({ period: Number((sorted[Math.floor(sorted.length / 2)] ?? 0).toFixed(2)), frames: sorted.length });
          } else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }),
    1500,
  );
}

test.describe.configure({ mode: 'serial' });

test('canvas-perf: 12 flooding terminals, pan 5 s at zoom 1 and 0.5', async ({ page }) => {
  test.setTimeout(90_000);
  await bootApp(page, { session: twelveNodeSession() });
  await stableRects(page, NODE_COUNT);
  await page.waitForFunction((n) => document.querySelectorAll('.pane-body .xterm').length >= n, NODE_COUNT, { timeout: 20_000 });
  await page.waitForFunction((n) => (window as unknown as { __PTY_CHANNELS__: unknown[] }).__PTY_CHANNELS__.length >= n, NODE_COUNT);

  const idle = await measureIdle(page);
  console.log(`[canvas-perf-idle] ${JSON.stringify(idle)}`);
  expect(idle.frames).toBeGreaterThan(30);

  const atOne = await measure(page, 1);
  console.log(`[canvas-perf] ${JSON.stringify(atOne)}`);
  expect(atOne.frames).toBeGreaterThan(30);
  expect(atOne.chips).toBe(0);

  const atHalf = await measure(page, 0.5);
  console.log(`[canvas-perf] ${JSON.stringify(atHalf)}`);
  expect(atHalf.frames).toBeGreaterThan(30);
  expect(atHalf.chips).toBe(NODE_COUNT);
});
