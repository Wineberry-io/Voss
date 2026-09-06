import { For, Show } from 'solid-js';
import type {
  ActiveLayout,
  LayoutPreset,
} from '../../canvas/arrange';
import { LAYOUT_PRESETS } from '../../canvas/arrange';

/**
 * Controlled titlebar preset switcher (A4-02 Task 1, A4-UI-SPEC).
 *
 * No local state — `activeLayout` and `onSelect` are owned by App.tsx
 * (single source of truth shared with `Cmd+G` cycling and grid
 * transforms). The `custom` state label appears only when the current
 * tree is off-cycle; it is display-only (not focusable, non-clickable).
 *
 * Tokens only (no raw hex, no white): active uses `--focus` background
 * with `--fg-0` text; inactive uses transparent with `--fg-2`; custom
 * uses `--bg-3` with `--accent-amber` per UI-SPEC.
 */
export type PresetSwitcherProps = {
  activeLayout: ActiveLayout;
  disabled?: boolean;
  onSelect: (preset: LayoutPreset) => void;
};

export default function PresetSwitcher(props: PresetSwitcherProps) {
  return (
    <div
      style={{
        display: 'flex',
        'align-items': 'center',
        'flex-shrink': '0',
        'margin-right': '10px',
        gap: '6px',
        // Ensure Tauri drag-region siblings don't swallow pointer events.
        'pointer-events': 'auto',
      }}
    >
      {/*
        Custom state label — only rendered when the tree is off-cycle.
        Display-only: not a button, not focusable, no click handler.
        aria-label per UI-SPEC.
      */}
      <Show when={props.activeLayout === 'custom'}>
        <span
          data-preset-state="custom"
          aria-label="Custom layout"
          tabindex={-1}
          style={{
            background: 'var(--bg-3)',
            color: 'var(--accent-amber)',
            border: '1px solid var(--border-bright)',
            padding: '2px 8px',
            'font-family': 'var(--font-ui)',
            'font-size': '11px',
            'line-height': '1',
          }}
        >
          custom
        </span>
      </Show>

      <div
        style={{
          display: 'flex',
          border: '1px solid var(--border)',
          overflow: 'hidden',
          'flex-shrink': '0',
        }}
      >
        <For each={LAYOUT_PRESETS}>
          {(preset, i) => {
            const active = () => props.activeLayout === preset;
            const isLast = () => i() === LAYOUT_PRESETS.length - 1;
            return (
              <button
                type="button"
                aria-label={`Switch layout to ${preset}`}
                aria-pressed={active() ? 'true' : 'false'}
                disabled={props.disabled}
                onClick={() => {
                  console.log('[PresetSwitcher] click', { preset, disabled: props.disabled });
                  if (props.disabled) return;
                  props.onSelect(preset);
                }}
                style={{
                  background: active() ? 'var(--focus)' : 'transparent',
                  // Token text only — never raw white (UI-SPEC color table).
                  color: active()
                    ? 'var(--fg-0)'
                    : props.disabled
                      ? 'var(--fg-3)'
                      : 'var(--fg-2)',
                  border: 'none',
                  'border-right': isLast()
                    ? 'none'
                    : '1px solid var(--border)',
                  padding: '4px 10px',
                  'font-family': 'var(--font-ui)',
                  'font-size': '11px',
                  cursor: props.disabled ? 'default' : 'pointer',
                  'line-height': '1',
                }}
              >
                {preset}
              </button>
            );
          }}
        </For>
      </div>
    </div>
  );
}
