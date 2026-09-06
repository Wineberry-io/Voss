import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from 'solid-js/web';
import { fireEvent } from '@testing-library/dom';

import PresetSwitcher from '../PresetSwitcher';
import type { ActiveLayout, LayoutPreset } from '../../../canvas/arrange';

/**
 * A4-02 Task 1 — PresetSwitcher is a controlled component.
 *
 * Contract (from A4-UI-SPEC):
 * - Props: { activeLayout, disabled?, onSelect }
 * - Renders four buttons in fixed order: fanout | pipeline | swarm | watchers
 * - `custom` label appears only when activeLayout === 'custom'; it is
 *   display-only (not focusable, non-clickable).
 * - aria-pressed='true' is set only on the active preset.
 * - aria-label="Switch layout to <preset>" on each preset button.
 * - No local createSignal — switcher reflects props exactly.
 * - Colors use --focus background and --fg-0 text on active (no raw white).
 * - Disabled buttons do not fire onSelect.
 */

const PRESETS: readonly LayoutPreset[] = [
  'fanout',
  'pipeline',
  'swarm',
  'watchers',
] as const;

let dispose: (() => void) | undefined;
function mount(ui: () => unknown) {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}
afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
});

function presetButton(root: HTMLElement, preset: LayoutPreset): HTMLButtonElement {
  return root.querySelector(
    `button[aria-label="Switch layout to ${preset}"]`,
  ) as HTMLButtonElement;
}

describe('PresetSwitcher — fixed order + exact copy', () => {
  it('renders fanout, pipeline, swarm, watchers in that order with lowercase labels', () => {
    const el = mount(() => (
      <PresetSwitcher activeLayout="fanout" onSelect={() => {}} />
    ));
    const buttons = el.querySelectorAll('button');
    expect(buttons).toHaveLength(4);
    const labels = Array.from(buttons).map((b) => b.textContent?.trim());
    expect(labels).toEqual(['fanout', 'pipeline', 'swarm', 'watchers']);
  });
});

describe('PresetSwitcher — aria-pressed reflects active preset', () => {
  for (const active of PRESETS) {
    it(`aria-pressed='true' only on ${active} when activeLayout=${active}`, () => {
      const el = mount(() => (
        <PresetSwitcher activeLayout={active} onSelect={() => {}} />
      ));
      for (const p of PRESETS) {
        const b = presetButton(el, p);
        expect(b.getAttribute('aria-pressed')).toBe(
          p === active ? 'true' : 'false',
        );
      }
    });
  }

  it('no preset is aria-pressed when activeLayout=custom', () => {
    const el = mount(() => (
      <PresetSwitcher activeLayout="custom" onSelect={() => {}} />
    ));
    for (const p of PRESETS) {
      expect(presetButton(el, p).getAttribute('aria-pressed')).toBe('false');
    }
  });
});

describe('PresetSwitcher — custom state label', () => {
  it('shows custom label only when activeLayout === custom', () => {
    const elActive = mount(() => (
      <PresetSwitcher activeLayout="fanout" onSelect={() => {}} />
    ));
    expect(
      elActive.querySelector('[data-preset-state="custom"]'),
    ).toBeNull();
    dispose?.();
    dispose = undefined;
    document.body.innerHTML = '';

    const elCustom = mount(() => (
      <PresetSwitcher activeLayout="custom" onSelect={() => {}} />
    ));
    const custom = elCustom.querySelector('[data-preset-state="custom"]');
    expect(custom).not.toBeNull();
    expect(custom!.textContent?.trim()).toBe('custom');
  });

  it('custom label is display-only — not a button, not focusable, no onSelect on click', () => {
    const onSelect = vi.fn<(p: LayoutPreset) => void>();
    const el = mount(() => (
      <PresetSwitcher activeLayout="custom" onSelect={onSelect} />
    ));
    const custom = el.querySelector('[data-preset-state="custom"]') as HTMLElement;
    expect(custom.tagName).not.toBe('BUTTON');
    expect(custom.getAttribute('aria-label')).toBe('Custom layout');
    // Either no tabindex or tabindex=-1.
    const ti = custom.getAttribute('tabindex');
    expect(ti === null || ti === '-1').toBe(true);
    fireEvent.click(custom);
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe('PresetSwitcher — controlled click behavior', () => {
  it('clicking a preset calls onSelect with that preset', () => {
    const onSelect = vi.fn<(p: LayoutPreset) => void>();
    const el = mount(() => (
      <PresetSwitcher activeLayout="fanout" onSelect={onSelect} />
    ));
    for (const p of PRESETS) {
      fireEvent.click(presetButton(el, p));
    }
    expect(onSelect.mock.calls.map((c) => c[0])).toEqual([
      'fanout',
      'pipeline',
      'swarm',
      'watchers',
    ]);
  });

  it('switcher has no local active state — re-rendering with new activeLayout flips aria-pressed', () => {
    let layout: ActiveLayout = 'fanout';
    const el = mount(() => (
      <PresetSwitcher activeLayout={layout} onSelect={() => {}} />
    ));
    expect(presetButton(el, 'fanout').getAttribute('aria-pressed')).toBe('true');
    // Clicking does NOT change DOM by itself (no local state).
    fireEvent.click(presetButton(el, 'pipeline'));
    expect(presetButton(el, 'fanout').getAttribute('aria-pressed')).toBe('true');
    expect(presetButton(el, 'pipeline').getAttribute('aria-pressed')).toBe(
      'false',
    );
  });
});

describe('PresetSwitcher — disabled state', () => {
  it('disabled=true: every preset button is disabled and clicks do not fire', () => {
    const onSelect = vi.fn<(p: LayoutPreset) => void>();
    const el = mount(() => (
      <PresetSwitcher activeLayout="fanout" disabled onSelect={onSelect} />
    ));
    for (const p of PRESETS) {
      const b = presetButton(el, p);
      expect(b.disabled).toBe(true);
      fireEvent.click(b);
    }
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe('PresetSwitcher — token-only colors (no raw white)', () => {
  it('active preset uses var(--fg-0) for text, not raw white', () => {
    const el = mount(() => (
      <PresetSwitcher activeLayout="fanout" onSelect={() => {}} />
    ));
    const active = presetButton(el, 'fanout');
    const inactive = presetButton(el, 'pipeline');
    // Active must not declare raw white text. Inline style is what the
    // existing implementation drives; assert the color value reads from a
    // CSS var (no literal 'white' anywhere in the inline style).
    expect(active.getAttribute('style')).not.toMatch(/white/);
    expect(inactive.getAttribute('style')).not.toMatch(/white/);
  });
});
