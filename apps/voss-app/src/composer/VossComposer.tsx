// V24-04 (VADE2-04) — global "Ask Voss to…" composer.
//
// A modal <dialog> reachable from any surface (⌘K + the portal-rail ask
// trigger). On open it shows ONLY the ask field and a safety-mode control
// defaulted to "Read only" (D-04); scope / agent target / team / budget /
// attached context are collapsed behind "Advanced" (D-05). It reuses the
// existing run-intake assembler (runIntake.ts assembleRunSpec + validateAutoStart);
// the humane safety labels map to the internal RunMode (Read only→Plan,
// Can edit→Edit, Autopilot→Auto) — code identifiers unchanged (D-09).
//
// Focus discipline (RESEARCH Pitfall 7): on open focus the ask textarea; a Tab
// trap keeps focus inside the dialog so Tab cannot reach a focused xterm pane
// behind the overlay. Escape closes; ⌘Enter creates; bare Enter inserts a
// newline (terminal-dense app — never auto-submits).

import { type Component, createEffect, createSignal, For, Show } from 'solid-js';
import './composer.css';
import { devlog } from '../devlog';
import {
  assembleRunSpec,
  validateAutoStart,
  type RunMode,
  type RunSpec,
  type RunTarget,
} from '../org/cockpit/runIntake';

export interface VossComposerProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (spec: RunSpec) => void | Promise<void>;
  allowedTargets?: readonly RunTarget[];
}

type SafetyMode = 'Read only' | 'Can edit' | 'Autopilot';

const SAFETY_MODES: SafetyMode[] = ['Read only', 'Can edit', 'Autopilot'];

// Humane safety label → internal RunMode (D-09: identifiers never surface).
const SAFETY_TO_RUNMODE: Record<SafetyMode, RunMode> = {
  'Read only': 'Plan',
  'Can edit': 'Edit',
  Autopilot: 'Auto',
};

const TEAMS = ['solo', 'core', 'review'];

// Advanced "agent target" maps to RunTarget; D-10 humane labels (no internal
// "native" vocabulary in UI strings).
const TARGETS: { id: RunTarget; label: string }[] = [
  { id: 'native', label: 'Voss run' },
  { id: 'terminal', label: 'Terminal agent' },
];

