import { invoke, Channel } from '@tauri-apps/api/core';

/**
 * Tauri PTY transport: owns the D-02 flood-contract frontend mechanisms —
 * per-requestAnimationFrame coalescing AND watermark backpressure (BOTH
 * required, complementary). The xterm `write` is injected so this layer is
 * unit-testable without a real Terminal.
 *
 * Mirrors the Rust `PtyEvent` (serde tag = "type", snake_case) from A2-02.
 */
export type PtyEvent =
  | { type: 'data'; bytes: number[] }
  | { type: 'exit'; code: number }
  | { type: 'fg_process'; name: string }
  | { type: 'title_change'; title: string }
  | { type: 'budget_update'; tokens_used: number; token_limit: number | null; cost_usd: number; iteration: number; model: string }
  | { type: 'context_update'; system_tokens: number; conversation_tokens: number; total_tokens: number; token_limit: number | null; files: FileContextEntry[] };

export type FileContextEntry = {
  path: string;
  tokens: number;
  state: 'full' | 'compressed' | 'dropped';
  pinned: boolean;
};

export type ContextData = {
  system_tokens: number;
  conversation_tokens: number;
  total_tokens: number;
  token_limit: number | null;
  files: FileContextEntry[];
};

export type BudgetState = {
  tokens_used: number;
  token_limit: number | null;
  cost_usd: number;
  iteration: number;
  model: string;
};

export interface AgentConfig {
  cliBinary: string;
  cliArgs: string[];
  sessionId: string;
  /** VCKP-13 managed launch: route to spawn_managed_agent (OS scope-sandbox). */
  managed?: boolean;
  /** Sandbox write-scope (absolute path) — required for a managed launch. */
  scope?: string;
  /** Honest capability tier recorded for this launch (resolveTier output). */
  tier?: 'A' | 'B' | 'C';
  /** Budget-kill threshold (USD): at/over → pty_kill (VCKP-13c). */
  budgetUsd?: number;
  /** VBUS-03 agent identity slug injected as VOSS_AGENT_ID (D-11/D-12). */
  vossAgentId?: string;
}

/** Result of `spawn_managed_agent` — `tier` is the EFFECTIVE tier (downgraded
 * to 'C' when no sandbox tool exists on the host; never overstated). */
export type ManagedSpawnResult = {
  pty_id: string;
  tier: 'A' | 'B' | 'C';
  sandboxed: boolean;
};

/** D-02 watermark thresholds — locked constants (do not tune). */
export const HIGH_WATERMARK = 100_000; // 100 KB → pause
export const LOW_WATERMARK = 10_000; //  10 KB → resume

export interface PtyTransportOpts {
  /** xterm `term.write` (data, callback). Injected for testability. */
  write: (data: Uint8Array, cb?: () => void) => void;
  onExit?: (code: number) => void;
  onFgProcess?: (name: string) => void;
  onTitle?: (title: string) => void;
  onBudgetUpdate?: (data: BudgetState) => void;
  onContextUpdate?: (data: ContextData) => void;
  agentPaneId?: string;
  workspacePath?: string;
  /** VCKP-13c budget-kill: cost_usd at/over this → pty_kill the pane. */
  budgetKillLimitUsd?: number;
  onBudgetKill?: (costUsd: number) => void;
}

function mergeChunks(chunks: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const c of chunks) total += c.length;
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.length;
  }
  return out;
}

export class PtyTransport {
  private channel = new Channel<PtyEvent>();
  private sessionId: string | null = null;
  private pending: Uint8Array[] = [];
  private rafPending = false;
  private watermark = 0;
  private opts: PtyTransportOpts;

  constructor(opts: PtyTransportOpts) {
    this.opts = opts;
    this.channel.onmessage = (ev: PtyEvent) => this.handle(ev);
  }

