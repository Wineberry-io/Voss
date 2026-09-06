// VCKP-08 / V14-08 — Live <-> Review toggle persistence + open-in-grid + spawn wiring.
//
// Harness rationale (see plan 08 research note): App.test.tsx MOCKS GridRoot
// ENTIRELY and supplies a controllerRef whose `splitFocused` is a no-op and which
// implements no `focusPaneById`, and it never mounts a real PaneComponent — so it
// CANNOT observe spawn_agent or pane-id minting. We therefore follow the
// runCommandBar.test.tsx pattern instead: stub `@tauri-apps/api/core`, exercise the
// real GLOBAL modules under test (selection.ts, model/bridge.ts), and replicate the
// App-local closures (orgViewOpen toggle, the display:none swap at App.tsx:1234, the
// open-in-grid createEffect at App.tsx:317-323, and handleLaunchAgent's race-free
// ordering at App.tsx:286-311) verbatim in tiny harness components / functions. This
// is approach (1) from the note: assert handleLaunchAgent's ordering at the
// GridController seam with a fake controller — no DOM-mocked GridRoot, deterministic.

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from 'solid-js/web';
import { createSignal, createEffect } from 'solid-js';

// RunCommandBar / the spawn path import `@tauri-apps/api/core`. Stub so any module
// import resolves under jsdom; we also assert against the captured mock when a spawn
// path actually invokes it (runCommandBar.test.tsx:13).
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));

import {
  selectedCardId,
  setSelectedCardId,
  selectedRunId,
  setSelectedRunId,
  openInGridRequest,
  setOpenInGridRequest,
  requestOpenInGrid,
} from '../org/selection';
import {
  cardToPane,
  registerTerminalCard,
  __resetBridgeMaps,
} from '../org/model/bridge';
import CardDrawer from '../org/cockpit/CardDrawer';
import type { AgentConfig } from '../pane/pty-ipc';
import type { GridController } from '../canvas/CanvasRoot';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown): HTMLElement {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}

afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  // selection.ts signals are module-level (global) — no reset helper exists, clear
  // them manually (note: selection.ts:8-9 / 15). bridge.ts has __resetBridgeMaps.
  setSelectedCardId(null);
  setSelectedRunId(null);
  setOpenInGridRequest(null);
  __resetBridgeMaps();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Case 1 — SELECTION PERSISTS ACROSS A LIVE->REVIEW->LIVE TOGGLE
//
// orgViewOpen is App-local; the ⌘⇧O path is `setOrgViewOpen((p) => !p)`
// (App.tsx:1061/1335). Replicate that exact toggle and round-trip it twice. The
// selection signals are a SEPARATE global module (selection.ts), so the toggle must
// not perturb them — that is the persistence guarantee VCKP-08 asserts.
// ---------------------------------------------------------------------------
describe('VCKP-08 — selection persists across the Live/Review toggle', () => {
  it('selectedRunId + selectedCardId survive a Live->Review->Live round-trip', () => {
    const [orgViewOpen, setOrgViewOpen] = createSignal(false); // false = Live (grid)

    setSelectedRunId('run-7');
    setSelectedCardId('card-99');

    // Live -> Review -> Live (the same ⌘⇧O signal flip, twice).
    setOrgViewOpen((p) => !p); // Live -> Review
    expect(orgViewOpen()).toBe(true);
    setOrgViewOpen((p) => !p); // Review -> Live
    expect(orgViewOpen()).toBe(false);

    expect(selectedRunId()).toBe('run-7');
    expect(selectedCardId()).toBe('card-99');
  });
});

