# Subtopic 04: Attention Management and Agent-State UX

> Researched: 2026-07-19 | Focus: terminal-first ADEs, raw CLI compatibility, optional Voss adoption | Sources consulted: 36

## Executive Finding

The market is converging on the same user problem: once developers run several long-lived agents, the scarce resource is no longer terminal space but human attention. The winning interaction is not a large orchestration dashboard. It is a quiet, truthful status layer that answers three questions at a glance:

1. Which session needs me now?
2. Why does it need me?
3. Can I jump directly to the exact pane and resume control?

The technically defensible way to deliver this without forcing Voss adoption is a **confidence-graded event fusion model**:

- **Terminal truth** is always available: PTY alive/dead, foreground process, output activity, focus/visibility, shell prompt boundaries, command exit status, bell, and explicit terminal notifications.
- **Agent truth** is available only when the existing CLI exposes hooks, plugins, ACP/app-server events, or another explicit lifecycle channel. It can distinguish working, permission request, question, completed, failed, or background work.
- **Heuristic inference** may fill gaps, but must remain visibly qualified and must never trigger destructive or permission-bearing automation.
- **Voss truth** is an optional additional source: budgets, gates, confidence, sign-off, task dependencies, and orchestrated child state. It should enrich the same attention model rather than replace terminal or CLI state.

This architecture gives a user useful supervision on day one with any command, richer status for supported CLI agents after explicit opt-in, and Voss orchestration only when requested.

## 1. Market Pattern: Attention Is a Product Surface

### Warp

