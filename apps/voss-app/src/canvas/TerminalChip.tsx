import { For, Show, createSignal, onCleanup, onMount } from 'solid-js';
import BudgetBar from '../grid/BudgetBar';
import type { BudgetState } from '../pane/pty-ipc';
import { getPaneSession, type DotState } from '../pane/paneSessionRegistry';
import { paneSessionTitle } from '../grid/PaneHeader';
import { lastLines } from './lod';

const REFRESH_MS = 1000;

/**
 * Low-detail stand-in for a terminal node below the LOD zoom: process name,
 * status dot, the last three buffer lines, and the budget bar. The live
 * xterm stays in the pane session registry, detached from layout.
 */
export default function TerminalChip(props: {
  paneId: string;
  cwd: string;
  shell: string;
  process?: string;
  budget?: BudgetState;
  roleColor?: string;
}) {
  const [lines, setLines] = createSignal<string[]>([]);
  const [dot, setDot] = createSignal<DotState>('loading');

  const refresh = () => {
    const s = getPaneSession(props.paneId);
    if (!s) return;
    setDot(s.dot);
    setLines(lastLines(s.term.buffer.active));
  };

  let timer: ReturnType<typeof setInterval> | undefined;
  onMount(() => {
    refresh();
    timer = setInterval(refresh, REFRESH_MS);
  });
  onCleanup(() => {
    if (timer) clearInterval(timer);
  });

  return (
    <div class="terminal-chip" data-terminal-chip={props.paneId} style={{ '--chip-role': props.roleColor ? `var(${props.roleColor})` : 'var(--fg-3)' }}>
      <div class="terminal-chip__head">
        <span class={`terminal-chip__dot terminal-chip__dot--${dot()}`} aria-hidden="true">●</span>
        <span class="terminal-chip__title">{paneSessionTitle(props.process, props.cwd, props.shell)}</span>
      </div>
      <div class="terminal-chip__lines">
        <For each={lines()}>{(line) => <div class="terminal-chip__line">{line}</div>}</For>
      </div>
      <Show when={props.budget}>
        {(b) => (
          <div class="terminal-chip__budget">
            <BudgetBar budget={b()} onClickDetail={() => {}} />
          </div>
        )}
      </Show>
    </div>
  );
}