// ---------------------------------------------------------------------------
// Case 2 — GRID STAYS MOUNTED (Pitfall 3: no conditional unmount)
//
// App.tsx:1234 wraps the grid in a node whose ONLY toggle is the inline
// `display: orgViewOpen() ? 'none' : 'flex'`. The node is NEVER torn down. Replicate
// that exact container and assert the SAME element reference persists across the
// toggle — only `display` flips between 'flex' and 'none'.
// ---------------------------------------------------------------------------
describe('VCKP-08 — grid container stays mounted across the toggle', () => {
  it('the grid node is the same element reference; only inline display flips', () => {
    const [orgViewOpen, setOrgViewOpen] = createSignal(false);

    const root = mount(() => (
      <div
        data-testid="grid-host"
        style={{ display: orgViewOpen() ? 'none' : 'flex' }}
      >
        <div data-testid="grid-root">grid</div>
      </div>
    ));

    const before = root.querySelector('[data-testid="grid-host"]') as HTMLElement;
    const gridBefore = root.querySelector('[data-testid="grid-root"]');
    expect(before.style.display).toBe('flex'); // Live

    setOrgViewOpen(true); // -> Review
    const duringReview = root.querySelector('[data-testid="grid-host"]') as HTMLElement;
    expect(duringReview).toBe(before); // same element reference — not remounted
    expect(duringReview.style.display).toBe('none');
    // The inner grid is still present (hidden, not removed).
    expect(root.querySelector('[data-testid="grid-root"]')).toBe(gridBefore);

    setOrgViewOpen(false); // -> Live
    const after = root.querySelector('[data-testid="grid-host"]') as HTMLElement;
    expect(after).toBe(before); // still the same node across the full round-trip
    expect(after.style.display).toBe('flex');
    expect(root.querySelector('[data-testid="grid-root"]')).toBe(gridBefore);
  });
});

// ---------------------------------------------------------------------------
// Case 3 — OPEN-IN-GRID (D-07)
//
// Two halves:
//  (a) CardDrawer button: bind a card to a pane via registerTerminalCard so
//      boundPaneId() is set, render the real CardDrawer, click "Open in grid", and
//      assert it pushes the bound paneId onto openInGridRequest (CardDrawer.tsx:89-94).
//  (b) App-side effect: replicate App.tsx:317-323 — read openInGridRequest(), flip
//      orgViewOpen(false), call gridController.focusPaneById(paneId), clear the
//      request — and assert all three on a spy controller.
// ---------------------------------------------------------------------------
describe('VCKP-08 — open-in-grid (D-07)', () => {
  it("CardDrawer 'Open in grid' button publishes the bound pane onto openInGridRequest", () => {
    // Bind a card to a pane (Bridge B) and select it so boundPaneId() resolves.
    const cardId = registerTerminalCard('pane-77');
    expect(cardToPane()[cardId]).toBe('pane-77');
    setSelectedCardId(cardId);

    const root = mount(() => <CardDrawer data={null} />);

    const btn = [...root.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Open in grid',
    ) as HTMLButtonElement;
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBe(false); // enabled because a live pane is bound

    btn.click();

    // The drawer requested the grid open the bound pane.
    expect(openInGridRequest()).toBe('pane-77');
  });

  it('the App-side effect flips orgViewOpen->false, focuses the pane, and clears the request', () => {
    const focusPaneById = vi.fn();
    const ctrl = { focusPaneById } as unknown as GridController;

    const [orgViewOpen, setOrgViewOpen] = createSignal(true); // start in Review

    // Replicates App.tsx:317-323 verbatim.
    dispose = render(() => {
      createEffect(() => {
        const paneId = openInGridRequest();
        if (!paneId) return;
        setOrgViewOpen(false);
        ctrl.focusPaneById(paneId);
        setOpenInGridRequest(null);
      });
      return null as never;
    }, document.createElement('div'));

    // Nothing fired yet.
    expect(orgViewOpen()).toBe(true);
    expect(focusPaneById).not.toHaveBeenCalled();

    // Fire the D-07 request (what CardDrawer does).
    requestOpenInGrid('pane-31');

    expect(orgViewOpen()).toBe(false); // jumped back to the grid (Live)
    expect(focusPaneById).toHaveBeenCalledTimes(1);
    expect(focusPaneById).toHaveBeenCalledWith('pane-31');
    expect(openInGridRequest()).toBeNull(); // consumed so it can't re-fire
  });
});

