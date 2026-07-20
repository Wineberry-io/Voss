// VCKP-03 — RunCommandBar (D-03): an always-on top intake strip mounted above
// the 4-region cockpit grid. It is the universal run-intake keystone (closes
// G2): one bar that starts BOTH run types from the same captured context.
//
// V24 vocabulary (D-11): humane safety labels (Read only / Can edit / Autopilot)
// replace exposed Plan/Edit/Auto toggles. Scope stays inline; team / budget /
// run target fold behind a Details disclosure (D-05 pattern).
//
// Two start paths (config-assembly mirrors AgentLaunchModal.buildConfig):
//   Bridge B (terminal): registerTerminalCard(paneId) mints the cardId, then
//     spawnAgent({..., sessionId: cardId, paneId}) — the cardId rides through as
//     the spawn_agent `sessionId` arg (zero Rust change). mode/team/scope/budget
//     are encoded into cliArgs so the launch carries the full intake context.
//   Bridge A (native): the injected V13.1 client's createSession(spec) returns
//     {id}; registerNativeCard(id, id) stores it (the create-response id IS the
//     snapshot node id — A1 finding). The client is GATED/mock in V14: when no
//     client is injected the native path is a disabled-with-reason no-op.
//
// Autopilot gating follows the decisionActions disabled-with-reason discipline:
// an Autopilot start missing budget OR scope renders the reason INLINE and calls
// NO start path (never a silent no-op).
//
// Styling: A12 tokens only via runCommandBar.css.

import { type Component, createMemo, createSignal, For, Show } from 'solid-js';
import { invoke } from '@tauri-apps/api/core';
import './runCommandBar.css';
import {
  assembleRunSpec,
  validateAutoStart,
  type RunMode,
  type RunSpec,
  type RunTarget,
} from './runIntake';
import { registerTerminalCard, registerNativeCard } from '../model/bridge';

/** Minimal V13.1-client surface RunCommandBar consumes (mock-injectable). */
export interface RunNativeClient {
  createSession(spec: RunSpec): Promise<{ id: string }>;
}

/**
 * Default terminal launcher: invokes the existing `spawn_agent` Tauri command
 * directly with the minted cardId as the `sessionId` arg (Bridge B). Mirrors
 * pty-ipc.ts `spawnAgent` payload shape so the launch is wired identically to
 * the pane path. Injectable so the test can assert the call without a real PTY.
 */
export type SpawnAgentFn = (o: {
  cliBinary: string;
  cliArgs: string[];
  taskPrompt: string;
  sessionId: string;
  paneId: string;
  cwd?: string;
}) => Promise<unknown>;

const defaultSpawnAgent: SpawnAgentFn = (o) =>
  invoke('spawn_agent', {
    cliBinary: o.cliBinary,
    cliArgs: o.cliArgs,
    sessionId: o.sessionId,
    paneId: o.paneId,
    cwd: o.cwd,
  });

/** Deps the run dispatch needs, independent of any one intake surface. */
export interface DispatchDeps {
  cliBinary: string;
  cwd?: string;
  /** Native (Voss harness) client. Native dispatch throws if absent. */
  client?: RunNativeClient;
  spawnAgent?: SpawnAgentFn;
  resolvePaneId?: () => string;
}

/**
 * Shared run dispatch for every intake surface (RunCommandBar + VossComposer).
 * Performs the side-effects (mint card, spawn/createSession) and THROWS on
 * failure; callers own UI feedback. Caller must pass a gate-passed spec
 * (validateAutoStart) — this does not re-gate.
 */
export async function dispatchRunSpec(
  spec: RunSpec,
  deps: DispatchDeps,
): Promise<void> {
  if (spec.target === 'terminal') {
    const paneId = (deps.resolvePaneId ?? (() => crypto.randomUUID()))();
    const cardId = registerTerminalCard(paneId);
    const spawn = deps.spawnAgent ?? defaultSpawnAgent;
    await spawn({
      cliBinary: deps.cliBinary,
      cliArgs: intakeCliArgs(spec),
      taskPrompt: spec.goal,
      sessionId: cardId,
      paneId,
      cwd: deps.cwd,
    });
    return;
  }
  if (!deps.client) {
    throw new Error(
      'Voss runs need the Voss server — not available in this build.',
    );
  }
  const response = await deps.client.createSession(spec);
  registerNativeCard(response.id, response.id);
}

