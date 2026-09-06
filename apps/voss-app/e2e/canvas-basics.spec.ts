import { test, expect } from '@playwright/test';
import { bootApp, paneRects, stableRects } from './_helpers';

/**
 * S1 canvas end-to-end (mock-IPC): free nodes, keyboard focus, close/respawn,
 * pan/zoom, v1 session migration, arrangements.
 */

test.describe.configure({ mode: 'serial' });

const BROWSER =
  (process.env.PW_BROWSER as 'chromium' | 'webkit' | 'firefox') ?? 'chromium';
test.use({ browserName: BROWSER });

const FOCUSED = '.grid-pane-leaf--focused';

function v1Session(count: number) {
  const leaf = (id: string, index: number) => ({ kind: 'pane', id, cwd: '/tmp/voss-e2e-proj', shell: 'zsh', index });
  let root: unknown = leaf('p1', 1);
  for (let i = 2; i <= count; i += 1) {
    root = { kind: 'split', orientation: i % 2 === 0 ? 'H' : 'V', ratio: 0.5, left: root, right: leaf(`p${i}`, i) };
  }
  return {
    version: 1,
    activePreset: null,
    grid: { root, focusedId: 'p1' },
    panes: Array.from({ length: count }, (_, i) => ({ id: `p${i + 1}`, scrollback: i === 0 ? ['restored line'] : null })),
    projectLessAccepted: true,
  };
}

test.describe('S1 canvas (mock-IPC)', () => {
  test('canvas-ac7: boots to one node at the world origin', async ({ page }) => {
    await bootApp(page);
    await expect(page.locator('[data-pane-id]')).toHaveCount(1);
    await expect(page.locator('.canvas-root')).toHaveAttribute('data-zoom', '1.00');
    const transform = await page.locator('[data-pane-id]').first().evaluate((el) => (el as HTMLElement).style.transform);
    expect(transform).toBe('translate(0px, 0px)');
  });

  test('canvas-ac3: ⌘D places a same-size node to the right, ⌘⇧D below', async ({ page }) => {
    await bootApp(page);
    await page.keyboard.press('Meta+KeyD');
    let rects = await stableRects(page, 2);
    expect(rects[1].x).toBeGreaterThan(rects[0].x + rects[0].w - 1);
    expect(Math.round(rects[1].y)).toBe(Math.round(rects[0].y));
    expect(Math.round(rects[1].w)).toBe(Math.round(rects[0].w));
    await expect(page.locator(FOCUSED)).toHaveAttribute('data-pane-id', rects[1].id);

    await page.keyboard.press('Meta+Shift+KeyD');
    rects = await stableRects(page, 3);
    const below = rects.find((r) => r.y > rects[0].y + 10)!;
    expect(below).toBeTruthy();
    expect(Math.round(below.x)).toBe(Math.round(rects[1].x));
  });

  test('canvas-ac2: ⌘1..⌘3 focus by reading order; ⌘[ ⌘] wrap', async ({ page }) => {
    await bootApp(page);
    await page.keyboard.press('Meta+KeyD');
    await page.keyboard.press('Meta+KeyD');
    const rects = await stableRects(page, 3);
    const ids = rects.map((r) => r.id);
    await page.keyboard.press('Meta+Digit2');
    await expect(page.locator(FOCUSED)).toHaveAttribute('data-pane-id', ids[1]);
    await page.keyboard.press('Meta+Digit1');
    await expect(page.locator(FOCUSED)).toHaveAttribute('data-pane-id', ids[0]);
    await page.keyboard.press('Meta+BracketLeft');
    await expect(page.locator(FOCUSED)).toHaveAttribute('data-pane-id', ids[2]);
    await page.keyboard.press('Meta+BracketRight');
    await expect(page.locator(FOCUSED)).toHaveAttribute('data-pane-id', ids[0]);
    await expect(page.locator(FOCUSED)).toHaveCount(1);
  });

  test('canvas-ac7b: closing the last node respawns a fresh one', async ({ page }) => {
    await bootApp(page);
    const before = (await paneRects(page))[0].id;
    await page.keyboard.press('Meta+KeyW');
    await expect(page.locator('[data-pane-id]')).toHaveCount(1);
    const after = (await paneRects(page))[0].id;
    expect(after).not.toBe(before);
  });

  test('canvas-ac1: a v1 three-pane session migrates to three nodes with a restore banner', async ({ page }) => {
    await bootApp(page, { session: v1Session(3) });
    const rects = await stableRects(page, 3);
    expect(rects.map((r) => r.id).sort()).toEqual(['p1', 'p2', 'p3']);
    await expect(page.locator('[data-testid="restore-banner"]')).toContainText('1 lines');
    const syncs = await page.evaluate(() => (window as unknown as { __SYNCS__: { nodes?: unknown[] }[] }).__SYNCS__);
    const last = syncs.filter((s) => s && Array.isArray(s.nodes)).at(-1)!;
    expect(last.nodes).toHaveLength(3);
  });

  test('canvas-ac5: ⌘0 resets zoom after a ctrl-wheel zoom; ⌘⇧0 fits', async ({ page }) => {
    await bootApp(page);
    await page.keyboard.press('Meta+KeyD');
    await stableRects(page, 2);
    const root = page.locator('.canvas-root');
    const box = (await root.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.keyboard.down('Control');
    await page.mouse.wheel(0, 600);
    await page.keyboard.up('Control');
    await expect.poll(async () => Number(await root.getAttribute('data-zoom'))).toBeLessThan(1);
    await page.keyboard.press('Meta+Digit0');
    await expect(root).toHaveAttribute('data-zoom', '1.00');
    await page.keyboard.press('Meta+Shift+Digit0');
    await expect.poll(async () => Number(await root.getAttribute('data-zoom'))).toBeLessThanOrEqual(1);
    await expect(page.locator('[data-pane-id]')).toHaveCount(2);
  });

  test('canvas-ac6: ⌘G cycles arrangements without changing node ids', async ({ page }) => {
    await bootApp(page);
    await page.keyboard.press('Meta+KeyD');
    await page.keyboard.press('Meta+KeyD');
    const before = (await stableRects(page, 3)).map((r) => r.id).sort();
    for (let i = 0; i < 4; i += 1) await page.keyboard.press('Meta+KeyG');
    const after = (await stableRects(page, 3)).map((r) => r.id).sort();
    expect(after).toEqual(before);
    await page.keyboard.press('Meta+Equal');
    await expect(page.locator('[data-pane-id]')).toHaveCount(3);
  });
});
