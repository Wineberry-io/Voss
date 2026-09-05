// Pane-session survival registry — HEAVY half: creation, adoption, spawn.
//
// Everything here was extracted from PaneComponent's onMount so the Terminal,
// PtyTransport (and its Tauri Channel), and the xterm host element persist
// across component remounts (drag/swap/layout-rearrange). The component is a
// thin adopter: it appends the session's host element into its body slot and
// points the session's mutable sink at its own signals. Zero Rust changes —
// the same PtyTransport instance keeps streaming through its Channel.
//
// Long-lived callbacks constructed HERE must never close over component
// state: they write the session's canonical fields + the paneId-keyed module
// registries (which keep updating while detached) and delegate UI updates
// through session.sink.

import { Terminal, type ILink, type ILinkProvider } from '@xterm/xterm';
import { CanvasAddon } from '@xterm/addon-canvas';
import { FitAddon } from '@xterm/addon-fit';
import { SearchAddon } from '@xterm/addon-search';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { invoke } from '@tauri-apps/api/core';
import { PtyTransport, type AgentConfig } from './pty-ipc';
import { adoptionByPaneId } from './adoptionRegistry';
import { registerPaneProc } from './procRegistry';
import { registerPaneBudget } from './budgetRegistry';
import { registerPaneContext } from './contextRegistry';
import { maybeLatchAgent } from './agentPaneRegistry';
import { mintSlug, registerSlug, slugByPaneId } from './slugRegistry';
import {
  registerScrollbackProvider,
} from './scrollbackRegistry';
import {
  getCurrentXtermTheme,
  registerTerminal,
  applyAppearanceToTerminal,
} from '../themes/themeRuntime';
import type { AppearanceSettings } from '../appearance/settings';
import {
  NOOP_SINK,
  trackPaneSession,
  type PaneSession,
  type PaneSink,
} from './paneSessionRegistry';

// OSC8 / file-path link scheme allowlist (T-A2-09).
const ALLOWED_SCHEMES = ['http:', 'https:', 'mailto:', 'file:'];
// File-path detection (UI-SPEC §3 link handling).
const FILE_PATH_RE = /(\/[^\s'"]+|~\/[^\s'"]+|\.[./][^\s'"]+)/g;

function openLink(uri: string): void {
  try {
    const u = new URL(uri);
    if (ALLOWED_SCHEMES.includes(u.protocol)) {
      void invoke('open_url', { url: uri });
    }
    // Any other scheme is silently rejected (T-A2-09).
  } catch {
    /* not a valid URL — ignore */
  }
}

function filePathLinkProvider(t: Terminal): ILinkProvider {
  return {
    provideLinks(y, callback) {
      const line = t.buffer.active.getLine(y - 1);
      if (!line) return callback(undefined);
      const text = line.translateToString(true);
      const links: ILink[] = [];
      for (const m of text.matchAll(FILE_PATH_RE)) {
        const idx = m.index ?? 0;
        links.push({
          text: m[0],
          range: {
            start: { x: idx + 1, y },
            end: { x: idx + m[0].length, y },
          },
          activate: (e: MouseEvent, path: string) => {
            if (e.metaKey) void invoke('open_path', { path });
          },
        });
      }
      callback(links.length ? links : undefined);
    },
  };
}

function buildTerminalOptions(settings: AppearanceSettings) {
  return {
    scrollback: 10_000,
    fontFamily: `"${settings.fontFamily}", "SF Mono", "Menlo", ui-monospace, monospace`,
    fontSize: settings.fontSize,
    lineHeight: settings.lineHeight,
    letterSpacing: settings.letterSpacing,
    customGlyphs: settings.ligatures,
    theme: getCurrentXtermTheme(),
    cursorStyle: settings.cursorShape,
    cursorBlink: settings.cursorBlink !== 'off',
    macOptionIsMeta: true,
    rightClickSelectsWord: false,
    allowProposedApi: false,
    linkHandler: {
      activate: (event: MouseEvent, uri: string) => {
        if (event.metaKey) openLink(uri);
      },
      allowNonHttpProtocols: true,
    },
  };
}

/** Canonical proc update: registries + session mirror + sink (the same work
 *  PaneComponent's old updateProc did, minus the component signal — that
 *  arrives via the sink). Title paths also stamp lastOscTitleAt (D-07). */
