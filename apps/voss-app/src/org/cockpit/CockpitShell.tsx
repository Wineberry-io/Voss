// VCKP-05 — integrated Run cockpit (D-01/D-02/D-08), recomposed in V14 chunk B
// to the cockpit mockup (.planning/sketches/V14-cockpit-mockup.html):
//
//   [team sidebar 252px] | [main: run header + board + horizontal timeline] |
//   [card drawer 372px]  with the gate bar (38px) spanning the bottom.
//
// The run-load + run-picker logic and the loading/error <Show> wrappers are
// LIFTED from OrgViewShell (now folded into the run header row so the picker /
// refresh / "← Grid" controls stay reachable in every load state). The
// ORG_TABS/activeTab tab machinery stays dropped (D-01/D-02).
//
// Five regions, driven by ONE global selection (../selection):
//   1. Team sidebar         — CockpitSidebar (roster / external agents / lineage)
//   2. Board                — BoardPanel (rich cards, onCardSelect)
//   3. Horizontal timeline  — TimelineRail (run milestones, node per card)
//   4. Card detail drawer   — CardDrawer (persistent, curated sections)
//   5. Bottom gate bar      — GateBar
// Selecting a card once updates board+drawer+rail+gate (single-selection
// acceptance, cockpit.test.tsx).

import {
  createSignal,
  createEffect,
  onMount,
  onCleanup,
  Show,
  For,
  type Component,
} from 'solid-js';
import './cockpitStyles.css';
import {
  runData,
  runEntries,
  loadError,
  loading,
  currentRunId,
  loadRun,
  enumerateRuns,
  refreshRun,
} from '../orgStore';
import { selectedCardId, setSelectedCardId } from '../selection';
import type { FollowUpClient } from '../feedbackWritePath';
import type { SidecarVossClient } from '../live/sidecarClient';
import { liveLabel } from '../live/sseClient';
import { cardsFromRunData } from '../boardDerive';
import { reconcileSwarm, type SwarmReconcileResult } from '../swarmReconcile';
import BoardPanel from '../panels/BoardPanel';
import CockpitSidebar from './CockpitSidebar';
import TimelineRail from './TimelineRail';
import CardDrawer from './CardDrawer';
import GateBar from './GateBar';

function shortRunId(id: string | null): string {
  if (!id) return '—';
  return id.length > 12 ? `${id.slice(0, 12)}…` : id;
}

