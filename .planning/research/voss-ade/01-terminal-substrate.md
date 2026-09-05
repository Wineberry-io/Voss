# Voss ADE Deep Dive: Terminal Substrate and tmux Engine

> Research date: 2026-07-19
> Scope: tmux Control Mode, PTY fidelity, persistence/recovery, alternate screen, scrollback, resize/focus, shell integration, flow control, SSH/mosh, and mux alternatives
> Method: five varied discovery searches (technical, implementation, question-form, recent, and criticism), recursive term searches, and targeted official/GitHub/news/community passes. 26 useful sources were fetched or inspected; primary documentation and repositories are weighted most heavily.

## Key Findings

1. **Voss should use tmux as the live process/session authority on supported Unix hosts, not merely copy tmux keybindings or visual conventions.** The missing product capability in the current app is not another split-pane UX. It is a process owner that survives the Tauri/webview lifecycle and can be reattached after the GUI exits or crashes. tmux already provides that boundary: its server owns PTYs and child processes, while disposable clients communicate over a socket and can detach/re-attach ([tmux repository](https://github.com/tmux/tmux), [Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started)).

2. **“tmux-backed by default” must still be a backend choice, not an application-wide dependency.** tmux 3.6b supports OpenBSD, FreeBSD, NetBSD, Linux, macOS, and Solaris, not native Windows ([tmux releases](https://github.com/tmux/tmux/releases), [tmux repository](https://github.com/tmux/tmux)). Voss should retain its existing `portable-pty` backend for Windows, missing/unsupported tmux, recovery mode, and users who explicitly choose a raw ephemeral PTY. Arbitrary shells and CLI agents must behave identically through either backend.

3. **Control Mode is the correct integration seam, but it is a protocol, not a terminal engine.** `tmux -CC` emits command reply blocks and asynchronous `%...` notifications, with pane output octal-escaped and tagged by stable pane ID. It was created specifically so iTerm2 could render tmux sessions in native GUI windows ([Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode), [iTerm2 integration](https://iterm2.com/3.3/documentation-tmux-integration.html)). Voss must still own protocol parsing, xterm rendering, input translation, GUI lifecycle, and resynchronization.

4. **Keep live topology canonical in tmux, but keep presentation metadata in Voss.** The current Voss binary split tree maps naturally to tmux's session/window/pane tree. Recommended mapping: Voss workspace -> tmux session; Voss layout/tab -> tmux window; Voss terminal leaf -> tmux pane. Split, resize, close, focus, and spawn become tmux transactions; the Solid store reconciles from the resulting IDs and notifications. Voss can retain pane headers, role colors, budgets, orchestration state, and saved layout intent without maintaining a second live process topology.

5. **Do not attach implicitly to the user's normal tmux server.** Use a Voss-owned socket namespace and a minimal controlled config. The tmux FAQ is explicit that anyone with socket access is fully trusted and can control the server; read-only/access flags are convenience controls, not a security boundary ([tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)). Offer “Import/attach existing tmux session” as an explicit separate mode.

6. **The current Voss session restore is visual reconstruction, not session persistence.** Rust's in-memory `PtyRegistry` owns every live child, and reader EOF removes it. The saved schema contains the grid and optional line snapshots only; it intentionally omits PTY IDs, running processes, and environment. Closing/crashing the desktop process therefore loses live local commands. tmux changes this from “recreate a shell and print old text” to actual detach/re-attach.

7. **Backpressure needs redesign at the mux boundary.** Today the frontend pauses the Rust PTY reader at 100 KB and resumes at 10 KB. Pausing the PTY reader can eventually backpressure the child process. Control Mode provides `pause-after`, `%pause`, `%continue`, and `%extended-output`; tmux continues to own the pane and expects a slow client to recover using `capture-pane` ([Control Mode flow control](https://github.com/tmux/tmux/wiki/Control-Mode)). Voss needs an explicit per-pane desync/re-hydration state, not just a pause boolean.

8. **Reattach and recovery require a terminal-state test program, not only scrollback replay.** tmux can capture normal history or alternate-screen contents, include attributes, preserve spaces/wraps, and capture incomplete escape sequences ([Advanced Use](https://github.com/tmux/tmux/wiki/Advanced-Use), [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)). A robust client still has to restore cursor/mode/title/mouse/focus state and then resume incremental output. This is the highest technical risk.

9. **Shell integration should be optional metadata, never a requirement for terminal correctness.** OSC 133 can mark prompt start, command start/execution, and completion/exit status ([Windows Terminal shell integration](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration)). VS Code demonstrates the richer value: reliable CWD, exact command lines, command navigation, accessibility, and failure marks, with nonce-based spoofing protection for trusted command metadata ([VS Code shell integration](https://code.visualstudio.com/docs/terminal/shell-integration)). Plain PTY bytes remain the compatibility baseline.

10. **Remote support should be layered, not conflated.** Running `ssh` inside a local tmux pane preserves only the local SSH client. True remote process persistence requires tmux on the remote host and a reconnectable `ssh host tmux -CC attach` control transport. Mosh is complementary for roaming but synchronizes visible screen state, not scrollback; its own documentation recommends tmux/screen when full history matters ([Mosh](https://mosh.org/)).

11. **Warp's evolution is a warning against overloading tmux with rich IDE semantics.** Warp's legacy remote path used tmux Control Mode for background commands, but its current SSH architecture installs an optional companion server for file watching, Git, indexing, and incremental structured updates ([Warp SSH](https://docs.warp.dev/terminal/warpify/ssh)). Voss should use tmux for terminal/session authority and its optional Voss sidecar/protocol for orchestration data, not scrape terminal output to infer the agent organization model.

12. **Zellij is the strongest strategic alternative, not the right first backend.** Zellij 0.44 now has native Windows support, HTTPS terminal-to-terminal attach, read-only sharing, CLI automation, screen dumping, and real-time pane subscriptions ([Zellij 0.44](https://zellij.dev/news/remote-sessions-windows-cli/)). It also distinguishes resurrection from live persistence: after process loss, it recreates layouts and discovered commands, optionally viewport/scrollback, with commands gated behind confirmation ([Session Resurrection](https://zellij.dev/documentation/session-resurrection)). Its richer protocol is attractive, but adding two mux authorities before the tmux adapter stabilizes would multiply fidelity and lifecycle complexity.

## Recommendation: Authority Decision

### Decision

Adopt a **transport-neutral `SessionEngine` with tmux as the default persistent Unix engine and the existing native PTY implementation as a first-class fallback**.

Do not ship a tmux-themed direct-PTY terminal and call it tmux-powered. Keybindings, pane splitting, and saved scrollback reproduce the least differentiated parts of tmux while leaving the central failure mode unchanged: the desktop process remains the process owner.

Do not make Voss orchestration the pane runtime. Every pane starts as a normal shell or arbitrary argv. A user can run Claude Code, Codex, Gemini CLI, OpenCode, SSH, Neovim, a REPL, or any other terminal program. Voss-aware metadata and the orchestration console attach only when explicitly enabled or detected.

### Authority Matrix

| Concern | Authority | Rationale |
|---|---|---|
| Child process and PTY lifetime | tmux server on supported Unix; direct backend otherwise | Survives GUI detach/crash without a Voss daemon rewrite |
| Live session/window/pane IDs | tmux | Stable `$`, `@`, `%` IDs are unambiguous and externally inspectable |
| Live split topology and terminal cell sizes | tmux | Avoids dual writers and keeps native tmux attach truthful |
| GUI workspace placement, headers, colors, orchestration panels | Voss | Client-specific presentation is not terminal process state |
| xterm viewport, selection, find overlay, local accessibility | Voss/xterm | Control Mode does not render a terminal UI |
| Normal and alternate-screen canonical cell state | tmux internally; Voss renderer mirrors it | tmux must be the recovery source after client loss |
| Saved layouts after reboot | Voss declarative session file | tmux does not survive OS reboot |
| Agent budgets, scope, board, audit, Voss session tree | Voss harness/protocol | Must not be inferred from terminal text |
| Command/CWD marks | Optional shell integration | Enhances arbitrary shells without becoming a prerequisite |

### Why Not a Voss PTY Daemon First?

A custom daemon could preserve the current exact xterm/PTY semantics and work on Windows, but it would require Voss to own:

- daemon discovery, socket authentication, version negotiation, upgrades, cleanup, and crash recovery;
- durable pane/session topology and multi-client attachment;
- terminal-state snapshots and output replay;
- remote bootstrap and reconnection;
- signals, job control, environment refresh, and process reaping across platforms;
- a new protocol and compatibility contract.

That is effectively implementing the difficult half of tmux/WezTerm's mux. It is justified only if a Control Mode prototype fails the fidelity gate or if native Windows persistence becomes a near-term release requirement.

## Detailed Notes

### 1. Current Voss Terminal Substrate

The existing architecture is a credible direct PTY terminal but not yet a persistent terminal engine:

- `crates/voss-app-core/src/pty/mod.rs` opens one native PTY per pane with `portable_pty`, starts `$SHELL` or arbitrary argv, writes raw bytes, resizes the master, kills/reaps the child, and stores handles in a process-local `HashMap`.
- `apps/voss-app/src/pane/pty-ipc.ts` transports byte arrays over a Tauri channel, batches writes once per animation frame, and invokes pause/resume at fixed frontend watermarks.
- `apps/voss-app/src/pane/paneSession.ts` creates xterm 5.5 with a 10,000-line buffer, Fit/Search/WebLinks/Canvas add-ons, keeps sessions alive across Solid component remounts, and sends xterm input directly to the PTY.
- `apps/voss-app/src/pane/paneSessionRegistry.ts` deliberately kills the process only on explicit pane destruction or workspace teardown. This protects against UI remounts, but it cannot protect against desktop-process exit.
- `crates/voss-app-core/src/session.rs` saves a versioned grid plus at most a line-array snapshot. Structural saves carry `scrollback: null`; full quit saves capture rendered text. This is useful UX context, not executable session state.
- Resize currently uses a 150 ms debounce before `fit()` plus `pty_resize`. That is reasonable for a direct PTY, but a mux client must also reconcile tmux `%layout-change` notifications and other attached clients.

Two current details need correction before or during the mux work:

1. The Voss OSC extractor in `pty/reader.rs` is not actually fragmentation-safe. It has no carry buffer, passes incomplete OSC fragments to display, and can extract only one sequence from an 8 KiB read. Control Mode adds another framing layer and makes a streaming byte parser mandatory.
2. Plain shell creation currently injects `VOSS_EMBEDDED=1`. To honor the no-adoption product boundary, generic panes should receive neutral terminal metadata such as `TERM_PROGRAM`, while Voss-specific environment variables should be injected only into explicit Voss launches.

### 2. Control Mode Mechanics

`tmux -C` starts a textual control client; `-CC` additionally disables canonical terminal handling for application integration. The client sends normal tmux commands terminated by newlines. Synchronous replies are framed by `%begin` and `%end`/`%error`, while asynchronous notifications begin with `%` ([Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode), [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)).

Important properties for Voss:

- Use stable IDs, never indexes or names, in the runtime model.
- Treat the stream as bytes. Pane output may be invalid UTF-8 and contains octal escapes for control characters and backslashes.
- Commands are serialized on the stream, but asynchronous notifications can arrive around reply blocks. The parser must model both.
- `%output` is application output as tmux received it. Output generated by tmux's own copy/choose mode is not sent, so Voss must provide its own find/copy/session picker UI.
- `refresh-client -C width,height` makes a Control Mode client participate in sizing. Without it, that client does not influence window size.
- `refresh-client -B` format subscriptions can emit property changes at most once a second. Use them for low-frequency CWD, title, active command, flags, and exit status, not raw rendering.
- Input can be encoded without shell quoting through `send-keys -H` hexadecimal ASCII bytes. Literal UTF-8 is supported with `-l`; arbitrary byte handling still needs tests ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)).

The open WezTerm tracking issue is a useful implementation checklist: attach as a mux domain; query sessions/windows/panes; synthesize GUI objects; implement scrollback/line rendering; translate key events; translate split/spawn actions; decide how to hide the hosting control pane; and support SSH bootstrap ([WezTerm issue #336](https://github.com/wezterm/wezterm/issues/336)). The issue remains open as of this research, so community reports of usable nightly support should not be treated as a mature dependency.

### 3. Proposed Engine Boundary

Use a Rust trait/domain boundary rather than allowing Solid components to know tmux commands:

```rust
trait SessionEngine {
    fn capabilities(&self) -> EngineCapabilities;
    async fn list_sessions(&self) -> Result<Vec<SessionInfo>>;
    async fn create_or_attach(&self, spec: SessionSpec) -> Result<SessionHandle>;
    async fn spawn_pane(&self, target: WindowId, spec: SpawnSpec) -> Result<PaneId>;
    async fn write(&self, pane: PaneId, bytes: &[u8]) -> Result<()>;
    async fn resize_client(&self, session: SessionId, size: CellSize) -> Result<()>;
    async fn resize_pane(&self, pane: PaneId, size: CellSize) -> Result<()>;
    async fn focus(&self, pane: PaneId) -> Result<()>;
    async fn signal(&self, pane: PaneId, signal: Signal) -> Result<()>;
    async fn snapshot(&self, pane: PaneId) -> Result<PaneSnapshot>;
    async fn detach(&self, session: SessionId) -> Result<()>;
    async fn kill_pane(&self, pane: PaneId) -> Result<()>;
    fn subscribe(&self, session: SessionId) -> EventStream;
}
```

Backends:

- `TmuxEngine`: process/session authority through a Voss-owned tmux server and one Control Mode client per attached Voss workspace.
- `DirectPtyEngine`: adapted from the current `PtyRegistry`; semantics explicitly labeled ephemeral across app exit.
- Later only, if justified: `VossDaemonEngine`, `ZellijEngine`, or a remote Voss terminal service.

The frontend should receive typed events such as `PaneOutput`, `PaneSnapshot`, `PaneExited`, `TopologyChanged`, `FocusChanged`, `TitleChanged`, `CwdChanged`, `LagChanged`, and `EngineDisconnected`. It should never parse tmux response strings.

### 4. tmux Server and Metadata Design

Use an isolated server socket such as `tmux -L voss-<uid>` or an explicit `-S` path under a mode-0700 Voss runtime directory. Start it with a generated minimal config rather than inheriting arbitrary user status bars, hooks, plugins, and keybindings. This avoids collisions while leaving the user's normal tmux untouched.

Store Voss mappings in tmux user options:

- session: `@voss-workspace-id`, project root, schema version;
- window: `@voss-layout-id` or GUI tab ID;
- pane: `@voss-pane-id`, optional agent identity, launch kind;
- never store secrets, auth tokens, or full prompts in tmux options.

At startup:

1. Probe `tmux -V` and required features.
2. Connect to the Voss socket; create it if absent.
3. List sessions/windows/panes with explicit `-F` formats and escaped values.
4. Match stable Voss user options to saved workspace state.
5. Adopt live panes; do not spawn replacement shells for matched panes.
6. Snapshot and render each adopted pane before accepting input.
7. Subscribe to topology and metadata changes.

On app window close, detach the control client by default. On explicit “Close pane/session,” kill the tmux object after confirmation. This distinction must be visible and testable.

tmux persistence ends when its server exits or the OS reboots. Voss must use exact language:

- **Detach/reattach:** same live process and PTY.
- **Restore/resurrect:** new processes reconstructed from saved declarations after reboot/server loss.
- **Replay:** historical output/audit, not a live process.

### 5. Terminal Fidelity and Alternate Screen

tmux presents `TERM=tmux-256color` or a related tmux/screen description to child applications; the outer client must accurately advertise its capabilities. The tmux FAQ says most display problems are incorrect `TERM` values ([tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)). Voss should not hard-code `xterm-256color` through the full stack once tmux is in the middle.

Required capability work:

- generate or validate outer `terminal-features` for RGB color, styled underlines, cursor style/color, hyperlinks, focus reporting, synchronized updates, clipboard, and graphics passthrough;
- support `alternate-screen` and snapshot the active alternate buffer separately from normal history;
- treat xterm normal and alternate buffers correctly; xterm defines the alternate screen as a display-sized buffer intended for programs such as editors ([xterm control sequences](https://www.x.org/docs/xterm/ctlseqs.pdf));
- decide a policy for `allow-passthrough`. tmux can permit DCS passthrough only for visible panes or all panes, but passthrough sequences can reach the outer terminal and need a security/capability review ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html));
- support bracketed paste, mouse protocols, focus in/out, keyboard protocol variants, Unicode width, combining characters, emoji, OSC 8, OSC 52, synchronized output, and title/CWD sequences;
- do not claim Kitty graphics or SIXEL parity until tested end to end through tmux and xterm.

Focus is not cosmetic. tmux can request and forward focus events to applications when `focus-events` is enabled, and exposes pane-focus hooks ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)). When the user moves between Voss panes or the app gains/loses OS focus, Voss must update the tmux active pane/client focus state so editors and TUIs receive correct FocusIn/FocusOut behavior.

### 6. Scrollback, Snapshot, and Re-hydration

There are three different histories:

1. tmux pane history, whose default limit is 2,000 lines unless configured;
2. xterm client scrollback, currently 10,000 lines in Voss;
3. Voss saved close-time text, currently capped to 2,000 lines.

Choose tmux history as canonical for live tmux-backed sessions and set an explicit Voss default (for example 20,000 lines, subject to profiling). xterm should be a cache/view of that history. Avoid divergent “same pane, different history” behavior after reattach.

Snapshot algorithm to prototype:

1. mark pane `hydrating` and buffer new `%output` by sequence/order;
2. query whether alternate screen is active and current cursor/mode metadata;
3. `capture-pane` the applicable normal history or alternate buffer with attributes, trailing spaces, wraps, and pending escape sequence as needed;
4. reset/rebuild the xterm model from the snapshot;
5. apply cursor/title/mouse/focus state that capture output does not encode sufficiently;
6. replay buffered output and mark synchronized.

`capture-pane -a` captures alternate-screen content but cannot access normal history at the same time; `-e`, `-C`, `-N`, `-J`, and `-P` change attribute, escaping, whitespace/wrap, and incomplete-sequence behavior ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)). A capture is not automatically an exact serialized terminal state. Fidelity must be proven with a test matrix.

After OS reboot, do not auto-run discovered commands. Zellij's safer precedent is to restore layout/viewport and put commands behind an explicit Enter-to-run gate ([Zellij Session Resurrection](https://zellij.dev/documentation/session-resurrection)). This matters especially for agent CLIs, deploy commands, and scripts with side effects.

### 7. Performance and Backpressure

Control Mode has two separate pressure points:

- tmux server -> Rust control client;
- Rust event fan-out -> Tauri channel -> xterm renderer.

Recommended design:

- one dedicated async task owns and parses each control connection;
- incremental byte parser with bounded allocations; never `read_to_string`;
- per-pane bounded byte queues and aggregate connection limits;
- coalesce UI deliveries on animation frames as the current frontend does;
- use `pause-after` and `%extended-output` lag age as the tmux/server mechanism;
- mark panes desynchronized on `%pause`; recover from tmux state before continuing;
- turn output “off” for panes/workspaces with no interested renderer only if snapshot re-hydration is proven;
- keep process lifecycle and control replies flowing even when a pane renderer is slow;
- record queue depth, output bytes/sec, parser time, xterm callback latency, dropped/resync count, and max event-loop stall.

The current “pause before next blocking read” implementation is not sufficient for a multiplexed connection: blocking a single control reader would stall notifications and output for every pane on that client. Pressure must be per pane above the shared parser.

Performance gates should cover idle CPU with 1/8/32 panes, `yes`/large build output, rapid split/close, full-screen TUI redraw, hidden workspaces, app minimize/restore, and control-client reconnect. A correctness gate is more important than a headline throughput number: a build or agent must not hang merely because its pane is hidden.

### 8. Resize and Multi-client Semantics

The current app derives cell sizes independently for each xterm leaf. Under tmux, the canonical size is produced by the tmux window layout:

- overall workspace cell size -> `refresh-client -C width,height`;
- split drag/keyboard resize -> tmux `resize-pane` or layout transaction;
- tmux `%layout-change` -> update Solid ratios and refit xterm leaves;
- avoid frontend optimistic state becoming a second authority; show immediate drag preview, commit to tmux, then reconcile.

tmux can choose largest, smallest, latest, or manual attached-client sizing. iTerm2 documents a real consequence: windows in a tmux session share size constraints, and a smaller attached client can create unused gray areas ([iTerm2 tmux integration](https://iterm2.com/3.3/documentation-tmux-integration.html)). Voss should default the Voss-owned server to a deterministic policy and explicitly define what happens when a normal terminal client attaches.

Recommended initial policy: one writable Voss GUI client determines size; external attaches are supported for observation/recovery but may change size only when explicitly promoted. Never present tmux `server-access` read-only as isolation; it is only protection against accidental trusted input.

### 9. Shell Integration

Add a small, reversible integration for bash, zsh, fish, and PowerShell, but make refusal/failure harmless.

Baseline OSC 133 events:

- prompt start;
- command input start/end;
- command execution start;
- command completion with exit status.

Optional fields:

- current working directory;
- exact command line, protected with a per-session nonce before Voss treats it as trusted;
- host/user/SSH context;
- command duration and semantic output ranges.

Benefits include command-block navigation, “copy command/output,” rerun, per-command exit marks, accurate split CWD, structured search, notifications when a command ends, and cleaner agent activity detection. VS Code notes that polling CWD is poor for performance and impossible on Windows without prompt heuristics, while integration makes it reliable ([VS Code shell integration](https://code.visualstudio.com/docs/terminal/shell-integration)).

Do not parse prompts with regex as the primary path. Do not use command metadata to bypass paste guards or permission gates without nonce validation. Do not install scripts without consent; support one-session injection, documented dotfile setup, and no-integration mode.

### 10. Remote SSH and Mosh

Support three explicit modes:

| Mode | Process authority | Persistence behavior |
|---|---|---|
| `ssh host` inside local Voss pane | local tmux owns SSH client; remote host owns remote child | local pane survives Voss GUI; remote command may die when SSH connection dies |
| Voss remote tmux attach over SSH | remote tmux owns remote PTYs | remote work survives local GUI and SSH reconnect |
| `mosh host` inside local/remote pane | mosh server/client state synchronization | roaming and sleep recovery, but visible state only; not full scrollback |

For remote Control Mode:

- bootstrap with ordinary OpenSSH so existing `~/.ssh/config`, ProxyJump, agents, host verification, and hardware keys continue to work;
- require explicit consent before installing tmux remotely;
- work without enhancement when tmux is absent;
- reconnect transport without respawning the remote session;
- identify remote host + socket + tmux session independently from the local workspace ID;
- refresh environment such as `SSH_AUTH_SOCK` deliberately; tmux server environments can outlive an individual login;
- never send Control Mode commands into a normal shell after loss of framing. A recent Warp community bug report describes exactly that failure after an SSH disconnect ([Warp community report](https://www.reddit.com/r/warpdotdev/comments/1sc8zk6/bug_report_tmux_control_mode_commands_leak_into/)); it is anecdotal, but the failure class is credible.

Mosh is not an interchangeable Control Mode transport. It operates at terminal screen-state synchronization rather than delivering an ordinary reliable byte stream, and explicitly lacks complete scrollback ([Mosh](https://mosh.org/)). Let users run it normally, but use SSH for the first remote tmux controller.

### 11. Alternatives

#### Zellij

Strengths:

- modern Rust client/server implementation;
- native Windows as of 0.44;
- detachable sessions, serialization/resurrection, plugins;
- HTTPS remote attach, read-only tokens, CLI actions;
- `dump-screen` and real-time pane viewport/scrollback subscriptions, which are more directly useful to a GUI client than tmux's raw-output-plus-capture model.

Weaknesses for the first Voss release:

- a second lifecycle/protocol/topology mapping;
- smaller installed base on remote servers;
- its layouts/plugins/modes can compete with Voss's GUI model;
- “resurrection” still reruns commands rather than restoring process memory.

Action: maintain a short Zellij compatibility spike after the `SessionEngine` contract is real. Its subscribe/dump APIs are a benchmark for what a future Voss-native daemon protocol should expose.

#### WezTerm Mux

WezTerm separates GUI clients from mux domains and supports Unix sockets, SSH domains, and TLS domains. It can automatically reconnect and resume a remote terminal session after interruption, but SSH mux domains require a compatible WezTerm installation on the remote machine ([WezTerm multiplexing](https://wezterm.org/multiplexing.html)).

Strengths: Rust, GPU terminal, cross-platform mux, mature terminal model.
Weaknesses: embedding/reusing its mux as a library is not a stable product contract; remote version coupling; Voss would inherit a much larger terminal product and configuration surface.
Action: learn from its domain abstraction; do not make Voss depend on the WezTerm executable.

#### Native Voss Mux Daemon

Strengths: exact Voss protocol, native Windows path, structured screen diffs, orchestration-aware metadata, no tmux impedance mismatch.
Weaknesses: highest engineering and security burden; duplicates mature process/session machinery.
Action: defer until measured Control Mode limitations justify it. If built, its protocol should expose cell-grid snapshots/deltas rather than raw PTY replay alone.

### 12. Voss Capability Integration Without Lock-in

The terminal engine must remain useful with Voss entirely absent from the user's PATH and workflow.

Progressive enhancement layers:

1. **Raw terminal:** any shell/argv, tmux persistence, splits, scrollback, SSH, copy/find.
2. **Generic shell metadata:** optional OSC command/CWD/status marks.
3. **Agent detection:** user-owned registry identifies a running CLI; no wrapping required.
4. **Agent adapters:** optional documented hooks/ACP/MCP/CLI-specific events when the agent supports them.
5. **Voss sidecar:** budget, scope, session tree, board, review, audit, and orchestration console.

tmux pane metadata can associate an arbitrary process with Voss UI state without changing how the process is launched. Avoid aliases or shims that replace `claude`, `codex`, or other agent binaries by default. “Manage with Voss” should be an explicit promotion action on an already functional pane.

## Phased Implementation and Verification

### Phase 0: Fidelity Spike (go/no-go)

- Implement an incremental Rust Control Mode parser and fixture corpus.
- Attach to an isolated tmux session, spawn one pane, send arbitrary bytes, resize, detach, reattach, and recover snapshot.
- Run `vttest`, bash/zsh, Neovim, less, fzf, htop, SSH, and at least three existing CLI agents.
- Verify alternate screen, mouse, bracketed paste, focus, OSC 8/52, truecolor, styled underline, emoji/wide/combining text, rapid resize, and 100 MB output.
- Crash-kill only the Voss app/controller; prove the pane process continues and reattaches.

**Go gate:** zero data-corrupting parser bugs, acceptable TUI recovery, no process stalls under hidden-pane output, and a documented capability matrix. Otherwise, prototype a native Voss daemon before migrating the app.

### Phase 1: Engine Abstraction

- Extract current PTY commands behind `DirectPtyEngine` without behavior changes.
- Introduce typed IDs/events/capabilities and engine selection.
- Preserve all existing PTY tests and add backend contract tests.

### Phase 2: Local tmux Authority

- Voss-owned socket/config; version/capability negotiation.
- Create/list/attach/detach/kill sessions.
- Map workspace/window/pane topology; reconcile notifications.
- Reattach on app restart; explicit detach versus terminate UX.
- Store only non-secret Voss identity metadata in user options.

### Phase 3: Snapshot, Flow, and Shell Metadata

- Full normal/alternate snapshot hydration.
- Per-pane control-flow queues and resync.
- Optional OSC 133 integration with nonce validation.
- Command blocks, accurate CWD, completion notifications.

### Phase 4: Remote tmux

- OpenSSH bootstrap/attach and reconnect state machine.
- Consent-based remote dependency handling.
- Host/session picker and degraded raw SSH fallback.
- No direct mosh Control Mode claim.

### Phase 5: Strategic Alternatives

- Zellij 0.44 adapter feasibility against the same engine contract.
- Decide whether native Windows persistence warrants a Voss mux daemon.
- Evaluate replacing raw-byte replay with structured cell-grid snapshots/deltas.

## Notable Quotes and Data

- tmux describes Control Mode as a “simple text-only protocol” and notes that it can be parsed over SSH ([Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)).
- Control Mode pane output “may not be valid UTF-8,” so a Rust parser must preserve bytes until octal decoding is complete ([Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)).
- When a Control Mode client is paused, “it is up to the client to update the content of the pane,” for example with `capture-pane` ([Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)).
- tmux's default pane history is 2,000 lines ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)).
- iTerm2 demonstrates the intended value proposition: normal native terminal UI with tmux persistence after iTerm quits or SSH is lost ([iTerm2 tmux integration](https://iterm2.com/3.3/documentation-tmux-integration.html)).
- Mosh synchronizes only visible terminal state and recommends tmux/screen for missing scrollback ([Mosh](https://mosh.org/)).
- WezTerm calls its mux feature “young” and requires a compatible remote WezTerm for SSH domains ([WezTerm multiplexing](https://wezterm.org/multiplexing.html)).
- Zellij resurrection serializes layouts/commands and can serialize viewport/scrollback, but gates rerunning restored commands behind confirmation by default ([Zellij Session Resurrection](https://zellij.dev/documentation/session-resurrection)).
- Zellij 0.44, released 2026-03-23, added native Windows, HTTPS terminal attach, read-only sharing, CLI automation, `dump-screen`, and real-time subscriptions ([Zellij 0.44](https://zellij.dev/news/remote-sessions-windows-cli/)).
- tmux's latest fetched release was 3.6b, dated 2026-05-20; its repository reports Unix-family platforms and an ISC license ([tmux releases](https://github.com/tmux/tmux/releases), [tmux repository](https://github.com/tmux/tmux)).

## Source Credibility Notes

### High confidence

- tmux wiki, manual, source repository, changelog, and releases: authoritative behavior and current platform/version information.
- iTerm2 documentation: primary evidence from the original Control Mode GUI integration.
- Microsoft Terminal and VS Code documentation: primary implementation guidance for OSC shell integration and ConPTY caveats.
- Mosh official site/paper: primary source for state synchronization and scrollback limitations.
- WezTerm and Zellij official docs/repos/news: primary source for alternative architectures and current features.
- Local Voss source: authoritative for current implementation; observations were verified directly in the named files.

### Medium confidence

- `tmuxctl` docs and the WezTerm tracking issue: useful implementation maps, but `tmuxctl` explicitly labels its async client early and the WezTerm feature remains an open tracking issue.
- Community reports about nightly WezTerm Control Mode, tmux latency, and terminal-daemon designs: useful for discovering failure classes, not sufficient to assert product quality or prevalence.

### Low confidence / excluded from core conclusions

- Reddit claims without logs or reproducible cases. The Warp disconnect report is retained only as an example of a framing-state failure to test.
- Generic comparison/blog pages and old manuals. They added little beyond primary sources and were not used for central decisions.

## Gaps and Open Questions

1. No local tmux binary was available in this checkout environment (`tmux -V` returned no version), so no live Control Mode probe or fidelity benchmark was run in this research task.
2. Exact minimum supported tmux version remains undecided. It should be derived from the notifications, formats, terminal features, and flow-control behavior the prototype actually uses.
3. It is not yet proven that `capture-pane` plus synthesized modes can restore an arbitrary alternate-screen TUI into xterm without visual or input-state defects.
4. Arbitrary byte input through `send-keys -H` needs exhaustive coverage, especially NUL, high-bit bytes, IME/composed input, Kitty keyboard protocol, mouse, and large bracketed paste.
5. tmux behavior with Voss's existing OS sandbox wrapper needs a concrete ownership decision: sandbox the command inside a tmux pane, not the tmux server itself, and verify signal/exit reporting.
6. The current app's Windows compile story needs review. `master_raw_fd()` uses Unix types in the core PTY surface even though `portable-pty` is cross-platform.
7. A product decision is still required for external normal tmux clients: supported writable attach, read-only observation, or recovery-only. This affects sizing and focus semantics.
8. tmux memory cost under many long-history, high-output agent panes was not benchmarked.
9. Graphics support (SIXEL/Kitty/iTerm images), clipboard policy, and DCS passthrough need an explicit threat and compatibility review.
10. Remote tmux install/update ownership, compatibility negotiation, ProxyJump, agent forwarding, and enterprise restrictions need user-environment testing.
11. Zellij 0.44's `subscribe` output and Rust APIs were not protocol-audited deeply enough to estimate a real adapter.
12. Reboot resurrection needs a safe launch descriptor. Inferring the foreground command is insufficient for shells and wrapped agent CLIs.

## All Sources

1. [tmux Control Mode wiki](https://github.com/tmux/tmux/wiki/Control-Mode) - canonical protocol, output framing, notifications, sizing, subscriptions, and flow control.
2. [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html) - canonical command/options/control-mode details, including input, history, alternate screen, focus, terminal features, and passthrough.
3. [tmux repository](https://github.com/tmux/tmux) - platform support, dependencies, license, server purpose, and current project status.
4. [tmux releases](https://github.com/tmux/tmux/releases) - current fetched release, 3.6b dated 2026-05-20.
5. [tmux changelog](https://github.com/tmux/tmux/blob/master/CHANGES) - recent Control Mode and terminal capability evolution.
6. [tmux Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started) - client/server, detach, and reattach semantics.
7. [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ) - TERM guidance, socket trust boundary, release cadence, scrollback and environment caveats.
8. [tmux Advanced Use](https://github.com/tmux/tmux/wiki/Advanced-Use) - capture-pane history/attribute/escape behavior and structured format usage.
9. [iTerm2 tmux integration](https://iterm2.com/3.3/documentation-tmux-integration.html) - original native GUI Control Mode integration, persistence value, resize and configuration limitations.
10. [iTerm2 shell integration](https://iterm2.com/documentation-shell-integration.html) - shell integration behavior and tmux interaction caveats.
11. [WezTerm multiplexing](https://wezterm.org/multiplexing.html) - mux domains, Unix/SSH/TLS transports, compatible remote dependency, and reconnection.
12. [WezTerm Control Mode issue #336](https://github.com/wezterm/wezterm/issues/336) - implementation checklist and feature maturity signal.
13. [WezTerm PTY source tree](https://github.com/wezterm/wezterm/tree/main/pty) - reference architecture behind the current `portable-pty` dependency lineage.
14. [Zellij commands](https://zellij.dev/documentation/commands) - attach/list/kill session CLI behavior.
15. [Zellij session manager](https://zellij.dev/documentation/session-manager-alias.html) - session switching, exited-session resurrection, client management, and sharing controls.
16. [Zellij Session Resurrection](https://zellij.dev/documentation/session-resurrection) - exact distinction between serialized layout/command/viewport/scrollback and live process persistence.
17. [Zellij 0.44 announcement](https://zellij.dev/news/remote-sessions-windows-cli/) - native Windows, HTTPS attach, read-only sharing, automation, dump, and subscription features.
18. [Zellij changelog](https://github.com/zellij-org/zellij/blob/main/CHANGELOG.md) - client/server separation, detach, terminal compatibility, and performance history.
19. [Mosh official site](https://mosh.org/) - roaming state-synchronization design and visible-state/scrollback limitation.
20. [Mosh technical article](https://www.usenix.org/system/files/login/articles/winstein.pdf) - primary technical background and tmux/screen complement.
21. [Warp SSH documentation](https://docs.warp.dev/terminal/warpify/ssh) - current companion-server approach and legacy tmux path context.
22. [Windows Terminal shell integration](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration) - OSC 133 command lifecycle semantics.
23. [VS Code terminal shell integration](https://code.visualstudio.com/docs/terminal/shell-integration) - CWD, command metadata, accessibility, nonce validation, and ConPTY caveats.
24. [Xterm control sequences](https://www.x.org/docs/xterm/ctlseqs.pdf) - alternate buffer and terminal control-sequence baseline.
25. [`tmuxctl` Rust source/docs](https://docs.rs/tmuxctl/latest/src/tmuxctl/lib.rs.html) - typed parser responsibilities and warning that protocol parsing is separate from emulation/rendering.
26. [Warp Control Mode disconnect report](https://www.reddit.com/r/warpdotdev/comments/1sc8zk6/bug_report_tmux_control_mode_commands_leak_into/) - anecdotal community failure report used only to define a reconnect/framing test.