export function reportPaneProc(s: PaneSession, name: string): void {
  s.lastProc = name;
  registerPaneProc(s.paneId, name);
  maybeLatchAgent(s.paneId, name);
  s.sink.setProc(name);
}

export interface CreatePaneSessionArgs {
  paneId: string;
  cwd?: string;
  agentConfig?: AgentConfig;
  workspacePath?: string;
  /** A6: restored scrollback seeded at creation only (never on adoption). */
  restoredScrollback?: string[];
  settings: AppearanceSettings;
}

/**
 * Build the persistent session: host element, Terminal (+Fit/Search/WebLinks
 * — CanvasAddon waits for first adoption: D-01 Pitfall 2, it must load after
 * `term.open`), permanent listeners, PtyTransport, and the paneId-keyed
 * registry registrations. Does NOT open or spawn.
 */
export function createPaneSession(args: CreatePaneSessionArgs): PaneSession {
  const hostEl = document.createElement('div');
  hostEl.style.width = '100%';
  hostEl.style.height = '100%';

  const term = new Terminal(buildTerminalOptions(args.settings));
  const fitAddon = new FitAddon();
  const searchAddon = new SearchAddon();
  term.loadAddon(fitAddon);
  term.loadAddon(searchAddon);
  term.loadAddon(new WebLinksAddon());

  const s: PaneSession = {
    paneId: args.paneId,
    hostEl,
    term,
    fitAddon,
    searchAddon,
    transport: undefined as unknown as PtyTransport, // assigned below
    sink: NOOP_SINK,
    owner: null,
    opened: false,
    spawned: false,
    firstInputFired: false,
    lastOscTitleAt: 0,
    dot: 'loading',
    lastExitCode: null,
    lastBudget: null,
    lastProc: '',
    cfg: {
      cwd: args.cwd,
      agentConfig: args.agentConfig,
      workspacePath: args.workspacePath,
    },
  };

  s.transport = new PtyTransport({
    write: (data, cb) => term.write(data, cb),
    onExit: (code) => {
      s.dot = 'exited';
      s.lastExitCode = code;
      s.sink.setDot('exited');
      s.sink.setExitCode(code);
    },
    onFgProcess: (name) => reportPaneProc(s, name),
    onTitle: (title) => {
      s.lastOscTitleAt = Date.now();
      reportPaneProc(s, title);
    },
    onBudgetUpdate: (data) => {
      s.lastBudget = data;
      registerPaneBudget(s.paneId, data);
      s.sink.setBudget(data);
      s.sink.markStreaming(); // V14 chunk C — honest streaming recency signal
      // V14-12 (VCKP-12): adopted-agent budget-stop. Adoption happens AFTER
      // spawn, so the limit is read per-event from the adoption registry.
      // Kill the process only — the session (scrollback, ExitBanner,
      // restart) survives.
      const adopted = adoptionByPaneId()[s.paneId];
      if (adopted && adopted.budgetUsd > 0 && data.cost_usd >= adopted.budgetUsd) {
        s.transport.kill();
      }
    },
    onContextUpdate: (data) => {
      registerPaneContext(s.paneId, data);
    },
    ...(args.agentConfig
      ? {
          agentPaneId: args.paneId,
          workspacePath: args.workspacePath,
          // VCKP-13c: budget-kill threshold for managed launches.
          budgetKillLimitUsd: args.agentConfig.budgetUsd,
        }
      : {}),
  });

  // D-07 primary: OSC 0/2 title → process slot.
  term.onTitleChange((title) => {
    s.lastOscTitleAt = Date.now();
    reportPaneProc(s, title);
  });
  term.onBell(() => s.sink.bell());
  term.registerLinkProvider(filePathLinkProvider(term));
  // Keystrokes → PTY. First input fires the sink's one-shot (A6 restore
  // banner dismiss) guarded by the SESSION flag, not the component's.
  term.onData((d) => {
    if (!s.firstInputFired) {
      s.firstInputFired = true;
      s.sink.onFirstInput();
    }
    s.transport.write(new TextEncoder().encode(d));
  });

  // A6: seed restored scrollback before the shell spawns (context only).
  if (args.restoredScrollback && args.restoredScrollback.length > 0) {
    term.write(args.restoredScrollback.join('\r\n') + '\r\n');
  }

  // paneId-keyed registries — these keep working while the pane is detached
  // (scrollback autosave + theme broadcasts reach background sessions).
  registerTerminal(args.paneId, term);
  registerScrollbackProvider(args.paneId, () => {
    const buf = term.buffer.normal;
    const lines: string[] = [];
    const totalRows = buf.length;
    for (let i = 0; i < totalRows; i++) {
      const line = buf.getLine(i);
      if (line) {
        lines.push(line.translateToString(true));
      }
    }
    // Trim trailing empty lines (xterm pads the buffer to viewport height).
    while (lines.length > 0 && lines[lines.length - 1].trim() === '') {
      lines.pop();
    }
    return lines;
  });

  trackPaneSession(s);
  return s;
}