const CockpitShell: Component<{
  cwd: string;
  cliBinary: string;
  onClose: () => void;
  /** V15-02: live follow-up write client, forwarded to the CardDrawer. */
  followUpClient?: FollowUpClient;
  /** V15-05: live sidecar client for the sidebar "Server sessions" section. */
  vossClient?: SidecarVossClient;
  /** V15-05: Attach action — App attachSession/openAttachedPane seam. */
  onAttach?: (sessionId: string) => void;
}> = (props) => {
  const [pickerOpen, setPickerOpen] = createSignal(false);
  const [swarmManifest, setSwarmManifest] = createSignal<unknown>(null);

  // VCKP-07 (GATED A13, best-effort): the swarm roster derives from the A13
  // .voss/swarm/manifest.json. reconcileSwarm is null-tolerant, so absence of a
  // manifest yields empty roster/cards and the sidebar section stays unrendered.
  const swarm = (): SwarmReconcileResult =>
    reconcileSwarm(swarmManifest() as any);

  let pickerRef: HTMLDivElement | undefined;
  let railRef: HTMLDivElement | undefined;

  // UI-REVIEW 6a: the timeline rail REACTS to the global selection — selecting
  // a board card highlights the matching timeline node. The rail's per-card
  // nodes carry data-node-id (TimelineRail), the same hook the old vertical
  // rail exposed.
  createEffect(() => {
    const id = selectedCardId();
    if (!id || !railRef) return;
    const row = railRef.querySelector<HTMLElement>(`[data-node-id="${id}"]`);
    if (!row) return;
    railRef
      .querySelectorAll('.cockpit-rail__selected')
      .forEach((el) => el.classList.remove('cockpit-rail__selected'));
    row.classList.add('cockpit-rail__selected');
    row.scrollIntoView?.({ block: 'nearest' });
  });

  onMount(() => {
    // D-04: auto-load the most-recent run on open.
    void enumerateRuns(props.cwd).then((entries) => {
      if (entries.length > 0) {
        void loadRun(entries[0].run_id, props.cwd, props.cliBinary);
      }
    });

    // VCKP-07 (GATED A13, best-effort): read .voss/swarm/manifest.json if a
    // future read path exists. No read command / fs-plugin ships in V14, so this
    // degrades silently to no-swarm. We do NOT call a non-existent invoke (avoids
    // console noise); the "when present" path is covered by the swarmReconcile
    // adapter test, not faked here. Establish the null default explicitly.
    setSwarmManifest(null);

    const onDocKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && pickerOpen()) {
        setPickerOpen(false);
        e.stopPropagation();
      }
    };
    const onDocClick = (e: MouseEvent) => {
      if (pickerOpen() && pickerRef && !pickerRef.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    };
    document.addEventListener('keydown', onDocKey, true);
    document.addEventListener('mousedown', onDocClick, true);
    onCleanup(() => {
      document.removeEventListener('keydown', onDocKey, true);
      document.removeEventListener('mousedown', onDocClick, true);
    });
  });

  const pickRun = (runId: string) => {
    setPickerOpen(false);
    void loadRun(runId, props.cwd, props.cliBinary);
  };

  // Run header derivations: idea from the audit/run-final when persisted
  // (falls back to the run id already shown in the picker button); progress
  // counts from the same boardDerive columns the board renders.
  const idea = (): string | null =>
    runData()?.audit?.idea ?? runData()?.run_final?.idea ?? null;

  const progress = () => {
    const cards = cardsFromRunData(runData());
    const count = (col: string) =>
      cards.filter((c) => c.column === col).length;
    return {
      total: cards.length,
      done: count('Done'),
      inflight: count('InProgress'),
      blocked: count('Blocked'),
    };
  };

  return (
    <div class="org-view-shell" role="region" aria-label="Run cockpit">
      {/* D-03: the RunCommandBar strip is mounted at App level ABOVE the
          grid/cockpit swap so it is present in BOTH Live Work and Run Review
          modes — it is intentionally NOT rendered here (no double strip). */}

      <div class="cockpit-body">
        <div class="cockpit-grid">
          {/* 1 — Team sidebar (mockup .sidebar) */}
          <aside class="cockpit-sidebar" aria-label="Team sidebar" tabindex={0}>
            <CockpitSidebar
              data={runData()}
              swarm={swarm()}
              vossClient={props.vossClient}
              onAttach={props.onAttach}
            />
          </aside>

          {/* 2/3 — Main column: run header + board + horizontal timeline */}
          <div class="cockpit-main">
            {/* Run header (mockup .runhdr) — hosts the lifted picker/refresh/
                back controls so they survive loading/error states below. */}
            <div class="cockpit-runhdr">
              <button class="org-header-btn" onClick={() => props.onClose()}>
                ← Grid
              </button>
              <button
                class="org-header-btn cockpit-runhdr__pick"
                aria-haspopup="listbox"
                aria-expanded={pickerOpen()}
                onClick={() => setPickerOpen((p) => !p)}
              >
                run {shortRunId(currentRunId())} ▾
              </button>
              <button
                class="org-header-btn"
                disabled={loading()}
                onClick={() => void refreshRun(props.cwd, props.cliBinary)}
              >
                <span
                  class={`org-refresh-glyph${loading() ? ' org-refresh-glyph--spinning' : ''}`}
                >
                  ↻
                </span>
                Refresh
              </button>
              {/* VCKP-06: live/snapshot state label. Bound to the sseClient
                  liveLabel signal; default 'snapshot' (no auto-stream in V14). */}
              <span
                class={`cockpit-live-label cockpit-live-label--${liveLabel()}`}
                aria-label={`Data source: ${liveLabel()}`}
              >
                {liveLabel() === 'live' ? '● live' : 'snapshot'}
              </span>

              <Show when={idea()}>
                <span class="cockpit-runhdr__idea">{idea()}</span>
              </Show>

              <Show when={progress().total > 0}>
                <span class="cockpit-runhdr__prog">
                  {progress().total} cards ·{' '}
                  <b class="cockpit-prog--done">{progress().done}</b> done ·{' '}
                  <b class="cockpit-prog--inflight">{progress().inflight}</b>{' '}
                  in-flight ·{' '}
                  <b class="cockpit-prog--blocked">{progress().blocked}</b>{' '}
                  blocked
                </span>
              </Show>

              <Show when={pickerOpen()}>
                <div class="org-run-picker" role="listbox" ref={pickerRef}>
                  <Show
                    when={runEntries().length > 0}
                    fallback={
                      <div class="org-run-picker__empty">No runs found</div>
                    }
                  >
                    <For each={runEntries()}>
                      {(entry) => (
                        <div
                          class={`org-run-picker__row${entry.run_id === currentRunId() ? ' org-run-picker__row--active' : ''}`}
                          role="option"
                          aria-selected={entry.run_id === currentRunId()}
                          onClick={() => pickRun(entry.run_id)}
                        >
                          <span>{shortRunId(entry.run_id)}</span>
                          <span>{entry.has_run_final ? 'final' : 'active'}</span>
                          <span class="org-run-picker__mtime">
                            {new Date(entry.mtime_secs * 1000).toLocaleString()}
                          </span>
                        </div>
                      )}
                    </For>
                  </Show>
                </div>
              </Show>
            </div>

            {/* Board + timeline — loading/error <Show> wrappers lifted from
                OrgViewShell occupy this slot so the header stays mounted. */}
            <Show
              when={!loading()}
              fallback={
                <div class="org-spinner" aria-label="Loading run">
                  <span class="org-spinner__glyph">⟳</span>
                </div>
              }
            >
              <Show
                when={!loadError()}
                fallback={
                  <div class="org-error-state">
                    <h2 class="org-error-state__heading">Run not found</h2>
                    <p class="org-error-state__body">
                      The run "{currentRunId() ?? ''}" could not be loaded.
                      Check that the run ID is valid and try refreshing.
                    </p>
                    <button
                      class="org-error-state__refresh"
                      onClick={() =>
                        void refreshRun(props.cwd, props.cliBinary)
                      }
                    >
                      Refresh
                    </button>
                  </div>
                }
              >
                <div class="cockpit-board" aria-label="Board spine" tabindex={0}>
                  <BoardPanel
                    data={runData()}
                    onCardSelect={setSelectedCardId}
                    selectedCardId={selectedCardId()}
                  />
                </div>

                <div
                  class="cockpit-rail"
                  aria-label="Timeline and replay"
                  tabindex={0}
                  ref={railRef}
                >
                  <TimelineRail
                    data={runData()}
                    onNodeSelect={setSelectedCardId}
                  />
                </div>
              </Show>
            </Show>
          </div>

          {/* 4 — Card detail drawer (mockup .drawer) */}
          <div class="cockpit-drawer" aria-label="Card detail" tabindex={0}>
            <CardDrawer followUpClient={props.followUpClient} />
          </div>

          {/* 5 — Gate bar */}
          <div class="cockpit-gate" aria-label="Gate bar" tabindex={0}>
            <GateBar />
          </div>
        </div>
      </div>
    </div>
  );
};

export default CockpitShell;
