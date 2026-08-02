# Agent-Neutral CLI Compatibility and Open Interoperability

> Research date: 2026-07-19  
> Scope: terminal-first ADE interoperability from unknown CLI processes through Voss-native cells  
> Sources consulted: 33 unique pages, including the current Codex manual  
> Research method: five varied discovery searches, recursive protocol/adapter searches, and official, GitHub, news, and community passes

## Key Findings

- **The non-negotiable baseline is byte-transparent PTY execution.** A PTY is a bidirectional terminal channel: bytes written to the master appear to the child as terminal input, including control characters such as `Ctrl-C`, and bytes written by the child are read from the master. That is the compatibility contract that lets an unknown CLI, full-screen TUI, debugger, editor, SSH session, or agent run unchanged. Voss must preserve native terminal sizing, signals, alternate-screen behavior, raw mode, and exit state before attempting any agent semantics ([Linux `pty(7)`](https://man7.org/linux/man-pages/man7/pty.7.html), [`portable-pty`](https://docs.rs/portable-pty/latest/portable_pty/)).
- **tmux should be the durable session/process authority; the app should be a client.** tmux control mode already provides a parseable control channel, asynchronous session/window/pane notifications, pane IDs, exact pane output, flow control, and recovery through `capture-pane`. This is a better foundation for a tmux-powered ADE than reimplementing multiplexing state inside the desktop shell ([tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)).
- **Terminal bytes and agent events are different planes.** ANSI/VT output is presentation, not a stable agent API. It may be non-UTF-8, contain escape sequences, be redrawn in place, or represent an alternate screen. Voss can render it and use low-confidence heuristics, but must not infer permissions, tool completion, or durable audit facts from screen scraping. Zed reached the same boundary: it could already run Gemini CLI in a terminal, but needed JSON-RPC rather than ANSI escape codes for rich integration ([Zed announcement](https://zed.dev/blog/bring-your-own-agent-to-zed), [tmux pane output semantics](https://github.com/tmux/tmux/wiki/Control-Mode#pane-output)).
- **Existing agent auth, configuration, billing, and TUI must remain agent-owned.** Zed now exposes three explicit paths: native Zed agent, ACP external agent using its own auth/config, and terminal thread using the CLI's native TUI/auth/config. Voss should adopt the same separation rather than disguising one path as another ([Zed agent paths](https://zed.dev/docs/ai/agents), [Zed external-agent boundaries](https://zed.dev/docs/ai/external-agents)).
- **Hooks are the best progressive enhancement for an interactive TUI, but they are adapters, not a universal protocol.** Claude Code, Codex CLI, Gemini CLI, and OpenCode expose materially different hook/plugin surfaces. Hooks can report session/turn/tool/permission/stop state without replacing the TUI, but installation changes agent-owned config and may trigger trust prompts. They therefore require explicit, reversible setup with source attribution and must never be silently installed ([Claude Code hooks](https://code.claude.com/docs/en/hooks), [Codex hooks](https://learn.chatgpt.com/docs/hooks), [Gemini hooks](https://geminicli.com/docs/hooks/reference/), [OpenCode plugins](https://opencode.ai/docs/plugins/)).
- **Structured headless modes are excellent for Voss-dispatched jobs, but must not replace native interactive sessions.** Claude Code `-p --output-format stream-json`, Codex `exec --json`, and Gemini headless JSON modes expose rich machine-readable streams. Those are distinct invocation modes, not safe side channels into an already running TUI. Voss should present them as an optional "integrated run" or orchestration backend while leaving the normal CLI command untouched ([Claude Code headless](https://code.claude.com/docs/en/headless), [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/), [Gemini automation](https://geminicli.com/docs/cli/tutorials/automation/)).
- **ACP is the strongest open path to a rich agent client, not a replacement for terminal support.** ACP uses JSON-RPC over stdio for local agents, supports multiple sessions per connection, streams UI updates, supports bidirectional permission requests, can forward MCP server configuration, and has adapters for Codex and Claude plus native/available support across a broad registry. Its current design assumes an editor-like client and says remote support is still in progress, so Voss should add ACP as an optional session type after the terminal core is reliable ([ACP introduction](https://agentclientprotocol.com/get-started/introduction), [architecture](https://agentclientprotocol.com/get-started/architecture), [agent list](https://agentclientprotocol.com/get-started/agents), [registry](https://agentclientprotocol.com/get-started/registry)).
- **MCP solves agent-to-capability access, not terminal lifecycle or agent UI interoperability.** MCP standardizes tools, resources, prompts, lifecycle negotiation, and context exchange between an AI host and servers; it explicitly does not dictate how the host manages its LLM or context. Voss can expose capabilities, project memory, review, or orchestration requests as an optional MCP server, but MCP cannot tell Voss that an arbitrary TUI is waiting for permission or render its turn stream ([MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture)).
- **Warp validates the progressive-enhancement product, and also exposes its failure modes.** Warp runs existing CLIs and adds rich input, metadata, review, remote control, and notifications; notifications require per-agent plugins/config changes and support varies by agent. Community reports show the cost of overreach: wrapper commands can miss detection, SSH/tmux can break environment-based plugins, terminal users object when agent mode replaces normal terminal behavior, and at least one user reported the terminal fighting TUI I/O ([Warp CLI agents](https://docs.warp.dev/agent-platform/cli-agents/overview/), [custom-wrapper issue](https://github.com/warpdotdev/warp/issues/8579), [Warp community AMA](https://www.reddit.com/r/warpdotdev/comments/1slf86f/we_just_launched_universal_agent_support_in_warp/)).
- **The practical product boundary is: observe by default, integrate by consent, orchestrate by promotion.** Unknown CLIs get complete terminal functionality. Recognized agents get cosmetic metadata only. Hooks/plugins, structured mode, ACP, Voss MCP, and Voss-native cells are separately opt-in capabilities with explicit ownership and downgrade paths.

## Detailed Notes

### 1. Architecture: two planes, one durable session authority

#### Terminal data plane

The data plane should carry terminal bytes without agent-specific interpretation:

- tmux server owns sessions, windows, panes, process lifetime, detach/reattach, scrollback source, and remote persistence.
- A Voss terminal client attaches through tmux control mode and renders each pane through the terminal renderer.
- Input is forwarded as terminal input, including raw control bytes; resize updates the real terminal size; focus, bracketed paste, mouse modes, Unicode, OSC, and alternate screen are preserved.
- A pane can host any shell or executable. Voss credentials, Voss initialization, or an agent registry entry are not prerequisites.
- Pane output may be recorded as terminal replay data only under an explicit retention policy. It is not automatically promoted into model context or an audit log.

tmux control mode sends parseable commands and asynchronous `%` notifications while preserving application pane output. It also has explicit flow control and a documented recovery path when a client falls behind ([tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)). A PTY remains the final compatibility boundary below tmux: the child believes it is connected to a terminal and receives normal signal semantics ([Linux `pty(7)`](https://man7.org/linux/man-pages/man7/pty.7.html)).

#### Metadata/control plane

The metadata plane should be additive and source-aware:

```text
AgentEvent {
  schema_version,
  event_id,
  timestamp,
  tmux_target, pane_id, process_id,
  cwd, repo_root, worktree, branch,
  agent_id, agent_version,
  native_session_id, native_turn_id, native_parent_id,
  type,                 // started | busy | waiting | permission | tool_* |
                        // file_changed | completed | error | stopped
  payload,
  source,               // process | terminal | osc | hook | jsonl | sse | acp | voss
  confidence,           // observed | declared | inferred
  adapter_version,
  raw_event_ref
}
```

Rules for this envelope:

1. Never collapse `inferred` screen/process state into an `observed` hook/protocol fact.
2. Preserve native IDs and raw-event references for debugging; do not pretend all agents share the same session model.
3. Version the Voss envelope independently from each adapter.
4. Unknown event fields are retained or ignored, not fatal.
5. Adapter failure degrades to a normal terminal pane. It never terminates or corrupts the agent session.

### 2. Practical capability ladder

| Level | Session class | Voss capability | User/agent ownership boundary |
|---|---|---|---|
| **L0** | Unknown PTY process | Full terminal, tmux persistence, splits, detach/reattach, scrollback, search, copy/paste, process exit | Voss knows nothing about the process beyond terminal/process facts |
| **L1** | Recognized command | Agent icon/name, command, version, cwd/repo/worktree, launch/resume template, generic busy CPU/exit indicators | Recognition is cosmetic; no config mutation, prompt interception, or auth handling |
| **L2** | Cooperative terminal session | OSC/bell/window-title/cwd signals, user-set status, `voss-agent-event` helper/status file, desktop notifications with confidence labels | Agent/wrapper explicitly emits hints; PTY remains canonical UI |
| **L3** | Hook/plugin enhanced TUI | Precise start/busy/wait/permission/tool/stop events, notification routing, session linking, limited cost/tool metadata when supplied | User explicitly installs an adapter; native TUI, auth, permission UI, and config stay authoritative |
| **L4** | Native structured run | JSONL/SSE stream, typed messages/tools/diffs/usage, resumable native session IDs, Voss orchestration dispatch | Separate native headless/server invocation; do not claim it is the same UX as the interactive TUI |
| **L5** | ACP external agent | Rich Voss agent panel, bidirectional permission requests, diff/tool rendering, multiple sessions, optional MCP forwarding | ACP process owns runtime/auth/model/tools/config; Voss owns client UI and tmux placement |
| **L6** | Voss-enhanced external agent | Opt-in Voss MCP tools/resources, project memory, role/board association, review requests, audit linkage, budgets as advisory or dispatch policy | External agent remains its own harness; Voss capabilities are sidecar services, not hidden replacements |
| **L7** | Voss-native cell | Full Voss harness event bus, hard budgets/scope/permissions, roles, session tree, board/reviewer/EM semantics, replay and audit | User has explicitly promoted the pane/run into Voss ownership |

The key UX rule is monotonic enhancement: moving up a level unlocks capabilities; moving down never makes the CLI unusable. Every pane displays its current integration level and which component owns auth, permissions, and execution.

### 3. Agent adapter observations

#### Claude Code

Claude Code has the richest documented hook surface in this set. Its hooks accept JSON on stdin for command handlers and cover session, turn, tool, permission, subagent, task, compaction, worktree, config, cwd, file, notification, and shutdown events. `PreToolUse` can block a tool, while a silent successful hook does not approve it; normal native permission flow continues ([hook lifecycle and decision flow](https://code.claude.com/docs/en/hooks)). Its structured print mode emits JSON or newline-delimited `stream-json`, including session metadata, cost, tool events, and parent tool IDs for subagent messages ([headless mode](https://code.claude.com/docs/en/headless)).

Voss implications:

- Prefer a user-approved Claude plugin package for lifecycle integration over ad hoc edits to `~/.claude/settings.json`.
- Do not replace or merge `CLAUDE.md`, `.claude/settings*.json`, permissions, skills, MCP, or login state.
- A hook adapter should only publish events to a local Voss socket/CLI and return no decision unless the user separately enables Voss enforcement.
- Preserve Claude's background-task semantics; `Stop` alone may not mean the pane is idle. The tmux-agent-status project specifically accounts for background tasks to avoid premature completion ([tmux-agent-status](https://github.com/samleeney/tmux-agent-status)).

#### Codex CLI

Codex supports native hooks from user/project config layers and a machine-readable non-interactive stream. The current docs list session, prompt, tool, permission, compaction, subagent, and stop events; every command hook receives JSON on stdin, and tool coverage includes shell, `apply_patch`, MCP, and other local function tools, with stated exceptions ([Codex hooks](https://learn.chatgpt.com/docs/hooks)). `codex exec --json` emits JSONL events such as `thread.started`, `turn.*`, `item.*`, and `error`, including command execution, file changes, MCP calls, web searches, plans, and usage; it reuses saved CLI authentication by default ([Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/)).

Voss implications:

- Hooks are an explicit setup step because non-managed hooks require user review/trust in `/hooks`.
- Use a stable installed adapter path. A changed command/path changes the hook identity and can require trust again; an open Codex issue documents this wrapper-installation friction ([Codex #21615](https://github.com/openai/codex/issues/21615)).
- Do not parse `~/.codex/log/codex-tui.log` or transcript JSON as a contract. The official hooks docs warn that transcript format is not stable, and a feature request documents why log parsing is only a workaround ([Codex #21990](https://github.com/openai/codex/issues/21990)).
- Treat hooks as a useful guardrail, not the hard security boundary; the docs state that specialized tool paths may opt out.

#### Gemini CLI

Gemini hooks use JSON stdin/stdout with explicit exit-code behavior, common session/cwd/transcript/timestamp fields, matchers, tool/agent/model/lifecycle events, allow/deny decisions, and notification events ([Gemini hook reference](https://geminicli.com/docs/hooks/reference/)). Headless mode supports prompt input and JSON output for automation ([Gemini automation](https://geminicli.com/docs/cli/tutorials/automation/)). Gemini was also the initial ACP reference integration, demonstrating that the same agent can support both a native terminal TUI and a rich protocol client ([Zed announcement](https://zed.dev/blog/bring-your-own-agent-to-zed)).

Voss implications:

- Offer both "Gemini CLI terminal" and "Gemini ACP session" explicitly.
- Never enable prompt/tool mutation hooks as part of basic status integration.
- Hook stdout must remain strictly JSON; adapter logging goes to stderr or the Voss local event socket.

#### OpenCode

OpenCode exposes an extensive plugin event set including permission, session, message, diff, tool, file, todo, command, and TUI events ([OpenCode plugins](https://opencode.ai/docs/plugins/)). Its TUI is already a client of a local server; the server publishes OpenAPI 3.1, SSE event streams, and TUI-control endpoints ([OpenCode server](https://opencode.ai/docs/server/)).

Voss implications:

- The least invasive interactive integration is a small user-installed plugin that emits normalized Voss events.
- A deeper adapter can connect to the documented server/SSE API, but Voss must not take over provider credentials through `/auth/:id`; OpenCode remains credential owner.
- A server-connected Voss UI and a raw OpenCode terminal pane should be separate presentation choices over the same agent-owned runtime where supported.

#### Unknown and custom agents

The fallback must remain useful without vendor support. Existing tmux projects demonstrate two viable opt-in escape hatches: a simple status-file contract and collector extensions ([tmux-agent-status custom integration](https://github.com/samleeney/tmux-agent-status), [workmux agent tracking](https://github.com/raine/workmux)). Voss should ship a tiny, documented helper:

```bash
voss-agent-event --state waiting --session "$ID" --reason permission
```

Wrappers can invoke this or emit a documented OSC sequence without Voss knowing the agent. This is a hint channel, not permission authority.

### 4. Detection and adapter registry

Do not hard-code only executable basenames. Warp's open issue shows that wrapper commands around a supported CLI lose enhancement when detection keys on the entrypoint name ([Warp #8579](https://github.com/warpdotdev/warp/issues/8579)). Use a declarative registry with:

- exact executable paths and basename matchers;
- user-defined wrapper aliases and command regexes;
- optional child-process fingerprinting;
- opt-in self-identification through an OSC sequence or `VOSS_AGENT_ADAPTER` environment value;
- version probes that never block pane startup;
- launch, resume, and attach templates;
- declared integration methods: `pty`, `hook`, `plugin`, `jsonl`, `server-sse`, `acp`, `voss-native`;
- adapter-owned files and a reversible uninstall manifest;
- required trust/permission steps and a capability matrix.

Recognition never grants integration rights. A detected `claude` command may display a badge at L1, but Voss cannot install a plugin, read its transcript, or intercept permissions until the user chooses that enhancement.

### 5. ACP and MCP in the Voss architecture

#### ACP client

ACP belongs beside terminal panes as an optional rich session host:

- Spawn the agent's registered ACP command as a subprocess.
- Keep the agent's own environment, auth store, config search paths, and model selection.
- Negotiate capabilities and render only features the agent actually declares.
- Map ACP sessions into tmux/Voss workspaces for organization, but do not pretend ACP stdio is a terminal PTY.
- Forward Voss-configured MCP servers only with a clear per-session consent/visibility surface.
- Store ACP logs for diagnostics under an explicit retention setting.

ACP supports concurrent sessions over one connection and bidirectional permission requests, but its stated trust model assumes an editor talking to a trusted model, and remote-agent support remains work in progress ([ACP architecture](https://agentclientprotocol.com/get-started/architecture), [ACP introduction](https://agentclientprotocol.com/get-started/introduction)). Voss should therefore treat ACP as a rich local adapter, not its universal security or remote orchestration substrate.

#### Voss MCP sidecar

Expose selected Voss capabilities as an MCP server so external agents can opt into Voss without becoming Voss agents:

- read project principles/memory;
- query session/board/task state;
- request a review or verification run;
- publish a handoff or result;
- inspect budgets and policies;
- call explicitly safe Voss tools.

Mutating operations still pass through Voss policy and produce audit records. Installing or forwarding the Voss MCP server is explicit per agent/project. MCP is additive because its host remains the existing agent; its architecture defines tools/resources/prompts and context exchange but does not control the agent loop ([MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture)).

### 6. Configuration, auth, and security rules

1. **Never proxy agent authentication by default.** Launch the user's installed binary with its normal home/config environment. Do not import OAuth tokens, API keys, subscription cookies, or provider accounts into Voss.
2. **Never overwrite agent config.** Parse structured JSON/TOML with the format's parser, merge only the adapter-owned entry, preserve formatting where practical, back up before mutation, and record exactly what Voss owns.
3. **Require a visible install transaction.** Show files changed, command/plugin installed, events subscribed, data emitted, and uninstall action. Native trust prompts remain native.
4. **Separate observation from enforcement.** Status/notification hooks return no allow/deny decision. A user must enable a distinct Voss policy adapter before Voss participates in tool blocking.
5. **Do not auto-approve native permission prompts.** Voss may notify or focus the pane. Automatic answers require a promoted Voss-owned mode with explicit policy.
6. **Keep secrets out of the event bus.** Normalize and redact payloads at the adapter boundary. Store raw hook events only in an opt-in diagnostic log with rotation.
7. **Fail open for usability, fail closed for claimed enforcement.** If a status adapter crashes, continue as a terminal. If an explicitly enabled Voss policy adapter cannot run, state that enforcement is unavailable and do not claim the run is governed.
8. **Remote sessions install adapters remotely.** SSH/tmux changes environment and filesystem ownership. Warp community reports show local-terminal assumptions and `TERM_PROGRAM` checks can fail through remote/tmux layers ([Warp AMA](https://www.reddit.com/r/warpdotdev/comments/1slf86f/we_just_launched_universal_agent_support_in_warp/)).

### 7. Product recommendations for Voss ADE

#### Ship first

1. Make tmux the canonical session engine with control-mode integration and exact PTY behavior.
2. Add a generic session switcher/dashboard based only on tmux/process/git facts.
3. Add command registry, wrapper aliases, launch/resume templates, and explicit integration-level badges.
4. Define and version the normalized `AgentEvent` envelope plus local Unix-domain socket/named-pipe event ingress.
5. Ship the no-dependency `voss-agent-event` helper and manual status controls.

#### Then add opt-in adapters

1. Claude Code plugin/hooks for status, permission-needed, tool activity, and stop.
2. Codex trusted hooks plus `codex exec --json` as a separate orchestration runner.
3. Gemini hooks plus Gemini ACP as separate choices.
4. OpenCode plugin/SSE connection.
5. ACP client and registry support behind a feature flag until capability/version handling and local trust UX are proven.
6. Voss MCP sidecar for external agents.

#### Keep optional

- Orchestration console, board, reviewer, budgets, and replay panels.
- Pane promotion to a Voss-native cell.
- Voss policy participation in another agent's tool lifecycle.
- Rich agent transcript retention.
- Cloud/remote ACP until the protocol's remote story stabilizes.

#### Explicitly avoid

- Requiring `voss` login or `.voss/` creation to open a terminal.
- Replacing `claude`, `codex`, `gemini`, or `opencode` with Voss wrappers by default.
- Re-rendering an interactive agent TUI from scraped ANSI into proprietary message cards.
- Treating process name, CPU use, terminal silence, or prompt-shaped text as authoritative working/waiting/completed state.
- Silently editing dotfiles, installing hooks/plugins, forwarding MCP servers, or changing permission modes.
- A universal "approve" button that bypasses the agent's native permission and trust model.

## Notable Quotes & Data Points

- ACP local agents run as editor subprocesses using JSON-RPC over stdio; remote support is explicitly described as work in progress ([ACP introduction](https://agentclientprotocol.com/get-started/introduction)).
- Zed's core distinction is concise: external agents use an "ACP agent process and its own auth/config," while terminal threads use "Native CLI/TUI auth/config" ([Zed agents](https://zed.dev/docs/ai/agents)).
- tmux control mode pane output is otherwise "exactly what the application running in the pane sent to tmux," including possibly invalid UTF-8 and terminal escape sequences ([tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)).
- Codex JSONL includes thread/turn lifecycle, item events, errors, command executions, file changes, MCP calls, web searches, plans, and usage ([Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/)).
- Claude Code `stream-json` includes final result, cost, session metadata, retry events, and subagent-parent identifiers ([Claude Code headless](https://code.claude.com/docs/en/headless)).
- Warp lists 14 recognized third-party agents, but agent notifications are currently limited to Claude Code, Codex, and OpenCode and require one-time plugin/config setup ([Warp CLI agent matrix](https://docs.warp.dev/agent-platform/cli-agents/overview/)).
- ACP's current public agent list includes Claude via an adapter, Codex via an adapter, Gemini CLI, OpenCode, Copilot, Cursor, Goose, and many others; the registry distributes machine-readable metadata for installable agents ([ACP agents](https://agentclientprotocol.com/get-started/agents), [registry](https://agentclientprotocol.com/get-started/registry)).

## Source Credibility Notes

- **Highest confidence:** OS/manual documentation, tmux's official wiki, official ACP/MCP specifications, and official Claude Code, Codex, Gemini CLI, OpenCode, Zed, and Warp documentation. These support protocol shapes and documented product behavior.
- **High but implementation-specific:** official GitHub repositories and issue trackers. They are valuable for real integration gaps, but open issues describe reporter-observed behavior and proposals, not guaranteed roadmaps.
- **Medium:** `tmux-agent-status` and `workmux`. They are concrete open-source implementations proving hook/status-file patterns, but their "stable" labels describe project-local experience, not vendor guarantees.
- **Medium-low:** Android Central. It corroborates the Gemini/Zed ACP launch, but the primary Zed and ACP sources are stronger.
- **Community signal only:** Warp's Reddit AMA. It is useful for failure modes and user sentiment, not prevalence estimates. Comments may be outdated after plugin fixes.
- **Excluded from core recommendations:** CAP/CLI Agent Protocol search results. Its progressive PTY/structured-fast-path concept is directionally aligned, but it is young and lacks the adoption/authority of ACP, MCP, tmux, or vendor-native hooks.

## Gaps

- Warp does not publicly document its complete detection mechanism. Command-name detection and OSC/plugin behavior are visible in issues/source discussions, but should not be treated as a stable external API.
- No cross-agent standard currently defines interactive TUI lifecycle events. ACP defines client-agent RPC; MCP defines host-server capabilities; neither upgrades an arbitrary already-running PTY session.
- Vendor hook schemas and coverage evolve quickly. A production adapter suite needs version probes, fixtures, and compatibility tests against pinned CLI releases.
- Reliable "waiting for user" semantics remain uneven. Workmux documents no waiting state for several supported CLIs, and notification coverage in Warp varies by agent.
- It is unclear whether all ACP adapters preserve every native subscription/auth path and native configuration behavior across versions. Voss must capability-test rather than assume parity.
- ACP's remote-agent transport and security model are not complete enough to serve as Voss's general remote session substrate today.
- Windows ConPTY, nested tmux-over-SSH, and shell-integration edge cases need local soak tests; research establishes the architecture but not Voss-specific correctness.
- There is no independent measurement of how often terminal users choose raw TUI versus ACP/rich panels. Voss should instrument only explicit local product metrics or conduct user interviews, never infer demand from competitor feature lists.

## All Sources

### Terminal and tmux foundations

1. [Linux `pty(7)`](https://man7.org/linux/man-pages/man7/pty.7.html) - authoritative pseudoterminal master/slave, byte flow, signal, and terminal semantics.
2. [`portable-pty` Rust docs](https://docs.rs/portable-pty/latest/portable_pty/) - cross-platform Rust PTY interface, resize, spawn, read/write, and lifecycle traits.
3. [tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode) - official parseable client protocol, pane output, notifications, flow control, and capture recovery.

### Agent Client Protocol and Zed

4. [ACP introduction](https://agentclientprotocol.com/get-started/introduction) - scope, local stdio JSON-RPC, remote status, and editor-oriented assumptions.
5. [ACP architecture](https://agentclientprotocol.com/get-started/architecture) - subprocess setup, concurrent sessions, streaming notifications, permissions, and MCP forwarding.
6. [ACP agents](https://agentclientprotocol.com/get-started/agents) - current compatible/native/adapted agent ecosystem.
7. [ACP registry](https://agentclientprotocol.com/get-started/registry) - curated distribution metadata and install model.
8. [Zed: Bring Your Own Agent](https://zed.dev/blog/bring-your-own-agent-to-zed) - primary account of moving from terminal ANSI to structured ACP.
9. [Zed agent paths](https://zed.dev/docs/ai/agents) - native, ACP external, and terminal-thread product separation.
10. [Zed external agents](https://zed.dev/docs/ai/external-agents) - explicit auth/config/runtime ownership and custom-agent configuration boundaries.
11. [Zed agent panel](https://zed.dev/docs/ai/agent-panel) - rich thread UI, feature variability, worktrees, review, and external-agent limitations.
12. [JetBrains ACP overview](https://www.jetbrains.com/acp/) - JetBrains/Zed ecosystem positioning; page yielded little fetchable detail.
13. [Android Central: Gemini CLI joins Zed](https://www.androidcentral.com/apps-software/ai/gemini-cli-zed-code-editor-partnership) - secondary launch coverage and quoted subprocess/JSON-RPC design.

### Model Context Protocol

14. [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture) - official scope, participants, JSON-RPC layers, transports, tools/resources/prompts, and explicit non-goals.

### Agent-native integration surfaces

15. [Claude Code hooks](https://code.claude.com/docs/en/hooks) - comprehensive lifecycle, input/output, decision, plugin, and security reference.
16. [Claude Code headless mode](https://code.claude.com/docs/en/headless) - JSON, stream-json, schema output, session/cost, retry, and subagent stream metadata.
17. [Claude Code settings](https://code.claude.com/docs/en/settings) - configuration scopes, precedence, permissions, MCP, plugins, OAuth/config ownership.
18. [Codex hooks](https://learn.chatgpt.com/docs/hooks) - official current hook events, trust, tool coverage, schemas, and limitations.
19. [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/) - official JSONL events, structured output, auth reuse, resume, and sandbox guidance.
20. [Current Codex manual](https://developers.openai.com/codex/codex-manual.md) - official synthesized manual fetched 2026-07-19; used to locate current hooks/config/auth material.
21. [Gemini CLI hooks reference](https://geminicli.com/docs/hooks/reference/) - JSON schemas, exit codes, lifecycle/tool/model events, and decisions.
22. [Gemini CLI automation](https://geminicli.com/docs/cli/tutorials/automation/) - headless prompt and structured JSON usage.
23. [OpenCode plugins](https://opencode.ai/docs/plugins/) - plugin locations and full event surface.
24. [OpenCode server](https://opencode.ai/docs/server/) - TUI/server split, OpenAPI, SSE, control, and auth endpoints.

### Competitor and implementation evidence

25. [Warp third-party CLI agents](https://docs.warp.dev/agent-platform/cli-agents/overview/) - official universal-agent feature and compatibility matrix.
26. [Warp Claude Code setup](https://docs.warp.dev/guides/external-tools/how-to-set-up-claude-code/) - native CLI install/auth/config preserved with an optional Warp notification plugin.
27. [Warp custom-wrapper issue #8579](https://github.com/warpdotdev/warp/issues/8579) - concrete command-detection failure for wrapper aliases.
28. [Warp universal-agent AMA](https://www.reddit.com/r/warpdotdev/comments/1slf86f/we_just_launched_universal_agent_support_in_warp/) - community reports on tmux/SSH plugins, TUI I/O conflicts, and terminal-first backlash.
29. [tmux-agent-status](https://github.com/samleeney/tmux-agent-status) - open implementation of hook-backed state plus generic status-file fallback.
30. [workmux](https://github.com/raine/workmux) - multi-agent tmux/worktree manager and evidence of uneven waiting-state support.
31. [Codex issue #21615](https://github.com/openai/codex/issues/21615) - user-consented hook trust friction for wrapper/IDE installers.
32. [Codex issue #21990](https://github.com/openai/codex/issues/21990) - request for stable hook/session metadata instead of runtime-log parsing.
33. [Codex issue #2109](https://github.com/openai/codex/issues/2109) - historical demand and provenance for lifecycle hooks.