export interface RunCommandBarProps {
  cwd: string;
  cliBinary: string;
  /** Native (Voss harness) client — GATED/mock in V14. Native path is a
   *  disabled-with-reason no-op when undefined. */
  client?: RunNativeClient;
  /** Terminal launch fn (Bridge B). Defaults to a direct spawn_agent invoke. */
  spawnAgent?: SpawnAgentFn;
  /** Pane id for the terminal launch. The cockpit has no active pane bound to
   *  the bar, so a fresh pane id is minted per run by default (mirrors
   *  PaneComponent using props.id as paneId). */
  resolvePaneId?: () => string;
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

const SAFETY_CLASS: Record<SafetyMode, string> = {
  'Read only': 'run-bar__safety--read-only',
  'Can edit': 'run-bar__safety--can-edit',
  Autopilot: 'run-bar__safety--autopilot',
};

// D-10 copy rule: internal-mechanics vocabulary (incl. "Voss-native") never
// surfaces in UI strings — the native target reads "Voss run".
const TARGETS: { id: RunTarget; label: string }[] = [
  { id: 'native', label: 'Voss run' },
  { id: 'terminal', label: 'Terminal agent' },
];
const TEAMS = ['solo', 'core', 'review'];

/**
 * Encode the intake context into CLI args so the terminal launch carries
 * mode/team/scope/budget (mirrors AgentLaunchModal.buildConfig arg assembly).
 */
function intakeCliArgs(spec: RunSpec): string[] {
  const args: string[] = ['--mode', spec.mode, '--team', spec.team];
  if (spec.scope) args.push('--scope', spec.scope);
  if (spec.budget != null) args.push('--budget', String(spec.budget));
  return args;
}

const RunCommandBar: Component<RunCommandBarProps> = (props) => {
  const [goal, setGoal] = createSignal('');
  const [safety, setSafety] = createSignal<SafetyMode>('Read only');
  const [team, setTeam] = createSignal<string>('solo');
  const [scope, setScope] = createSignal('');
  const [budget, setBudget] = createSignal('');
  const targetOptions = () =>
    TARGETS.filter((target) =>
      props.allowedTargets ? props.allowedTargets.includes(target.id) : true,
    );
  const [target, setTarget] = createSignal<RunTarget>(
    props.allowedTargets?.[0] ?? 'native',
  );
  const [detailsOpen, setDetailsOpen] = createSignal(false);
  const [contextAttached, setContextAttached] = createSignal(false);
  const [blockReason, setBlockReason] = createSignal<string | null>(null);
  const [startedMsg, setStartedMsg] = createSignal<string | null>(null);
  let startedTimer: ReturnType<typeof setTimeout> | undefined;
  const flashStarted = (msg: string) => {
    setStartedMsg(msg);
    clearTimeout(startedTimer);
    startedTimer = setTimeout(() => setStartedMsg(null), 2000);
  };

  const canStart = createMemo(() => goal().trim().length > 0);

  const currentSpec = (): RunSpec => {
    const b = budget().trim();
    return assembleRunSpec({
      goal: goal().trim(),
      mode: SAFETY_TO_RUNMODE[safety()],
      team: team(),
      scope: scope().trim() || undefined,
      budget: b ? Number(b) : undefined,
      target: target(),
    });
  };

  const handleStart = async () => {
    if (!canStart()) return;
    setBlockReason(null);
    const spec = currentSpec();

    const gate = validateAutoStart(spec);
    if (!gate.ok) {
      setBlockReason(gate.reason ?? 'Cannot start.');
      return;
    }

    try {
      await dispatchRunSpec(spec, {
        cliBinary: props.cliBinary,
        cwd: props.cwd,
        client: props.client,
        spawnAgent: props.spawnAgent,
        resolvePaneId: props.resolvePaneId,
      });
    } catch (e) {
      setBlockReason(e instanceof Error ? e.message : String(e));
      return;
    }
    flashStarted('Task started');
  };

  return (
    <div class="run-command-bar" role="region" aria-label="Task intake">
      {/* Row 1 — dominant ask field */}
      <div class="run-bar__row run-bar__row--goal">
        <div class="run-bar__goal">
          <span class="run-bar__goal-icon" aria-hidden="true">
            ▸
          </span>
          <input
            class="run-bar__goal-input"
            placeholder="What should Voss work on?"
            value={goal()}
            onInput={(e) => setGoal(e.currentTarget.value)}
            aria-label="Task goal"
          />
        </div>
      </div>

      {/* Row 2 — scope · safety · details · start */}
      <div class="run-bar__row run-bar__row--controls">
        <label class="run-bar__scope">
          <span class="run-bar__scope-prefix">In</span>
          <input
            class="run-bar__scope-input"
            placeholder="e.g. tests/**"
            value={scope()}
            onInput={(e) => setScope(e.currentTarget.value)}
            aria-label="Scope"
          />
        </label>

        <span class="run-bar__sep" aria-hidden="true">
          ·
        </span>

        <select
          class={`run-bar__safety ${SAFETY_CLASS[safety()]}`}
          aria-label="Safety mode"
          value={safety()}
          onChange={(e) => setSafety(e.currentTarget.value as SafetyMode)}
        >
          <For each={SAFETY_MODES}>{(m) => <option value={m}>{m}</option>}</For>
        </select>

        <span class="run-bar__sep" aria-hidden="true">
          ·
        </span>

        <button
          type="button"
          class="run-bar__details-toggle"
          aria-expanded={detailsOpen() ? 'true' : 'false'}
          aria-controls="run-bar-details-panel"
          onClick={() => setDetailsOpen((o) => !o)}
        >
          {detailsOpen() ? 'Details ▾' : 'Details ▸'}
        </button>

        <button
          type="button"
          class="run-bar__start"
          disabled={!canStart()}
          onClick={() => void handleStart()}
          aria-label="Start Task"
        >
          Start ↵
        </button>
      </div>

      {/* Row 3 — optional details panel */}
      <Show when={detailsOpen()}>
        <div id="run-bar-details-panel" class="run-bar__details">
          <label class="run-bar__detail-field">
            <span class="run-bar__detail-key">team</span>
            <select
              class="run-bar__detail-select"
              value={team()}
              onChange={(e) => setTeam(e.currentTarget.value)}
              aria-label="Team"
            >
              <For each={TEAMS}>{(t) => <option value={t}>{t}</option>}</For>
            </select>
          </label>

          <label class="run-bar__detail-field">
            <span class="run-bar__detail-key">budget</span>
            <input
              class="run-bar__detail-input run-bar__detail-input--budget"
              type="number"
              min="0"
              placeholder="$"
              value={budget()}
              onInput={(e) => setBudget(e.currentTarget.value)}
              aria-label="Budget"
            />
          </label>

          <div class="run-bar__group" aria-label="Run target">
            <div class="run-bar__seg">
              <For each={targetOptions()}>
                {(t) => (
                  <button
                    type="button"
                    class={`run-bar__seg-btn${t.id === 'native' ? ' run-bar__seg-btn--native' : ''}${target() === t.id ? ' run-bar__seg-btn--active' : ''}`}
                    onClick={() => setTarget(t.id)}
                  >
                    {t.label}
                  </button>
                )}
              </For>
            </div>
          </div>

          <button
            type="button"
            class={`run-bar__attach${contextAttached() ? ' run-bar__attach--on' : ''}`}
            onClick={() => setContextAttached((v) => !v)}
            aria-pressed={contextAttached()}
            aria-label="Attach context"
          >
            {contextAttached() ? '✓ ctx' : '+ ctx'}
          </button>
        </div>
      </Show>

      <Show when={blockReason()}>
        <span class="run-bar__reason" role="alert">
          {blockReason()}
        </span>
      </Show>

      <Show when={startedMsg()}>
        <span class="run-bar__started" role="status">
          {startedMsg()}
        </span>
      </Show>
    </div>
  );
};

export default RunCommandBar;
