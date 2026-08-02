import { onMount, onCleanup, createSignal, Show } from 'solid-js';
import { invoke } from '@tauri-apps/api/core';
import '@xterm/xterm/css/xterm.css';
import './pane.css';
import { type AgentConfig, type BudgetState } from './pty-ipc';
import { isKnownAgentCli } from './agentDetect';
import BudgetBar from '../grid/BudgetBar';
import BudgetPopover from '../grid/BudgetPopover';
import PasteGuard from './PasteGuard';
import ExitBanner from './ExitBanner';
import ProtocolPane from './ProtocolPane';
import FindBar from './FindBar';
import {
  getPaneSession,
  type PaneSession,
  type PaneSink,
} from './paneSessionRegistry';
import {
  adoptPaneSession,
  createPaneSession,
  releasePaneSession,
  reportPaneProc,
  respawnPaneSession,
  spawnPaneSession,
} from './paneSession';
import {
  resolvePane,
  cardToPane,
  cardToSessionNode,
} from '../org/model/bridge';
import { requestOpenInReview } from '../org/selection';
import { applyAppearanceToTerminal } from '../themes/themeRuntime';
import {
  loadAppearanceSettings,
  subscribeAppearanceSettings,
  type AppearanceSettings,
} from '../appearance/settings';
import { DEFAULT_APPEARANCE_SETTINGS } from '../appearance/types';
import {
  clipboardImageFile,
  imageFileToBytes,
  quotePathForShell,
  resolveTerminalCopyAction,
  shouldGuardTerminalPaste,
  type CopyMode,
} from './terminalClipboard';

export interface PaneProps {
  /** Pane id for scrollback registry and restore keying (A6). */
  id?: string;
  /** Working directory for the spawned shell; header shows its basename. */
  cwd?: string;
  /** $SHELL basename for the header shell slot (A2 = static; A8 wires real). */
  shell?: string;
  /** Pane index — A2 is always 1; A3 assigns real indices. */
  index?: number;
  /** Session-restored scrollback lines to seed before shell interaction (A6 D-09). */
  restoredScrollback?: string[];
  /** Called once on first user input in a restored pane (dismiss RestoreBanner). */
  onFirstInput?: () => void;
  agentConfig?: AgentConfig;
  workspacePath?: string;
  /** Grid supplies PaneHeader; hide this pane's duplicate chrome row. */
  embeddedInGrid?: boolean;
  /** V15-03 (VLIVE-04): native server session — when set, the pane body is a
   *  structured ProtocolPane and NO PTY is spawned (discriminator). */
  nativeSessionId?: string;
  nativeSidecarId?: string;
}

function basename(p: string): string {
  const parts = p.replace(/\/+$/, '').split('/');
  return parts[parts.length - 1] || p;
}

type DotState = import('./paneSessionRegistry').DotState;