  private handle(ev: PtyEvent): void {
    switch (ev.type) {
      case 'data': {
        const buf = Uint8Array.from(ev.bytes);
        this.pending.push(buf);
        this.watermark += buf.length;
        if (!this.rafPending) {
          this.rafPending = true;
          requestAnimationFrame(() => this.flush());
        }
        // Backpressure: too much buffered → tell Rust to stop reading.
        if (this.watermark > HIGH_WATERMARK && this.sessionId) {
          void invoke('pty_pause', { sessionId: this.sessionId });
        }
        break;
      }
      case 'exit':
        this.opts.onExit?.(ev.code);
        if (this.opts.agentPaneId) {
          void invoke('mark_agent_stopped', {
            paneId: this.opts.agentPaneId,
            workspacePath: this.opts.workspacePath ?? null,
          }).catch((e) =>
            console.error('[voss-app] agent registry exit update failed:', e),
          );
        }
        break;
      case 'fg_process':
        this.opts.onFgProcess?.(ev.name);
        break;
      case 'title_change':
        this.opts.onTitle?.(ev.title);
        break;
      case 'budget_update': {
        this.opts.onBudgetUpdate?.({
          tokens_used: ev.tokens_used,
          token_limit: ev.token_limit,
          cost_usd: ev.cost_usd,
          iteration: ev.iteration,
          model: ev.model,
        });
        // VCKP-13c budget-kill — the universal (tier-C-and-up) hard control:
        // at/over the limit, terminate the pane via the existing pty_kill path.
        const limit = this.opts.budgetKillLimitUsd;
        if (limit != null && ev.cost_usd >= limit && this.sessionId) {
          this.opts.onBudgetKill?.(ev.cost_usd);
          this.kill();
        }
        break;
      }
      case 'context_update':
        this.opts.onContextUpdate?.({
          system_tokens: ev.system_tokens,
          conversation_tokens: ev.conversation_tokens,
          total_tokens: ev.total_tokens,
          token_limit: ev.token_limit,
          files: ev.files,
        });
        break;
    }
  }

  /** Merge a frame's worth of chunks into ONE xterm write (coalescing). */
  private flush(): void {
    this.rafPending = false;
    if (this.pending.length === 0) return;
    const merged = mergeChunks(this.pending);
    this.pending = [];
    this.opts.write(merged, () => {
      this.watermark = Math.max(this.watermark - merged.length, 0);
      if (this.watermark < LOW_WATERMARK && this.sessionId) {
        void invoke('pty_resume', { sessionId: this.sessionId });
      }
    });
  }

  async spawn(o: {
    rows: number;
    cols: number;
    cwd?: string;
  }): Promise<string> {
    this.sessionId = await invoke<string>('spawn_pty', {
      onData: this.channel,
      rows: o.rows,
      cols: o.cols,
      cwd: o.cwd,
    });
    return this.sessionId;
  }

  async spawnAgent(o: {
    rows: number;
    cols: number;
    cwd?: string;
    paneId: string;
    workspacePath?: string;
  } & AgentConfig): Promise<string> {
    this.sessionId = await invoke<string>('spawn_agent', {
      onData: this.channel,
      rows: o.rows,
      cols: o.cols,
      cwd: o.cwd,
      cliBinary: o.cliBinary,
      cliArgs: o.cliArgs,
      sessionId: o.sessionId,
      paneId: o.paneId,
      workspacePath: o.workspacePath,
      vossAgentId: o.vossAgentId ?? null,
    });
    return this.sessionId;
  }

  /** VCKP-13: managed launch under the OS scope-sandbox. Mirrors spawnAgent
   * but invokes `spawn_managed_agent` with the scope + requested tier; returns
   * the EFFECTIVE tier (honestly downgraded when no sandbox tool exists). */
  async spawnManagedAgent(o: {
    rows: number;
    cols: number;
    cwd?: string;
    paneId: string;
    workspacePath?: string;
    scope: string;
    tier: 'A' | 'B' | 'C';
  } & AgentConfig): Promise<ManagedSpawnResult> {
    const res = await invoke<ManagedSpawnResult>('spawn_managed_agent', {
      onData: this.channel,
      rows: o.rows,
      cols: o.cols,
      cwd: o.cwd,
      cliBinary: o.cliBinary,
      cliArgs: o.cliArgs,
      sessionId: o.sessionId,
      paneId: o.paneId,
      workspacePath: o.workspacePath,
      scope: o.scope,
      tier: o.tier,
      vossAgentId: o.vossAgentId ?? null,
    });
    this.sessionId = res.pty_id;
    return res;
  }

  write(bytes: Uint8Array): void {
    if (!this.sessionId) return;
    void invoke('pty_write', {
      sessionId: this.sessionId,
      data: Array.from(bytes),
    });
  }

  resize(rows: number, cols: number): void {
    if (!this.sessionId) return;
    void invoke('pty_resize', { sessionId: this.sessionId, rows, cols });
  }

  kill(): void {
    if (!this.sessionId) return;
    void invoke('pty_kill', { sessionId: this.sessionId });
    this.sessionId = null;
  }

  /** D-07 fallback: resolve the foreground process name via the Rust pgid poll. */
  async fgProcess(): Promise<string | null> {
    if (!this.sessionId) return null;
    return invoke<string | null>('get_fg_process', {
      sessionId: this.sessionId,
    });
  }
}