/**
 * Mount the session into a component's body slot. First adoption opens the
 * terminal (xterm must measure inside live DOM) and loads CanvasAddon
 * strictly AFTER open (D-01 Pitfall 2). Re-adoption just moves the host
 * element (appendChild relocates it from any previous parent), refits, and
 * repaints. Returns the owner token the adopter must pass to release.
 */
export function adoptPaneSession(
  s: PaneSession,
  slot: HTMLDivElement,
  sink: PaneSink,
  keyHandler: (e: KeyboardEvent) => boolean,
  settings: AppearanceSettings,
): symbol {
  slot.appendChild(s.hostEl);
  if (!s.opened) {
    s.term.open(s.hostEl);
    // D-01 Pitfall 2: CanvasAddon MUST load strictly AFTER term.open().
    s.term.loadAddon(new CanvasAddon());
    s.opened = true;
    s.fitAddon.fit();
  } else {
    s.fitAddon.fit();
    s.term.refresh(0, Math.max(0, s.term.rows - 1));
  }
  s.sink = sink;
  // Single-slot in xterm — the last adopter's handler wins (correct: the
  // session has exactly one live component at a time).
  s.term.attachCustomKeyEventHandler(keyHandler);
  // Idempotent; covers appearance changes that landed while detached.
  applyAppearanceToTerminal(s.term, settings);
  const token = Symbol('pane-adoption');
  s.owner = token;
  return token;
}

/**
 * Component onCleanup path. No-op unless the token matches (a swap's new
 * adopter may have claimed the session before the old component disposes).
 * Detaches; NEVER kills — destruction is paneSessionRegistry.destroyPaneSession.
 */
export function releasePaneSession(s: PaneSession, token: symbol): void {
  if (s.owner !== token) return;
  s.owner = null;
  s.sink = NOOP_SINK;
  s.hostEl.remove();
}

/**
 * Spawn the session's process (managed agent / agent / plain shell from the
 * frozen creation config). Guarded — adoption after a move never respawns.
 */
export async function spawnPaneSession(s: PaneSession): Promise<void> {
  if (s.spawned) return;
  s.spawned = true;
  const { cwd, agentConfig, workspacePath } = s.cfg;
  // VBUS-03 (D-11): every pane gets a VOSS_AGENT_ID slug before any agent
  // runs. Respawns reuse the pane's existing slug (D-13 best-effort).
  const vossAgentId =
    slugByPaneId()[s.paneId] ?? mintSlug(agentConfig?.cliBinary);
  registerSlug(s.paneId, vossAgentId);
  if (agentConfig) {
    // VCKP-13: the managed toggle routes to the SANDBOXED command — never a
    // no-op security switch. Unmanaged configs keep the unchanged spawnAgent.
    if (agentConfig.managed) {
      await s.transport.spawnManagedAgent({
        rows: s.term.rows,
        cols: s.term.cols,
        cwd,
        paneId: s.paneId,
        workspacePath,
        ...agentConfig,
        scope: agentConfig.scope ?? cwd ?? '',
        tier: agentConfig.tier ?? 'B',
        vossAgentId,
      });
    } else {
      await s.transport.spawnAgent({
        rows: s.term.rows,
        cols: s.term.cols,
        cwd,
        paneId: s.paneId,
        workspacePath,
        ...agentConfig,
        vossAgentId,
      });
    }
  } else {
    await s.transport.spawn({
      rows: s.term.rows,
      cols: s.term.cols,
      cwd,
    });
  }
  s.dot = 'running';
  s.sink.setDot('running');
}

/** ExitBanner restart: same transport/Channel — scrollback preserved. */
export async function respawnPaneSession(s: PaneSession): Promise<void> {
  s.transport.kill();
  s.lastExitCode = null;
  s.dot = 'loading';
  s.sink.setExitCode(null);
  s.sink.setDot('loading');
  s.spawned = false;
  await spawnPaneSession(s);
}