/** D-06 copy/interrupt mode. 'smart' = selection→copy else SIGINT. A8 surfaces UI. */
export default function PaneComponent(props: PaneProps) {
  let containerRef!: HTMLDivElement;
  let bodyRef!: HTMLDivElement;
  // The live session (Terminal + transport + host element) persists in the
  // paneSession registry across remounts (drag/swap/layout) — this component
  // only ADOPTS it. See paneSessionRegistry.ts.
  let session: PaneSession | undefined;
  let adoptToken: symbol | undefined;
  let observer: ResizeObserver | undefined;
  let resizeTimer: ReturnType<typeof setTimeout> | undefined;
  let dprMedia: MediaQueryList | undefined;
  let fgPoll: ReturnType<typeof setInterval> | undefined;
  let perfStop = false; // stops the test-only rAF perf probe on cleanup
  let bypassFlag = false; // one-shot ⌘⇧V paste bypass
  let bellFlashTimer: ReturnType<typeof setTimeout> | undefined;
  let bellBadgeTimer: ReturnType<typeof setTimeout> | undefined;
  let appearanceUnsub: (() => void) | undefined;
  let headerRef!: HTMLDivElement;
  const copyMode = 'smart' as CopyMode; // D-06 configurable hook (A8 UI)

  const [focused, setFocused] = createSignal(true); // single pane = focused (A2)
  const [dot, setDot] = createSignal<DotState>('loading');
  const [proc, setProc] = createSignal('');
  const [pendingPaste, setPendingPaste] = createSignal<string | null>(null);
  const [showFind, setShowFind] = createSignal(false);
  const [exitCode, setExitCode] = createSignal<number | null>(null);
  const [appearance, setAppearance] = createSignal<AppearanceSettings>(
    DEFAULT_APPEARANCE_SETTINGS,
  );
  const [bellBadge, setBellBadge] = createSignal(false);
  const [headerFlash, setHeaderFlash] = createSignal(false);
  const [budget, setBudget] = createSignal<BudgetState | null>(null);
  const [budgetPopoverAnchor, setBudgetPopoverAnchor] = createSignal<HTMLElement | null>(null);
  const openBudgetPopover = (anchor: HTMLElement) =>
    setBudgetPopoverAnchor((prev) => (prev === anchor ? null : anchor));
  const closeBudgetPopover = () => setBudgetPopoverAnchor(null);
  const isAgentCli = () => isKnownAgentCli(proc());

  // --- V14 chunk C role chrome (mockup .pane::before / .ph) — AGENT panes
  // only (props.agentConfig present). ---------------------------------------

  // Role from the launch CLI — the same CLI→role mapping the sidebar/grid
  // chrome use (App.mapRole / SplitNode.mapCliToRoleColor). Unknown agent CLIs
  // default to executor: these panes are agent launches by construction.
  const agentRole = (): 'planner' | 'executor' | 'reviewer' | 'watcher' => {
    switch (props.agentConfig?.cliBinary) {
      case 'claude':
      case 'voss':
        return 'planner';
      case 'gemini':
        return 'reviewer';
      case 'opencode':
        return 'watcher';
      default:
        return 'executor';
    }
  };
  const roleColor = () => `var(--role-${agentRole()})`;

  // Bound board card (Bridge B reverse lookup) — reactive via the live
  // cardToPane signal; undefined until the bridge binds one.
  const boundCardId = () => {
    const paneId = props.id;
    if (!paneId || !props.agentConfig) return undefined;
    return resolvePane(
      { cardToPane: cardToPane(), cardToSessionNode: cardToSessionNode() },
      paneId,
    );
  };

  // Honest streaming signal: budget telemetry seen within the last 3s — the
  // SAME recency definition the sidebar + grid PaneHeader already use
  // (budgetRegistry lastSeenMs < 3000). Event-driven decay via timeout; no
  // fabricated state.
  const [streaming, setStreaming] = createSignal(false);
  let streamDecayTimer: ReturnType<typeof setTimeout> | undefined;
  const markStreaming = () => {
    setStreaming(true);
    if (streamDecayTimer) clearTimeout(streamDecayTimer);
    streamDecayTimer = setTimeout(() => setStreaming(false), 3000);
  };

  const cwdBase = () => basename(props.cwd ?? '~');
  const shellName = () => props.shell ?? 'shell';
  const onDpr = () => session?.fitAddon.fit();

  const writeBytes = (b: Uint8Array) => session?.transport.write(b);
  const writeStr = (s: string) => writeBytes(new TextEncoder().encode(s));

  const playAudibleBell = () => {
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.value = 0.08;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.08);
      osc.onended = () => void ctx.close();
    } catch {
      /* no audio — ignore */
    }
  };

  const triggerBell = (behavior: AppearanceSettings['bellBehavior']) => {
    if (behavior === 'none') return;

    if (behavior === 'badge') {
      setBellBadge(true);
      if (bellBadgeTimer) clearTimeout(bellBadgeTimer);
      bellBadgeTimer = setTimeout(() => setBellBadge(false), 2000);
      return;
    }

    if (behavior === 'audible') {
      playAudibleBell();
      return;
    }

    // visual flash (default)
    if (appearance().reducedMotionEnabled) {
      setHeaderFlash(true);
      if (bellFlashTimer) clearTimeout(bellFlashTimer);
      bellFlashTimer = setTimeout(() => setHeaderFlash(false), 120);
      return;
    }
    setHeaderFlash(true);
    if (bellFlashTimer) clearTimeout(bellFlashTimer);
    bellFlashTimer = setTimeout(() => setHeaderFlash(false), 200);
  };

  const SEARCH_DECORATIONS = {
    activeMatchBackground: 'rgba(90,124,255,0.35)',
    matchOverviewRuler: 'rgba(90,124,255,0.35)',
    activeMatchColorOverviewRuler: 'rgba(90,124,255,0.35)',
  } as const;

  const restart = async () => {
    if (!session) return;
    await respawnPaneSession(session); // scrollback preserved — same Terminal
  };

  const keyHandler = (e: KeyboardEvent): boolean => {
    const meta = e.metaKey;
    if (!meta) return true;
    const k = e.key.toLowerCase();

    // ⌘⇧V — one-shot paste bypass (let the native paste through, no banner).
    if (e.shiftKey && k === 'v') {
      bypassFlag = true;
      return true;
    }
    // ⌘⇧K — clear scrollback.
    if (e.shiftKey && k === 'k') {
      session?.term.clear();
      return false;
    }
    // ⌘F — open find bar.
    if (!e.shiftKey && k === 'f') {
      setShowFind(true);
      return false;
    }
    // ⌘C copies terminal selection. Ctrl+C remains the interrupt path.
    if (!e.shiftKey && k === 'c') {
      const action = resolveTerminalCopyAction(
        !!session?.term.hasSelection(),
        copyMode,
      );
      if (action === 'copy-selection') {
        const sel = session?.term.getSelection() ?? '';
        void navigator.clipboard?.writeText(sel);
        session?.term.clearSelection();
        return false;
      }
      if (action === 'interrupt') {
        writeBytes(new Uint8Array([0x03])); // ETX → SIGINT to fg pgid
        return false;
      }
      return false;
    }
    return true;
  };

  const pasteText = (text: string, bypass: boolean) => {
    if (!text) return;
    if (shouldGuardTerminalPaste(text, bypass)) {
      setPendingPaste(text);
    } else {
      writeStr(text);
    }
  };

  const onPaste = (e: ClipboardEvent) => {
    e.preventDefault();
    const data = e.clipboardData;
    const imageFile = clipboardImageFile(data);
    if (imageFile) {
      void (async () => {
        try {
          const payload = await imageFileToBytes(imageFile);
          const path = await invoke<string>('save_clipboard_image', payload);
          writeStr(quotePathForShell(path));
        } catch (err) {
          console.error('[voss-app] image paste failed:', err);
        } finally {
          bypassFlag = false;
        }
      })();
      return;
    }
    const text = e.clipboardData?.getData('text') ?? '';
    pasteText(text, bypassFlag);
    bypassFlag = false; // consume one-shot
  };

  onMount(async () => {
    // V15-03: native protocol panes render <ProtocolPane> instead of xterm —
    // skip terminal/transport setup entirely (the body div is swapped out).
    if (props.nativeSessionId) {
      setDot('running');
      return;
    }
    let settings = DEFAULT_APPEARANCE_SETTINGS;
    try {
      settings = await loadAppearanceSettings();
      setAppearance(settings);
    } catch {
      /* use defaults when settings unavailable (tests) */
    }

    // Adopt the existing live session (remount after drag/swap/layout) or
    // create a fresh one. Only creation spawns — adoption never respawns.
    const paneId = props.id ?? String(props.index ?? 1);
    let created = false;
    session = getPaneSession(paneId);
    if (!session) {
      created = true;
      session = createPaneSession({
        paneId,
        cwd: props.cwd,
        agentConfig: props.agentConfig,
        workspacePath: props.workspacePath,
        restoredScrollback: props.restoredScrollback,
        settings,
      });
    }
    const s = session;

    const sink: PaneSink = {
      setDot,
      setExitCode,
      setBudget,
      setProc,
      bell: () => triggerBell(appearance().bellBehavior),
      markStreaming,
      onFirstInput: () => props.onFirstInput?.(),
    };
    adoptToken = adoptPaneSession(s, bodyRef, sink, keyHandler, settings);

    // Hydrate component signals from the session's canonical state — the
    // process may have progressed or exited while detached.
    setDot(s.dot);
    setExitCode(s.lastExitCode);
    if (s.lastBudget) setBudget(s.lastBudget);
    if (s.lastProc) setProc(s.lastProc);

    containerRef.addEventListener('paste', onPaste, true); // capture phase

    if (created) await spawnPaneSession(s);

    appearanceUnsub = subscribeAppearanceSettings((next) => {
      setAppearance(next);
      applyAppearanceToTerminal(s.term, next);
    });

    // D-07 fallback: poll pgid only when no recent OSC title (>2s).
    fgPoll = setInterval(() => {
      if (Date.now() - s.lastOscTitleAt < 2000) return;
      s.transport
        .fgProcess()
        .then((name) => {
          if (name) reportPaneProc(s, name);
        })
        .catch(() => {});
    }, 500);

    // Debounced container resize → fit + pty_resize (Pattern 6).
    observer = new ResizeObserver(() => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        s.fitAddon.fit();
        s.transport.resize(s.term.rows, s.term.cols);
      }, 150);
    });
    observer.observe(containerRef);

    // Pitfall 5: re-fit on DPR (Retina ↔ external display) change.
    dprMedia = window.matchMedia(
      `(resolution: ${window.devicePixelRatio}dppx)`,
    );
    dprMedia.addEventListener('change', onDpr);

    // D-02 test-only perf probe: records rAF deltas into a ring buffer for
    // the flood-perf harness. Inert in production (env guard) — T-A2-12.
    if (import.meta.env.MODE === 'test') {
      const w = window as unknown as { __vossPerf?: { frames: number[] } };
      w.__vossPerf = { frames: [] };
      let last = performance.now();
      const tick = () => {
        if (perfStop) return;
        const now = performance.now();
        const f = w.__vossPerf!.frames;
        f.push(now - last);
        if (f.length > 1000) f.shift();
        last = now;
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  });

  onCleanup(() => {
    perfStop = true;
    if (resizeTimer) clearTimeout(resizeTimer);
    if (fgPoll) clearInterval(fgPoll);
    if (bellFlashTimer) clearTimeout(bellFlashTimer);
    if (bellBadgeTimer) clearTimeout(bellBadgeTimer);
    if (streamDecayTimer) clearTimeout(streamDecayTimer);
    appearanceUnsub?.();
    observer?.disconnect();
    dprMedia?.removeEventListener('change', onDpr);
    containerRef?.removeEventListener('paste', onPaste, true);
    // The session SURVIVES this unmount (drag/swap/layout rearrange). It is
    // killed only via destroyPaneSession (real close, orphan reap, workspace
    // teardown). A stale token (swap re-adopted first) makes this a no-op.
    if (session && adoptToken) releasePaneSession(session, adoptToken);
  });

  const sendPaste = () => {
    const p = pendingPaste();
    if (p) writeStr(p);
    setPendingPaste(null);
  };
  const discardPaste = () => setPendingPaste(null);

  const closeFind = () => {
    setShowFind(false);
    session?.term.focus();
  };

  const paneClass = () => {
    const base = props.embeddedInGrid ? 'pane pane--embedded' : 'pane';
    return focused() && !props.embeddedInGrid
      ? `${base} focused`
      : base;
  };

  return (
    <div
      ref={containerRef}
      class={paneClass()}
      onClick={() => setFocused(true)}
    >
      {/* V14 chunk C — role-colored full-height left edge (mockup
          .pane::before), agent panes only. Color set inline from the
          --role-* tokens (mirrors AgentItem); no new custom properties. */}
      <Show when={props.agentConfig}>
        <span
          class="pane-role-edge"
          style={{ background: roleColor() }}
          aria-hidden="true"
        />
      </Show>
      <Show when={!props.embeddedInGrid}>
      <div
        ref={headerRef}
        class={`pane-header${headerFlash() ? ' bell-flash' : ''}${isAgentCli() ? ' agent-pane' : ''}`}
      >
        <span
          class={`dot ${dot()}${isAgentCli() ? ' agent' : ''}${streaming() ? ' pane-dot--streaming' : ''}`}
        >
          ●
        </span>
        <span class="sep">·</span>
        <span class="idx">{props.index ?? 1}</span>
        <span class="sep">·</span>
        <span class="cwd">{cwdBase()}</span>
        <span class="sep">·</span>
        <span class="shell">{shellName()}</span>
        <Show when={proc()}>
          <span class="sep">·</span>
          <span class={isAgentCli() ? 'proc agent-proc' : 'proc'}>{proc()}</span>
        </Show>
        {/* V14 chunk C — role pill (mockup .ppill, 11px ≥ A12 floor). For
            configured agent panes it supersedes the generic "agent" hint
            below (same slot, more specific). */}
        <Show when={props.agentConfig}>
          <span class="sep">·</span>
          <span
            class="role-pill"
            style={{
              color: roleColor(),
              background: `color-mix(in srgb, ${roleColor()} 16%, transparent)`,
            }}
          >
            {agentRole()}
          </span>
        </Show>
        <Show when={isAgentCli() && !budget() && !props.agentConfig}>
          <span class="sep">·</span>
          <span style={{ color: 'var(--accent-cyan)', 'font-size': '11px' }}>agent</span>
        </Show>
        <Show when={isAgentCli() && budget()?.model}>
          <span class="sep">·</span>
          <span class="model">{budget()!.model}</span>
        </Show>
        <Show when={bellBadge()}>
          <span class="sep">·</span>
          <span class="bell-badge" title="Bell">
            *
          </span>
        </Show>
        <span class="spacer" />
        {/* V14 chunk C — bound-card chip (mockup .pcard): Bridge B reverse
            lookup; clicking selects the card and jumps to Run Review. */}
        <Show when={boundCardId()}>
          {(cardId) => (
            <button
              type="button"
              class="card-chip"
              title="Open this card in Run Review"
              onClick={(e) => {
                e.stopPropagation();
                requestOpenInReview(cardId());
              }}
            >
              ▦ {cardId().slice(0, 8)}
            </button>
          )}
        </Show>
        <Show when={budget()}>
          {(b) => (
            <BudgetBar
              budget={b()}
              onClickDetail={(anchor) => openBudgetPopover(anchor)}
            />
          )}
        </Show>
        {/* V14 chunk C — streaming flag (mockup .pstream): budget-event
            recency (<3s), the registry signal the sidebar already shows. */}
        <Show when={props.agentConfig && streaming()}>
          <span class="stream-flag">streaming</span>
        </Show>
        <button class="menu" title="menu" type="button">
          ⋯
        </button>
      </div>
      </Show>
      <Show
        when={props.nativeSessionId}
        fallback={<div ref={bodyRef} class="pane-body" />}
      >
        <ProtocolPane
          sessionId={props.nativeSessionId!}
          sidecarId={props.nativeSidecarId!}
          onEnded={() => {
            // D-11: ProtocolPane renders its own inline ended banner — the
            // header dot reflects the state; no absolute PTY ExitBanner here.
            setDot('exited');
          }}
        />
      </Show>

      <Show when={showFind()}>
        <FindBar
          onNext={(q) =>
            session?.searchAddon.findNext(q, { decorations: SEARCH_DECORATIONS })
          }
          onPrev={(q) =>
            session?.searchAddon.findPrevious(q, { decorations: SEARCH_DECORATIONS })
          }
          onClose={closeFind}
        />
      </Show>

      <Show when={pendingPaste() !== null}>
        <PasteGuard
          pendingText={pendingPaste() as string}
          onSend={sendPaste}
          onDiscard={discardPaste}
        />
      </Show>

      <Show when={exitCode() !== null && !props.nativeSessionId}>
        <ExitBanner exitCode={exitCode() as number} onRestart={restart} />
      </Show>

      <Show when={budgetPopoverAnchor() != null && budget() != null}>
        <BudgetPopover
          budget={budget()!}
          anchor={budgetPopoverAnchor()!}
          onClose={closeBudgetPopover}
        />
      </Show>
    </div>
  );
}