const VossComposer: Component<VossComposerProps> = (props) => {
  const [goal, setGoal] = createSignal('');
  const [safety, setSafety] = createSignal<SafetyMode>('Read only');
  const [advancedOpen, setAdvancedOpen] = createSignal(false);
  const [scope, setScope] = createSignal('');
  const [budget, setBudget] = createSignal('');
  const [team, setTeam] = createSignal('solo');
  const targetOptions = () =>
    TARGETS.filter((target) =>
      props.allowedTargets ? props.allowedTargets.includes(target.id) : true,
    );
  const [target, setTarget] = createSignal<RunTarget>(
    props.allowedTargets?.[0] ?? 'native',
  );
  const [contextPath, setContextPath] = createSignal('');
  const [error, setError] = createSignal<string | null>(null);

  let askRef: HTMLTextAreaElement | undefined;
  let dialogRef: HTMLDialogElement | undefined;

  // On open: clear transient error and focus the ask field (RESEARCH Pitfall 7).
  createEffect(() => {
    if (props.open) {
      setError(null);
      queueMicrotask(() => askRef?.focus());
    }
  });

  const canCreate = () => goal().trim().length > 0;

  const buildState = () => {
    const b = budget().trim();
    return {
      goal: goal().trim(),
      mode: SAFETY_TO_RUNMODE[safety()],
      team: team(),
      scope: scope().trim() || undefined,
      budget: b ? Number(b) : undefined,
      target: target(),
    };
  };

  const handleCreate = async () => {
    if (!canCreate()) return;
    setError(null);
    const state = buildState();
    devlog('info', 'composer.create', 'clicked', {
      mode: state.mode,
      team: state.team,
      target: state.target,
      hasScope: Boolean(state.scope),
      goalLen: state.goal.length,
    });
    // Autopilot ("Auto") must pass the run-intake gate before dispatch.
    const gate = validateAutoStart(state);
    if (!gate.ok) {
      devlog('warn', 'composer.create', 'gate blocked', { reason: gate.reason });
      setError(gate.reason ?? 'Cannot create Task.');
      return;
    }
    const spec = assembleRunSpec(state);
    try {
      await props.onCreated?.(spec);
    } catch (e) {
      devlog('error', 'composer.create', 'onCreated threw', e);
      setError(e instanceof Error ? e.message : 'Could not start the Task.');
      return;
    }
    devlog('info', 'composer.create', 'dispatched ok');
    props.onClose();
  };

  const onDialogKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      props.onClose();
      return;
    }
    // ⌘Enter creates; bare Enter is left to the textarea (newline).
    if (e.key === 'Enter' && e.metaKey) {
      e.preventDefault();
      handleCreate();
      return;
    }
    // Tab trap — keep focus within the dialog (Pitfall 7).
    if (e.key === 'Tab' && dialogRef) {
      const focusables = Array.from(
        dialogRef.querySelectorAll<HTMLElement>(
          'button:not([disabled]), textarea, select, input, [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  return (
    <Show when={props.open}>
      <div
        class="composer-backdrop"
        onClick={(e) => {
          if (e.target === e.currentTarget) props.onClose();
        }}
      >
        <dialog
          ref={dialogRef}
          class="composer-dialog"
          aria-label="Ask Voss to create a Task"
          aria-modal="true"
          open
          onKeyDown={onDialogKeyDown}
          onClose={() => props.onClose()}
        >
          <div class="composer-titlerow">
            <span class="composer-title">
              <span class="composer-glyph" aria-hidden="true">
                ❯
              </span>{' '}
              Ask Voss to…
            </span>
            <span class="composer-kbd" aria-hidden="true">
              ⌘K
            </span>
          </div>

          <textarea
            ref={askRef}
            class="composer-ask"
            aria-required="true"
            aria-label="Ask"
            placeholder="Describe what you want Voss to do..."
            value={goal()}
            onInput={(e) => setGoal(e.currentTarget.value)}
          />

          <div class="composer-controls">
            <label class="composer-kv">
              <span class="composer-kv__key">Safety</span>
              <select
                class="composer-select"
                aria-label="Safety mode"
                value={safety()}
                onChange={(e) => setSafety(e.currentTarget.value as SafetyMode)}
              >
                <For each={SAFETY_MODES}>{(m) => <option value={m}>{m}</option>}</For>
              </select>
            </label>

            <div class="composer-controls__right">
              <button
                type="button"
                class="composer-advanced-toggle"
                aria-expanded={advancedOpen() ? 'true' : 'false'}
                aria-controls="advanced-panel"
                onClick={() => setAdvancedOpen((o) => !o)}
              >
                {advancedOpen() ? 'Advanced ▾' : 'Advanced ▸'}
              </button>
              <button
                type="button"
                class="composer-create"
                disabled={!canCreate()}
                onClick={handleCreate}
              >
                Create Task
              </button>
            </div>
          </div>

          <Show when={advancedOpen()}>
            <div id="advanced-panel" class="composer-advanced">
              <label class="composer-field">
                <span class="composer-field__key">Scope</span>
                <input
                  class="composer-input"
                  aria-label="Scope"
                  placeholder="Scope (paths, patterns)..."
                  value={scope()}
                  onInput={(e) => setScope(e.currentTarget.value)}
                />
              </label>
              <label class="composer-field">
                <span class="composer-field__key">Agent</span>
                <select
                  class="composer-select"
                  aria-label="Agent target"
                  value={target()}
                  onChange={(e) => setTarget(e.currentTarget.value as RunTarget)}
                >
                  <For each={targetOptions()}>{(t) => <option value={t.id}>{t.label}</option>}</For>
                </select>
              </label>
              <label class="composer-field">
                <span class="composer-field__key">Team</span>
                <select
                  class="composer-select"
                  aria-label="Team"
                  value={team()}
                  onChange={(e) => setTeam(e.currentTarget.value)}
                >
                  <For each={TEAMS}>{(t) => <option value={t}>{t}</option>}</For>
                </select>
              </label>
              <label class="composer-field">
                <span class="composer-field__key">Budget</span>
                <input
                  class="composer-input composer-input--budget"
                  type="number"
                  min="0"
                  aria-label="Budget"
                  placeholder="$"
                  value={budget()}
                  onInput={(e) => setBudget(e.currentTarget.value)}
                />
              </label>
              <label class="composer-field">
                <span class="composer-field__key">Context</span>
                <input
                  class="composer-input"
                  aria-label="Attach context"
                  placeholder="Attach context file..."
                  value={contextPath()}
                  onInput={(e) => setContextPath(e.currentTarget.value)}
                />
              </label>
            </div>
          </Show>

          <Show when={error()}>
            <span class="composer-error" role="alert">
              {error()}
            </span>
          </Show>
        </dialog>
      </div>
    </Show>
  );
};

export default VossComposer;