Warp now treats agent attention as a first-class multi-surface system rather than a notification toggle. Its official documentation defines three user-facing events, **Complete**, **Request**, and **Error**; renders state in tab indicators; shows focus-aware toasts; maintains a notification mailbox with unread and error filters; sends native notifications while the app is backgrounded; and deep-links every item back to the originating session. It suppresses per-child notification churn in orchestrated runs and instead notifies primarily on the parent while exposing child state in a dedicated drill-down. [Warp agent notifications](https://docs.warp.dev/agent-platform/capabilities/agent-notifications/)

This is an important distinction:

- **State** is continuous and high-volume: working, blocked, completed, errored.
- **Attention** is a durable transition requiring user awareness: a new request, completion to review, or error.
- **Notification** is only one delivery channel for an attention event.

Warp also keeps Terminal mode separable from Agent mode, supports third-party CLI agents, and lets users disable Warp AI globally. That product boundary supports the Voss requirement that terminal use must not imply adoption of a proprietary agent runtime. [Warp overview](https://docs.warp.dev/)

For ordinary commands, Warp has a separate terminal notification path: notify after a long-running command finishes, detect a password prompt, or honor application-emitted OSC 9/777 notifications. Notifications are focus-aware, avoiding a desktop alert when the user is already looking at the source session. [Warp desktop notifications](https://docs.warp.dev/terminal/more-features/notifications)

### Codemux

Codemux exposes a compact hierarchy: pane state, aggregated tab state, and aggregated workspace state. Its priority rule is explicit: a permission request outranks other states. Completion remains marked for review only when the user was not viewing the pane, and clears when the user visits it. This is a useful read/unread model rather than a claim that looking at a terminal changed the agent itself. [Codemux agent status](https://docs.codemux.org/agent-status)

Codemux is also unusually candid about interoperability. Its terminal status integration is fully supported for Claude Code through installed hooks, while other raw terminal agents may have no status indicator. Its separate structured chat integration can support more providers because it owns the event stream. That distinction is evidence against pretending that a generic PTY parser can produce provider-equivalent semantics.

### workmux and tmux-native monitors

workmux writes agent state to files, matches it to worktree paths, decorates tmux window names, and provides a status dashboard/sidebar with live output previews and jump navigation. Its state vocabulary is deliberately small: working, waiting, and done. It documents unequal support: some agents lack a waiting state because their hooks do not expose it. [workmux repository](https://github.com/raine/workmux)

The independent `tmux-agent-status` project reaches the same architecture. Claude Code and Codex use lifecycle hooks; unsupported agents can contribute status files or collector extensions. It explicitly handles a subtle case where an agent turn ends while a background process remains active, preventing premature completion. [tmux-agent-status](https://github.com/samleeney/tmux-agent-status)

This is strong practical evidence for two Voss requirements:

- A terminal engine needs **source-aware status**, not one global `active` flag.
- Completion must mean the observed unit of work reached a terminal state, not merely that output paused or the top-level model emitted a final response.

### dmux

dmux takes a different approach. It tracks output activity, then uses a lightweight remote model through OpenRouter to classify a quiet pane as waiting, dialog, or idle, with a user-typing guard to reduce false positives. It polls each pane once per second and sends focus-aware attention signals. [dmux documentation](https://dmux.ai/)

This produces broader coverage but creates a materially different trust contract:

- Terminal content is sent to an inference provider unless the feature is disabled or changed.
- Classification is probabilistic.
- A model can confuse a printed prompt, documentation example, historical scrollback, or alternate-screen redraw with live agent state.
- Cost, latency, network availability, and data handling become dependencies for a feature users expect from a local terminal.

dmux therefore demonstrates a useful optional fallback, not an acceptable source of authoritative permission or completion state for Voss.

### Paneflow

Paneflow states the progressive-enhancement contract most clearly: any binary runs in a normal PTY, supported agents report rich lifecycle state through hooks or shims, and unknown CLIs remain normal terminal panes with only process-tree and terminal-activity inference. Its state vocabulary includes thinking, waiting, finished, errored, and stalled. [Paneflow features](https://paneflow.dev/docs/features)

Paneflow also exposes pane state through local JSON-RPC, while its MCP bridge is read-only and returns terminal output as untrusted data. This separation is directly relevant to Voss: inspection and attention can be useful without granting another agent permission to type into a sibling pane. [Paneflow features](https://paneflow.dev/docs/features)

### Flowmux and BridgeSpace

Flowmux markets a deliberately quiet overview: project dashboard, agent status, model information, and response previews around real CLI agents and tmux panes. Its principle, “keep your agent workflow in the terminal,” aligns with Voss’s desired terminal-first posture. [Flowmux](https://www.flowmux.dev/)

BridgeSpace combines up to 16 agent terminals with BridgeBoard, BridgeSwarm, memory, editor, and browser surfaces. Its public material supports the demand for consolidated supervision, but gives less technical detail on how raw CLI state is determined. [BridgeSpace product](https://www.bridgemind.ai/products/bridgespace)

BridgeSpace’s release history is more informative than its marketing. It records repeated regressions where agent panes continued running but appeared blank, partial, or frozen during multi-agent output; several releases attempted scheduler changes before the product rolled back to a known-good terminal renderer. It also added recovery notifications when a resumed agent could not launch. [BridgeSpace changelog](https://www.bridgemind.ai/changelog)

The implication is critical: **rendering health and process health are separate state dimensions**. A pane may be working while its viewport is stale. A terminal-first ADE needs liveness telemetry for the PTY reader, render queue, tmux attachment, and foreground process, not only an agent badge.

## 2. The Evidence Hierarchy

### Tier 1: Explicit structured lifecycle events

These are the strongest sources because the agent runtime declares what happened:

- Claude Code lifecycle hooks can observe prompt submission, tool phases, notifications, permission requests, stop, and subagent events. Anthropic describes hooks as deterministic logic at defined lifecycle points. [Anthropic hooks overview](https://claude.com/blog/how-to-configure-hooks)
- Gemini CLI provides typed JSON events including `BeforeAgent`, `AfterAgent`, `Notification`, `SessionStart`, and `SessionEnd`; notification hooks are observability-only and cannot approve permissions. [Gemini CLI hook reference](https://geminicli.com/docs/hooks/reference/)
- OpenCode plugins can subscribe to `permission.asked`, `permission.replied`, `session.error`, `session.idle`, `session.status`, and other events. [OpenCode plugin events](https://opencode.ai/docs/plugins/)
- Codex supports a completion notification hook, while its broader hooks surface has evolved. Its own repository documents invoking a configured notification program after a turn. [Codex Rust CLI README](https://github.com/openai/codex/blob/main/codex-rs/README.md)

Even structured events are not universal or perfectly stable. One Codex issue reports that legacy completion notification payloads lacked enough parent/subagent metadata to suppress child noise reliably. [Codex event-hooks issue](https://github.com/openai/codex/issues/2109) A newer issue reports hook-trust prompts blocking orchestrated startup in some versions, with disabling hooks as the workaround. [Codex hook-trust issue](https://github.com/openai/codex/issues/24093)

Therefore Voss needs versioned adapters and explicit capability discovery, not a static claim that “Codex hooks are supported.”

### Tier 2: Standard terminal and shell semantics

OSC 133 can reliably delimit shell prompt start, prompt end, command execution, and command completion, including exit status. Contour, kitty, WezTerm, Windows Terminal, and VS Code document compatible forms. [Contour OSC 133](https://contour-terminal.org/vt-extensions/osc-133-shell-integration/), [kitty shell integration](https://sw.kovidgoyal.net/kitty/shell-integration/), [Windows Terminal shell integration](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration), [VS Code shell integration](https://code.visualstudio.com/docs/terminal/shell-integration)

OSC 133 can establish:

- the shell is waiting at a prompt;
- a command began;
- the command ended;
- the exit code, when supplied;
- command-region boundaries for navigation and review.

It cannot establish:

- that an interactive agent is asking a question rather than redrawing its TUI;
- that a spinner means useful work is progressing;
- that a model turn is semantically complete;
- that an approval prompt is safe to approve;
- that the agent has finished background tasks.

Shell integration must also be opt-in and reversible. zsh maintainers noted that users otherwise install plugins to get semantic prompt markers, motivating native shell support. [zsh OSC 133 proposal](https://www.zsh.org/mla/workers/2025/msg00106.html) Voss should not silently rewrite shell startup files merely to obtain status.

### Tier 3: Explicit terminal application notifications

OSC notification protocols are useful as an application-to-terminal signal, especially across SSH, but are fragmented:

- Warp accepts OSC 9 and OSC 777. [Warp desktop notifications](https://docs.warp.dev/terminal/more-features/notifications)
- kitty defines a richer OSC 99 protocol with identifiers, title/body chunks, focus actions, urgency, expiry, filters, and capability queries, while also accepting legacy OSC 9. [kitty desktop notifications](https://sw.kovidgoyal.net/kitty/desktop-notifications/)

These signals should create a user notification, not mutate authoritative agent state unless the emitted payload is authenticated to a known adapter. Any process can print an OSC sequence. Voss should sanitize lengths and control characters, rate-limit notifications, and attribute them to the emitting tmux pane.

### Tier 4: OS/process observations

The tmux/PTY supervisor can reliably know:

- tmux server/session/window/pane existence;
- client attachment and pane focus;
- foreground process identity and exit;
- byte activity and silence duration;
- whether the viewport renderer consumed recent output;
- whether an alternate screen is active;
- whether the terminal emitted BEL;
- whether the shell has returned to a prompt, if shell integration is active.

These facts are suitable for neutral states such as `shell-ready`, `command-running`, `process-exited`, `output-active`, `quiet`, `detached`, and `render-lagging`. They should not be relabeled as `agent-working`, `needs-permission`, or `done` without stronger evidence.

### Tier 5: Output-pattern or LLM inference

Regex and model classification can be useful for hints, especially with unsupported TUIs, but are intrinsically vulnerable to:

- prompts echoed in logs, tests, README files, or chat history;
- localization and theme changes;
- agent version changes;
- alternate-screen partial captures;
- animation that appears active while the agent is hung;
- inactivity while a network/tool call is legitimately long-running;
- arbitrary repository output spoofing a state marker.

Community reports describe silent `tmux send-keys` failures where text lands in an input buffer but Enter is absorbed by bracketed paste or a modal dialog. A successful `tmux` command therefore proves only local delivery, not that the target agent accepted or acted on the request. [tmux dispatch failure report](https://www.reddit.com/r/LocalLLaMA/comments/1shgpj8/tmuxbased_agent_coordination_a_silent_dispatch/)

Another multi-agent terminal discussion reports cascading failures when fire-and-forget pane messaging had no delivery acknowledgement. [multi-agent TUI discussion](https://www.reddit.com/r/ClaudeCode/comments/1s3mjzs/i_built_a_tui_that_replaces_tmux_for_running/)

Voss should show an `inferred` badge or reduced-confidence styling for heuristic state and never use it as permission evidence, automatic merge evidence, or proof of task completion.

## 3. A State Model for Voss

### Do not use one enum for everything

Most prototypes collapse process state, agent state, task state, attention state, and UI read state into one enum. That creates impossible transitions and misleading labels. Voss should model orthogonal dimensions:

```text
PaneHealth      = healthy | render_lagging | disconnected | exited
TerminalState   = shell_ready | command_running | interactive | quiet | unknown
AgentState      = unavailable | starting | working | waiting_input | waiting_permission
                | completed | failed | stalled | unknown
TaskState       = unbound | queued | in_progress | blocked | review | done | failed
AttentionReason = permission | question | completion | error | stalled | budget
                | gate | conflict | signoff | terminal_failure
ReadState       = seen | unseen | acknowledged | resolved
EvidenceSource  = voss_event | cli_hook | structured_protocol | shell_osc
                | process | terminal_notification | heuristic
Confidence      = authoritative | strong | inferred | unknown
```

A raw `htop`, database shell, test runner, or unknown CLI has `AgentState=unavailable`, not `idle`. An active CLI agent with no adapter has `AgentState=unknown`, while the terminal may still be confidently `interactive` or `output-active`.

### Event envelope

Every observation should enter a single local event bus with provenance:

```json
{
  "eventId": "uuid",
  "paneId": "%17",
  "tmuxSessionId": "$3",
  "kind": "agent.permission_requested",
  "occurredAt": "2026-07-19T17:42:00Z",
  "source": "cli_hook",
  "adapter": "claude-code",
  "adapterVersion": "1.4",
  "confidence": "authoritative",
  "correlation": {
    "agentSessionId": "...",
    "turnId": "...",
    "taskId": null
  },
  "payload": {
    "tool": "Bash",
    "summary": "Permission requested"
  }
}
```

The reducer derives current state and attention items from events. It must retain source/confidence so the UI can tell the truth and debugging can explain why a badge appeared.

### Priority and aggregation

Recommended attention priority:

1. terminal failure or disconnected pane with a live process;
2. permission request or direct question;
3. Voss gate, budget halt, conflict, or sign-off;
4. agent error or verified stall;
5. completed and ready for review;
6. informational command completion.

Workspace and tab badges should show the highest-priority unseen attention item, plus a count. Continuous `working` activity belongs in subtle state decoration, not the notification count.

### State transitions need hysteresis

Avoid flicker and notification storms:

- Require a short stable interval before changing `working -> quiet` from activity alone.
- A hook-declared `waiting_permission` overrides activity heuristics until a matching reply or new turn.
- A completion event remains `review` until the pane is viewed or explicitly acknowledged.
- `stalled` requires a configured elapsed threshold and should say what stopped changing: output, process CPU, event heartbeat, or adapter heartbeat.
- Coalesce repeated permission/idle events by `(pane, turn, reason)` while preserving the latest payload.
- Reopening a pane marks an item seen, not resolved. Only an actual lifecycle event or explicit action resolves it.

## 4. Notification UX

### Minimum usable system

- Pane header: one stable status icon, accessible label, source/confidence tooltip, and no animation except active work.
- Tab/workspace: aggregate highest-priority state and unseen count.
- Attention inbox: durable, keyboard-navigable list sorted by severity then age, with one-keystroke jump to the source tmux pane.
- In-app toast: only for background panes, no more than two visible, coalesce bursts.
- Desktop notification: only when the app/window is not focused or the pane is not visible; clicking focuses the correct workspace, tab, and tmux pane.
- Optional sound: off by default or independently configurable by reason; never randomize sounds.
- Quiet hours and per-project muting.
- Notification audit: when, why, source, and which pane, so false positives can be diagnosed.

Warp’s mailbox, tab badges, and parent-only orchestration notification policy are the strongest documented reference for this design. [Warp agent notifications](https://docs.warp.dev/agent-platform/capabilities/agent-notifications/)

### Avoid approval fatigue

IDE agent products make permission state explicit because agents can modify files, run commands, and access external resources. VS Code separates session permission level from individual tool/URL approval and exposes auto-approval notifications. [VS Code approvals](https://code.visualstudio.com/docs/agents/approvals), [VS Code agent security](https://code.visualstudio.com/docs/agents/security)

For external CLIs, Voss must preserve the CLI’s own approval UI. A Voss attention item may deep-link to it, but must not display Allow/Deny actions unless the adapter has a structured, authenticated, supported response channel and the request ID is still current. This is already the intent of Voss’s adopted-agent comments and should become an enforced capability check.

### Multi-agent observability without dashboard compulsion

The daily-driver default should be a thin terminal layer:

- status in pane/tab chrome;
- shortcut to “next item needing attention”;
- optional inbox drawer;
- terminal-native quick switcher with status/reason previews;
- no permanent Kanban, swarm graph, or usage dashboard.

The optional orchestration console can add task dependencies, ownership, budgets, gates, evidence, and child-agent drill-down. Both surfaces should consume the same event model. This avoids implementing two incompatible concepts of “blocked” and keeps Voss optional.

## 5. Exact Implications for the Current Voss App

### Existing strengths

The current code already contains useful foundations:

- `attentionQueue.ts` normalizes Voss SSE events for permissions, budgets, confidence, gates, and idle sessions into deep-linkable items (`apps/voss-app/src/org/attention/attentionQueue.ts:30-72`, `156-249`).
- It explicitly suppresses permission actions for adopted external agents, an important honesty boundary (`attentionQueue.ts:118-121`, `169-181`).
- Attention items can resolve to pane/session targets.
- The Voss protocol supplies richer native signals that raw terminals cannot: budget, confidence, gate, sign-off, and unsupported claims.

### Current gaps

1. **The registry cannot represent meaningful live state.** Its database constraint permits only `active` or `stopped` (`crates/voss-app-core/src/agent_registry.rs:96-108`). This is process registration, not agent state.
2. **The sidebar presents activity without provenance.** `AgentItem` exposes booleans such as `isStreaming` and `isActive`, but not waiting, permission, completed, error, evidence source, confidence, or last transition (`apps/voss-app/src/components/sidebar/AgentItem.tsx:3-16`).
3. **The attention queue is Voss-centric.** Its live path consumes Voss SSE event shapes. The comments describe CLI hook normalization, but the product needs a general local event ingestion boundary for CLI hooks, tmux/process events, shell markers, bells, and renderer health.
4. **Idle is mislabeled.** The current copy turns `session.idle` into “awaiting input” (`attentionQueue.ts:236-245`). Idle can also mean completed, paused, rate-limited, detached, or simply no active turn. The reason should come from the source event.
5. **The top-chrome notifications button is a stub** (`apps/voss-app/src/components/titlebar/TopChrome.tsx:228-233`). The existing attention panel can be the first inbox rather than creating another parallel system.
6. **OSC parsing is not a reusable incremental parser.** The current PTY reader extracts one complete Voss-specific OSC 1337 sequence from a single read chunk and otherwise passes bytes through (`crates/voss-app-core/src/pty/reader.rs:14-30`, `53-99`). A real shell/notification integration needs streaming parsing across fragmented reads, multiple sequences per chunk, BEL/ST terminators, length limits, and transparent passthrough of unknown sequences.
7. **Terminal health is absent from attention.** The BridgeSpace regressions show why Voss needs reader/renderer/tmux-attachment liveness distinct from process and agent state.

### Required architectural boundary

Create a local **Terminal Event Broker** owned by the terminal engine, not by the Voss sidecar:

- Input sources: tmux control notifications, PTY bytes, shell integration, process inspection, app focus, renderer acknowledgements, optional CLI adapters, and optional Voss SSE.
- Output: source-qualified observations and derived attention items.
- Persistence: app-local database, not the repository’s `.voss` directory.
- Voss sidecar: an optional producer/consumer on the bus, started only through explicit orchestration actions.
- External CLI config changes: never automatic without a preview and confirmation; preserve existing hook arrays/plugins; support uninstall and health checks.

This lets ordinary terminal status work before Voss is initialized and prevents Voss-specific OSC variables or project files from becoming prerequisites.

## 6. Adapter Strategy

### Capability manifest

Each agent adapter should declare capabilities discovered at runtime:

```text
binaryDetection
sessionCorrelation
turnStarted
turnCompleted
permissionRequested
questionRequested
errorReported
backgroundTaskReported
resume
structuredReply
hookInstall
hookHealth
```

The UI should derive available actions from this manifest. It should not infer support from the binary name alone.

### Modes

- **Raw:** launch exactly the user’s command; no config mutation; terminal/process signals only.
- **Observe:** user explicitly enables a documented hook/plugin or structured client connection; status enriches without changing the agent’s model, auth, permissions, or command grammar.
- **Control:** only when a supported protocol can acknowledge actions; allows structured resume/reply/cancel.
- **Voss:** optional adoption adds tasks, policies, budgets, gates, and coordination.

Every pane can display its current mode and downgrade reason. Unknown agents remain fully usable.

### Hook safety

Gemini’s own best-practices document warns that hooks inherit environment variables and can exfiltrate prompts, output, or secrets. [Gemini hook best practices](https://geminicli.com/docs/hooks/best-practices/) Therefore:

- listener binds only to loopback or a permission-restricted Unix socket;
- each pane gets an unguessable session token;
- hook payload size and event rate are bounded;
- the hook runner has a short timeout and non-blocking failure behavior;
- config mutation is transactional and preserves user hooks;
- the user can inspect the exact installed script and events;
- no terminal output is uploaded for classification by default.

## 7. Anti-Patterns

1. **Do not call silence “idle” or “done.”** It is only absence of observed output.
2. **Do not parse approval prompts and then auto-approve them.** Printed text is not an authenticated request.
3. **Do not rely on `tmux send-keys` success as delivery acknowledgement.** Verify state through an explicit event or keep the action pending.
4. **Do not install hooks by silently rewriting global agent config.** Require consent, preserve other integrations, and provide removal.
5. **Do not make an LLM classify every terminal pane by default.** This adds privacy, network, cost, latency, and false-positive risk to the terminal core.
6. **Do not notify on continuous work.** Notify on attention transitions; render working state quietly.
7. **Do not clear a permission request because the pane was focused.** Mark it seen; resolve it only from a response event.
8. **Do not conflate agent completion with task acceptance or Voss sign-off.** Completion should lead to review, not automatic done.
9. **Do not allow arbitrary OSC output to invoke privileged Voss actions.** Terminal notifications are untrusted display metadata.
10. **Do not make the orchestration console the only place to see state.** Terminal pane/tab chrome and a jump command must remain sufficient for the daily loop.
11. **Do not hide terminal-engine failure behind an agent spinner.** Surface stale rendering, lost tmux attachment, and dead readers separately.
12. **Do not promise identical state support across Claude, Codex, Gemini, OpenCode, or unknown CLIs.** Publish a runtime capability matrix.

## 8. Phased Priorities

### P0: Make state honest

1. Define the orthogonal state/event schema with evidence source and confidence.
2. Replace the registry’s binary `active/stopped` meaning with process registration plus a separate derived-state store.
3. Stop translating generic idle into “awaiting input.”
4. Wire the existing notification button to a durable attention inbox.
5. Add “next attention item” and direct pane focus.
6. Add process/PTY/tmux/renderer health signals.

**Exit criterion:** any pane can explain its displayed state and evidence source; unknown commands never receive fake agent semantics.

### P1: Terminal-native signals

1. Implement an incremental, bounded OSC parser with transparent unknown-sequence passthrough.
2. Support opt-in OSC 133 and OSC 7 shell integration for prompt, command, exit, and CWD boundaries.
3. Support BEL and OSC 9/777; consider OSC 99 later after capability negotiation.
4. Add focus-aware in-app and desktop notifications with quiet settings and coalescing.
5. Persist attention/read state locally.

**Exit criterion:** long commands and shell sessions produce reliable, focus-aware attention without any agent integration or Voss project files.

### P2: Opt-in agent observers

1. Build adapters for Claude Code, Codex, Gemini CLI, and OpenCode using their supported lifecycle channels.
2. Add preview/install/uninstall/health flows for hooks and plugins.
3. Correlate agent session/turn IDs to tmux pane IDs using per-pane tokens.
4. Support waiting-permission, waiting-question, completed, failed, and background-task-aware working where the provider exposes them.
5. Expose a capability matrix in the pane inspector and settings.

**Exit criterion:** disabling or removing every adapter leaves the original CLI and terminal fully functional; supported adapters pass lifecycle contract tests across pinned CLI versions.

### P3: Optional Voss convergence

1. Feed Voss budget, confidence, gate, task, sign-off, and child-run events through the same broker.
2. Keep terminal attention visible in normal pane/tab chrome.
3. Add orchestration-only filters and parent/child drill-down in the console.
4. Notify on parent-level actionable transitions by default; keep child churn in the console unless directly blocked on the user.
5. Add explicit acknowledgement and resolution semantics to the Voss protocol.

**Exit criterion:** a user can run only raw terminals, raw terminals plus observed agents, or a full Voss orchestration without changing the underlying attention concepts.

### P4: Optional heuristics and remote operation

1. Add local-only pattern packs for unsupported tools, clearly labeled inferred.
2. Evaluate an opt-in local or remote LLM classifier only after measuring precision/recall on real pane traces.
3. Add stall detection based on multiple independent signals, not silence alone.
4. Preserve source pane attribution over SSH/tmux and test notification focus routing across windows.

**Exit criterion:** heuristics have an evaluation corpus, published false-positive/false-negative rates, privacy controls, and cannot drive permission or merge actions.

## 9. Contradictions and Evidence Quality

### Contradictions

- **Hooks are precise vs. hooks are universal.** Hooks are the best evidence source when available, but provider coverage and payloads differ by version. Codemux documents no terminal status for several agents, while workmux and newer tmux tools claim support for more agents through newly added hooks. These claims are time-sensitive, not necessarily inconsistent.
- **Inferred state is useful vs. inferred state is reliable.** dmux product docs describe LLM classification as the mechanism for waiting/idle detection. Paneflow explicitly says unsupported agents only expose what can be inferred. Neither provides an externally validated accuracy rate. Treat this as UX assistance, not authority.
- **Session visible vs. process alive.** Paneflow documents layout/session reconstruction but not child-process survival after app exit. tmux-backed tools can preserve processes independently. “Session restore” must therefore specify whether it restores UI state, terminal scrollback, or live processes.
- **BridgeSpace “GPU-accelerated terminals” vs. operational reliability.** The product page presents mature multi-agent terminals, while its own changelog records a multi-release rendering regression and rollback. The changelog is stronger evidence for engineering risk than the marketing page is for reliability.
- **Agent completion vs. work completion.** Provider hooks often report end-of-turn. `tmux-agent-status` documents special handling for background tasks, proving end-of-turn alone can be premature.

### Source quality

- **High:** official protocol/shell documentation from Warp, VS Code, Windows Terminal, kitty, Contour, Gemini CLI, OpenCode; source repositories and issue trackers.
- **Medium-high:** open-source project documentation for workmux, tmux-agent-status, Paneflow, and dmux, because behavior is inspectable but claims were not independently benchmarked here.
- **Medium:** BridgeSpace product and changelog. They are first-party, but the changelog contains concrete regression detail and version history.
- **Low to medium:** Reddit discussions. They are anecdotal and sometimes promotional, but useful as failure-mode discovery; no core recommendation depends on a single community post.

## 10. Research Gaps

- No product surveyed publishes a rigorous precision/recall benchmark for terminal-output or LLM-based waiting/stall detection.
- BridgeSpace does not publicly explain its lifecycle-event or raw CLI detection architecture in enough detail to compare reliability.
- Flowmux’s public site states the desired UX but provides limited technical documentation of event sources.
- OSC notification support remains fragmented; OSC 9, 777, and 99 are not one interoperable standard.
- CLI hook APIs are changing quickly. A shipping Voss adapter must verify current provider versions and fixtures in CI rather than relying on documentation captured on this date.
- Native desktop notification focus/deep-link behavior varies across macOS, Windows, Linux desktop environments, SSH, and nested tmux; this needs packaged-app testing.
- No independent usability study was found comparing always-visible multi-agent dashboards against quiet, attention-driven terminal navigation.

## 11. Sources Consulted

### Product and ADE documentation

1. [Warp agent notifications](https://docs.warp.dev/agent-platform/capabilities/agent-notifications/) - notification taxonomy, mailbox, status indicators, orchestration behavior.
2. [Warp desktop notifications](https://docs.warp.dev/terminal/more-features/notifications) - long-command/password notifications and OSC 9/777.
3. [Warp overview](https://docs.warp.dev/) - terminal/agent separation, third-party CLIs, optional AI, Oz observability.
4. [Warp full terminal use](https://docs.warp.dev/agent-platform/capabilities/full-terminal-use) - shared PTY control and terminal buffer visibility.
5. [Codemux agent status](https://docs.codemux.org/agent-status) - hook-based state, aggregation, attention priority, view-aware clearing.
6. [workmux repository](https://github.com/raine/workmux) - hook/status-file integrations, tmux status, dashboard, support limitations.
7. [workmux changelog](https://github.com/raine/workmux/blob/main/CHANGELOG.md) - dashboard/sidebar evolution and state edge-case fixes.
8. [tmux-agent-status repository](https://github.com/samleeney/tmux-agent-status) - hook-driven status and background-task handling.
9. [dmux documentation](https://dmux.ai/) - output activity plus LLM classification and focus-aware notifications.
10. [dmux repository](https://github.com/standardagents/dmux) - inspectable implementation/project evidence.
11. [Paneflow features](https://paneflow.dev/docs/features) - progressive enhancement, state sources, local IPC and read-only MCP.
12. [Paneflow getting started](https://paneflow.dev/docs) - raw CLI compatibility and no provider proxying.
13. [Paneflow product](https://paneflow.dev/) - visible state, context, and multi-agent positioning.
14. [Flowmux](https://www.flowmux.dev/) - quiet tmux-native overview around real CLIs.
15. [BridgeSpace product](https://www.bridgemind.ai/products/bridgespace) - multi-agent terminal and orchestration surface claims.
16. [BridgeSpace changelog](https://www.bridgemind.ai/changelog) - recovery notifications and detailed multi-pane rendering regressions/rollback.

### Terminal and shell protocols

17. [Contour OSC 133](https://contour-terminal.org/vt-extensions/osc-133-shell-integration/) - prompt/command semantic marker specification.
18. [VS Code terminal shell integration](https://code.visualstudio.com/docs/terminal/shell-integration) - OSC 633/133, command detection, nonce-based spoofing protection.
19. [Windows Terminal shell integration](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration) - cross-platform OSC 133 behavior and exit status.
20. [kitty shell integration](https://sw.kovidgoyal.net/kitty/shell-integration/) - OSC 133 implementation guidance.
21. [WezTerm shell integration](https://wezterm.org/shell-integration.html) - opt-in shell integration and OSC 7/133 support.
22. [kitty desktop notifications](https://sw.kovidgoyal.net/kitty/desktop-notifications/) - OSC 99, focus, identity, limits, negotiation, and legacy OSC 9.
23. [zsh semantic-marker proposal](https://www.zsh.org/mla/workers/2025/msg00106.html) - ecosystem adoption and plugin burden.

### Agent lifecycle and safety

24. [Gemini CLI hooks reference](https://geminicli.com/docs/hooks/reference/) - structured lifecycle and notification event schemas.
25. [Gemini hook best practices](https://geminicli.com/docs/hooks/best-practices/) - hook exfiltration and environment risks.
26. [OpenCode plugins](https://opencode.ai/docs/plugins/) - permission/session event surface.
27. [OpenCode permissions](https://opencode.ai/docs/permissions/) - ask/allow/deny semantics.
28. [Anthropic hooks overview](https://claude.com/blog/how-to-configure-hooks) - deterministic lifecycle customization.
29. [Codex CLI README](https://github.com/openai/codex/blob/main/codex-rs/README.md) - completion notification support.
30. [Codex event hooks issue](https://github.com/openai/codex/issues/2109) - subagent metadata/noise limitation.
31. [Codex hook-trust issue](https://github.com/openai/codex/issues/24093) - orchestration startup regression involving hook trust.
32. [VS Code approvals](https://code.visualstudio.com/docs/agents/approvals) - approval and permission separation.
33. [VS Code agent security](https://code.visualstudio.com/docs/agents/security) - review and auto-approval notification behavior.

### Community and failure evidence

34. [tmux dispatch failure report](https://www.reddit.com/r/LocalLLaMA/comments/1shgpj8/tmuxbased_agent_coordination_a_silent_dispatch/) - anecdotal `send-keys` acknowledgement failure.
35. [multi-agent TUI discussion](https://www.reddit.com/r/ClaudeCode/comments/1s3mjzs/i_built_a_tui_that_replaces_tmux_for_running/) - anecdotal silent message drops and at-a-glance state need.
36. [tmux orchestrator discussion](https://www.reddit.com/r/tmux/comments/1s6oze9/built_an_agent_orchestrator_within_tmux/) - user preference for status plus direct terminal navigation over feature-heavy viewers.

## Bottom Line for the Main Report

Voss should not attempt to “detect agent state” as one generic PTY feature. It should build a tmux-backed terminal event system that knows exactly what it observed, grades each observation by provenance, and promotes only actionable transitions into a focus-aware attention inbox. Existing CLI agents remain raw and fully functional; adapters are opt-in progressive enhancement; Voss orchestration is a richer optional producer of the same events. The competitive advantage is not having more colored status labels. It is being the terminal ADE that is explicit about what it knows, what it inferred, and what it is actually allowed to control.