// ---------------------------------------------------------------------------
// Case 4 — SPAWN WIRING (Bridge B), asserted at the GridController seam.
//
// Replicate handleLaunchAgent's exact race-free ordering (App.tsx:286-311) against a
// fake controller whose snapshot() returns a fresh focusedId after splitFocused.
// Assert: a cardId is minted, bound to the new pane (cardToPane), and carried as the
// AgentConfig.sessionId written to the per-pane config map. This is the seam doSpawn
// later reads to take the spawnAgent branch.
// ---------------------------------------------------------------------------

/** Minimal re-statement of App.tsx handleLaunchAgent against an injected seam. */
function wireAgentLaunch(
  ctrl: Pick<GridController, 'splitFocused' | 'snapshot'>,
  config: { cliBinary: string; cliArgs: string[]; taskPrompt: string },
  setAgentConfigByPaneId: (paneId: string, cfg: AgentConfig) => void,
): { newId: string; cardId: string; cfg: AgentConfig } | null {
  const before = ctrl.snapshot().focusedId;
  ctrl.splitFocused('H');
  const newId = ctrl.snapshot().focusedId;
  if (newId === before) return null; // GRD-05 guard: split rejected — abort.

  const cardId = registerTerminalCard(newId);
  const cfg: AgentConfig = {
    cliBinary: config.cliBinary,
    cliArgs: config.cliArgs,
    sessionId: cardId,
  };
  setAgentConfigByPaneId(newId, cfg);
  return { newId, cardId, cfg };
}

describe('VCKP-08 — spawn wiring mints a cardId and carries it as sessionId (Bridge B)', () => {
  it('mints a cardId, binds it to the new pane, and writes it as AgentConfig.sessionId', () => {
    let focusedId = 'pane-old';
    const ctrl = {
      splitFocused: vi.fn(() => {
        focusedId = 'pane-new'; // split succeeds -> focus moves to the new pane
      }),
      snapshot: vi.fn(() => ({ nodes: [], view: { x: 0, y: 0, zoom: 1 }, focusedId })),
    };
    const configByPane: Record<string, AgentConfig> = {};

    const out = wireAgentLaunch(
      ctrl,
      { cliBinary: 'claude', cliArgs: ['--mode', 'Edit'], taskPrompt: 'Refactor auth' },
      (paneId, cfg) => {
        configByPane[paneId] = cfg;
      },
    );

    expect(out).not.toBeNull();
    expect(ctrl.splitFocused).toHaveBeenCalledWith('H');
    expect(out!.newId).toBe('pane-new');

    // Bridge B: the minted cardId is bound to the new pane...
    expect(typeof out!.cardId).toBe('string');
    expect(cardToPane()[out!.cardId]).toBe('pane-new');

    // ...and rides through as the AgentConfig.sessionId on the new pane's config.
    expect(configByPane['pane-new']).toBeDefined();
    expect(configByPane['pane-new'].sessionId).toBe(out!.cardId);
    expect(configByPane['pane-new'].cliBinary).toBe('claude');
    expect(configByPane['pane-new'].cliArgs).toEqual(['--mode', 'Edit']);
  });

  it('GRD-05 guard: a rejected split mints NO cardId and writes NO config', () => {
    const ctrl = {
      splitFocused: vi.fn(), // no-op: focusedId unchanged (min-size rejection)
      snapshot: vi.fn(() => ({ nodes: [], view: { x: 0, y: 0, zoom: 1 }, focusedId: 'pane-stuck' })),
    };
    const configByPane: Record<string, AgentConfig> = {};

    const out = wireAgentLaunch(
      ctrl,
      { cliBinary: 'claude', cliArgs: [], taskPrompt: 'x' },
      (paneId, cfg) => {
        configByPane[paneId] = cfg;
      },
    );

    expect(out).toBeNull(); // aborted
    expect(Object.keys(cardToPane())).toHaveLength(0); // no register* leakage
    expect(Object.keys(configByPane)).toHaveLength(0);
  });
});
