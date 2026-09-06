import { test, expect } from '@playwright/test';
import { bootApp, stableRects } from './_helpers';

/**
 * S2 canvas end-to-end (mock-IPC): snap guides, low-detail chips, note and
 * file nodes.
 */

test.describe.configure({ mode: 'serial' });

const FOCUSED = '.grid-pane-leaf--focused';

function session(count: number) {
  const nodes = Array.from({ length: count }, (_, i) => ({
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

test.describe('S2 canvas nodes (mock-IPC)', () => {
  test('canvas-s2-ac1: dragging a node near another shows a snap guide', async ({ page }) => {
    await bootApp(page);
    await page.keyboard.press('Meta+KeyD');
    const rects = await stableRects(page, 2);
    const header = page.locator(`[data-pane-id="${rects[1].id}"] .pane-header-bar`);
    const box = (await header.boundingBox())!;
    const hx = box.x + 120;
    const hy = box.y + box.height / 2;
    await page.mouse.move(hx, hy);
    await page.mouse.down();
    await page.mouse.move(hx - 200, hy + 300, { steps: 6 });
    await page.mouse.move(hx - 13, hy + 300, { steps: 6 });
    await expect(page.locator('[data-guide="x"]')).toHaveCount(1);
    await page.mouse.up();
    await expect(page.locator('[data-guide]')).toHaveCount(0);
    const after = await stableRects(page, 2);
    const a = after.find((r) => r.id === rects[0].id)!;
    const b = after.find((r) => r.id === rects[1].id)!;
    expect(Math.round(b.x)).toBe(Math.round(a.x + a.w));
  });

  test('canvas-s2-ac2: twelve nodes become chips below zoom 0.6 and come back as terminals', async ({ page }) => {
    await bootApp(page, { session: session(12) });
    await stableRects(page, 12);
    const root = page.locator('.canvas-root');
    const box = (await root.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.keyboard.down('Control');
    for (let i = 0; i < 12; i += 1) await page.mouse.wheel(0, 300);
    await page.keyboard.up('Control');
    await expect.poll(async () => Number(await root.getAttribute('data-zoom'))).toBeLessThan(0.6);
    await expect(page.locator('[data-terminal-chip]')).toHaveCount(12);
    await expect(page.locator('.pane-body .xterm')).toHaveCount(0);
    await page.keyboard.press('Meta+Digit0');
    await expect(root).toHaveAttribute('data-zoom', '1.00');
    await expect(page.locator('[data-terminal-chip]')).toHaveCount(0);
    await expect(page.locator('.pane-body .xterm')).toHaveCount(12);
    const syncs = await page.evaluate(() => (window as unknown as { __PTY_CHANNELS__: unknown[] }).__PTY_CHANNELS__.length);
    expect(syncs).toBe(12);
  });

  test('canvas-s2-ac6: a note placed with ⌘⇧N keeps its text and renders a preview when unfocused', async ({ page }) => {
    await bootApp(page);
    await page.keyboard.press('Meta+Shift+KeyN');
    await expect(page.locator('[data-placement-ghost="note"]')).toHaveCount(1);
    const root = page.locator('.canvas-root');
    const box = (await root.boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.75, box.y + box.height * 0.7);
    await expect(page.locator('[data-note-node]')).toHaveCount(1);
    const editor = page.locator('[data-note-editor] .cm-content');
    await expect(editor).toBeVisible();
    await editor.click();
    await page.keyboard.type('# Plan');
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await page.keyboard.type('- ship S2');
    await expect
      .poll(async () => {
        const syncs = await page.evaluate(() => (window as unknown as { __SYNCS__: { nodes?: { note?: { text: string } }[] }[] }).__SYNCS__);
        return syncs.filter((s) => s && Array.isArray(s.nodes)).at(-1)?.nodes?.find((n) => n.note)?.note?.text ?? '';
      })
      .toContain('ship S2');
    await page.keyboard.press('Meta+Digit1');
    await expect(page.locator('[data-note-preview] h1')).toHaveText('Plan');
    await expect(page.locator('[data-note-preview] li')).toHaveText('ship S2');
  });

  test('canvas-s2-file: quick open lists workspace files and opens a read-only file node', async ({ page }) => {
    await bootApp(page, {
      commandOverrides: {
        list_dir: [{ name: 'src', is_dir: true, children: [{ name: 'main.ts', is_dir: false }] }],
      },
    });
    await page.keyboard.press('Meta+KeyP');
    await page.keyboard.type('main.ts');
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-file-node="src/main.ts"]')).toHaveCount(1);
    await expect(page.locator('[data-file-editor] .cm-content')).toContainText('export const x = 1;');
    await expect(page.locator(FOCUSED)).toHaveCount(1);
    await expect(page.locator(`${FOCUSED} .pane-header-bar`)).toContainText('src/main.ts');
  });
});
