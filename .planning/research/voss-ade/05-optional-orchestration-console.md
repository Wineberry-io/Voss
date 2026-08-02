# Optional Orchestration Console for a Terminal-First Voss ADE

**Research date:** 2026-07-19  
**Scope:** Multi-agent coordination UX and product architecture, with emphasis on a console that is strictly optional and does not replace users' existing terminal workflows or CLI agents.  
**Evidence base:** 39 linked sources spanning official product documentation, public repositories, release notes, issue reports, research, and user criticism.  
**Confidence:** High on documented capabilities and the recommended boundary model; medium on proprietary implementation details; low-to-medium on vendor outcome claims that lack independent validation.

## Executive conclusion

Voss should not make its orchestration console the terminal's operating model. It should make the terminal engine the durable operating model and make the console a projection over terminal, task, worktree, and event state.

The winning product contract is:

> Every shell and existing CLI agent works normally with Voss completely absent. Users can progressively attach observation, coordination, or native Voss orchestration to selected panes without changing the command, account, model, configuration, or TUI that already works for them.

This conclusion is supported by the clearest market patterns:

- **Paneflow has the strongest neutrality boundary.** It runs any binary as an ordinary process, adds richer state only for known agents, keeps provider auth and network traffic with the agent, and uses read-only MCP for cross-pane inspection. That is the closest direct precedent for the requested Voss posture. [Paneflow getting started](https://paneflow.dev/docs), [Paneflow product documentation](https://paneflow.dev/)
- **Warp demonstrates the value and danger of a two-plane product.** Its terminal remains useful with AI globally disabled, and it can enrich third-party CLI agents. Its separate Oz control plane provides runs, environments, schedules, transcripts, and artifacts. At the same time, user criticism repeatedly objects when Oz changes or dominates the everyday terminal experience. [Warp local agents](https://docs.warp.dev/agent-platform/local-agents/overview), [Oz overview](https://docs.warp.dev/agent-platform), [Warp user criticism](https://www.reddit.com/r/warpdotdev/comments/1r404b6/what_have_you_done_to_warp_terminal/)
- **BridgeSpace offers a compelling visual vocabulary, but its orchestration is vertically integrated.** BridgeBoard, BridgeSwarm, shared memory, roles, mission tree, and command bar are useful references. However, BridgeSwarm requires BridgeSpace and relies on a proprietary coordination layer. Vendor pages also conflict on scale and access, so its outcome claims need cautious treatment. [BridgeSpace](https://www.bridgemind.ai/products/bridgespace), [BridgeSwarm](https://www.bridgemind.ai/bridgeswarm), [BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace)
- **Codemux exposes the most useful negative evidence.** Its current orchestration panel has phases, live agent drill-down, token estimates, approval, and stop controls, but the docs admit Claude-only support, heuristic attribution, approximate token accounting, a disabled pause button, a restart stub, and a stop action that interrupts the whole turn. A console is harmful when it presents controls or state that are not authoritative. [Codemux workflow orchestration](https://docs.codemux.org/workflow-orchestration)
- **Claude Code teams prove that tmux is a credible display substrate, not a sufficient control plane.** The feature uses independent sessions, a shared task list, direct messaging, and tmux/iTerm split panes. Anthropic also documents coordination overhead, token cost, lagging task status, incomplete resumption, and orphaned tmux sessions. Voss should own durable orchestration state above tmux while treating tmux as process/session authority. [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams)

The recommended Voss product has three independent planes:

1. **Terminal plane:** tmux-backed, provider-neutral, always available, and authoritative for processes, panes, attachment, and byte streams.
2. **Interoperability plane:** optional observation and adapters for process identity, agent status, notifications, session resume, hooks, ACP, and MCP.
3. **Voss orchestration plane:** explicitly activated task graphs, roles, budgets, approvals, audit, review, and multi-agent coordination.

The first screen remains the terminal. The orchestration console opens only on command, only starts Voss services when needed, and can be closed without affecting any terminal or third-party agent process.

## Research method and evidence labels

This report distinguishes four evidence strengths:

| Label | Meaning |
|---|---|
| **Verified, primary** | Behavior documented in official technical documentation, a public repository, or detailed release notes. |
| **Verified claim, vendor-only** | Specific product behavior claimed by the vendor but not independently reproduced during this research. |
| **Preview or experimental** | Explicitly labeled beta, preview, experimental, simulated, disabled, or limited. |
| **Anecdotal criticism** | User report or issue evidence useful for identifying failure modes, but not proof of prevalence. |

Marketing scale claims, benchmark claims, and claims such as "zero conflicts" are not treated as demonstrated outcomes unless a reproducible method is available.

## What an orchestration console is actually for

A terminal grid already solves process visibility. A useful console must solve the problems that become hard when several long-running processes, agents, branches, and approvals exist at once:

1. **Attention:** Which pane needs the human now, and why?
2. **Ownership:** Which task, files, branch, and worktree belong to which worker?
3. **Intent:** What objective and constraints is each worker operating under?
4. **Control:** Can the user steer, pause, stop, retry, reassign, or approve through a real control path?
5. **Evidence:** What commands ran, what changed, what checks passed, and what remains an unverified claim?
6. **Integration:** How do independently produced changes move through review, conflict resolution, and merge?
7. **Cost and policy:** What resources, permissions, budgets, and external systems did a run consume?

The console should not duplicate raw terminal output, replace a CLI's native conversation UI, choose a provider on the user's behalf, or pretend that an unknown process has structured state it does not expose.

## Competitive capability comparison

| Product | Default daily-driver surface | Optional coordination surface | Existing CLI neutrality | Coordination model | Review/evidence | Important caveat |
|---|---|---|---|---|---|---|
| **Warp + Oz** | Terminal, panes, vertical tabs, editor/review | Agent Management Panel in Warp; separate Oz web app for cloud runs | Strong but recognition is adapter/command dependent; AI can be globally disabled | Local parallel sessions plus Oz cloud parent/child orchestration, schedules, APIs, and integrations | Diff review, run transcript, artifacts, credits, environment and trigger metadata | Product pressure toward Oz has generated user backlash; wrapper commands can lose rich agent detection |
| **BridgeSpace** | Native multi-pane terminal grid with editor/browser | BridgeBoard and BridgeSwarm mission view | Claims support for several terminal agents, but orchestration requires BridgeSpace and a proprietary layer | Coordinator, builders, scout, reviewer; file ownership; mailbox; quality gates | Board state, mission tree, review, memory | Mostly vendor evidence; product, docs, and demo differ; the browser demo is explicitly a simulation |
| **Paneflow** | Local terminal workspace | Agents, Review, worktree, and pane-context surfaces | Best-in-class stated boundary: any binary works; no provider proxy; unknown CLIs stay ordinary | Human-supervised parallel panes; read-only MCP and JSON-RPC, not a mandatory meta-agent | Branch/worktree diff, prefilled review prompts, agent state, server state | It is not tmux-backed and explicitly positions itself as replacing a local multiplexer |
| **Codemux** | Linux-first terminal/browser/worktree workspace | OpenFlow and newer Workflow Orchestration panel | Multiple CLI presets, but new structured Workflow is Claude-only | Named phases, orchestrator, role agents, approval, stuck detection, drill-down | Phase/agent summaries, tool calls, findings, tokens, elapsed time | Attribution and token counts are approximate; pause/restart incomplete; stop scope is wrong |
| **Claude Code teams** | Claude Code terminal session | In-process team switcher or tmux/iTerm split panes and task list | None outside Claude Code | Lead, independent teammates, shared dependency-aware tasks, direct messages | Individual terminal visibility and task list | Experimental; expensive; status, resume, and cleanup limitations |
| **OpenAI Codex app** | Dedicated agent command center, not a general terminal-first product | Threads grouped by project, isolated worktrees, diff review, editor handoff | Reuses Codex CLI history/config, but is Codex-specific | Parallel agent threads and subagents with structured app-server events | In-thread diff, approvals, worktree isolation, durable thread/turn/item model | Strong protocol model, weak precedent for cross-provider neutrality |
| **Google Antigravity 2.0** | Standalone agent command center | Projects, synchronous/asynchronous agents, subagents, artifacts, browser controls | Model/tool extensibility exists, but the product owns the agent experience | Central launch/monitor/orchestrate model with project-scoped tools and artifacts | Plans, diffs, diagrams, screenshots, browser recordings | Separating the manager from the IDE is controversial; high autonomy expands the permission and containment burden |

## Product findings by competitor

### Warp and Oz

**Verified capabilities**

- Warp's local terminal UI supports concurrent conversations, panes, third-party CLI agents, notifications, rich input, code review, and terminal context. Its AI features can be globally disabled in settings. [Local Agents overview](https://docs.warp.dev/agent-platform/local-agents/overview)
- Warp recommends local multi-agent patterns that are not proprietary orchestration: put any supported CLI in separate tabs and worktrees, assign explicit file and validation ownership, then compare diffs. [Warp multi-agent guide](https://docs.warp.dev/guides/agent-workflows/how-to-run-multiple-ai-coding-agents/)
- Oz is a distinct orchestration platform spanning desktop, web, CLI, API, SDK, schedules, triggers, environments, secrets, and hosted or self-hosted execution. [Oz overview](https://docs.warp.dev/agent-platform), [Oz CLI](https://docs.warp.dev/reference/cli), [Oz architecture](https://docs.warp.dev/enterprise/enterprise-features/architecture-and-deployment)
- The Oz web app's run ledger includes status, title, environment, creator, source, artifacts, credits, transcripts, filters, schedules, and integrations. This is materially more useful than a large chat transcript. [Oz web app](https://docs.warp.dev/agent-platform/cloud-agents/oz-web-app)
- The API returns a run ID immediately, exposes lifecycle states, and provides a session link to the full transcript, commands, file changes, and output. [Oz API and SDK quickstart](https://docs.warp.dev/reference/api-and-sdk/quickstart)
- Warp can keep ordinary and AI-enhanced use separate: AI can be disabled, local conversations default to local storage, and cloud synchronization is optional for local conversations. [Warp local agents](https://docs.warp.dev/agent-platform/local-agents/overview), [Interacting with agents](https://docs.warp.dev/agent-platform/local-agents/interacting-with-agents)

**What Voss should copy**

- Separate the daily terminal surface from the fleet/run control plane.
- Make status, worktree, diff, notification, and review useful for third-party CLIs, not only the native orchestrator.
- Represent every orchestration run with an immutable identity and queryable lifecycle, transcript, artifact set, and origin.
- Let users start locally and later move selected workloads to remote or isolated execution without changing the ordinary pane model.

**What Voss should avoid**

- Do not make native orchestration visually or behaviorally dominate the terminal. Multiple Warp users describe the terminal becoming more confusing or less focused as Oz surfaces expanded. This is anecdotal but directly relevant product feedback. [User criticism of Oz in the terminal](https://www.reddit.com/r/warpdotdev/comments/1r404b6/what_have_you_done_to_warp_terminal/), [Requests to restore the older agent-mode experience](https://www.reddit.com/r/warpdotdev/comments/1rgiesj/some_new_settings_restore_old_agent_mode/)
- Do not infer agent identity only from an executable name. Warp issue #8579 shows that aliases and wrappers such as `omx` and `omc` lose recognition and status. Users need configurable command matching plus an explicit "attach as agent" action. [Warp custom wrapper issue](https://github.com/warpdotdev/warp/issues/8579)
- Do not couple non-AI terminal value to AI telemetry or plan requirements. Warp's privacy page says paid plans can opt out of telemetry while retaining AI, whereas the free plan requires telemetry for AI. Whatever Voss's eventual business model, terminal operation should never depend on Voss AI telemetry. [Warp privacy overview](https://www.warp.dev/privacy)

### BridgeSpace, BridgeBoard, and BridgeSwarm

**Verified claims, mostly vendor-only**

- BridgeSpace documents 1 to 16 terminal panes, command blocks, editor, file browser, workspaces, Kanban tasks, agent configuration, and direct task execution in terminals. [BridgeSpace technical docs](https://docs.bridgemind.ai/docs/bridgespace)
- The current product page describes BridgeBoard as a two-way synced Kanban, BridgeMemory as Markdown in `.bridgememory/` shared over MCP, and BridgeSwarm as coordinator/builders/scouts/reviewers in a live mission tree with an `@` command bar. [BridgeSpace product page](https://www.bridgemind.ai/products/bridgespace)
- BridgeSwarm says it uses exclusive file ownership, structured roles, quality gates, real-time coordination, and teams commonly sized at three to five agents. It explicitly requires BridgeSpace. [BridgeSwarm product page](https://www.bridgemind.ai/bridgeswarm)
- The vendor's architecture explanation correctly identifies common problems: excessive inter-agent chatter, overlapping work, vague completion criteria, and missing escalation. Its proposed answer is constrained roles, ownership, and structured escalation. The claimed outcomes, including "zero file conflicts," are not independently substantiated. [BridgeSwarm design post](https://www.bridgemind.ai/blog/bridgeswarm-multi-agent-coding-team)
- The release ledger provides stronger evidence that a real desktop product exists and is actively maintained. It documents durable pane/session identity, Claude and Codex resume, swarm stop/resume paths, mailbox/watch cleanup, terminal backpressure, and several heavy-output failure fixes. [BridgeSpace changelog](https://www.bridgemind.ai/changelog)

**Evidence cautions**

- The interactive web demo explicitly calls itself a simulation. It is useful for evaluating information architecture, not runtime fidelity or orchestration reliability. [BridgeSpace demo](https://www.bridgemind.ai/products/bridgespace/demo)
- Vendor surfaces are inconsistent. The technical docs say basic features are free and Pro unlocks multiple tabs, Kanban, agent configuration, and prompts, while the product page says BridgeSpace is included with every paid plan. The product page emphasizes up to 16 terminals, while the BridgeMind homepage claims hundreds of agents. [BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace), [BridgeSpace product page](https://www.bridgemind.ai/products/bridgespace), [BridgeMind homepage](https://www.bridgemind.ai/)
- Independent, technically detailed reviews of BridgeSwarm were not found. Confidence in the exact coordination and enforcement implementation is therefore medium at best.

**What Voss should copy**

- A task board can be a useful optional input surface when board state is bidirectional and agents can file evidence, blockers, and review requests.
- A mission tree is a strong spatial representation for parent, child, role, and dependency relationships.
- One command bar with explicit targeting, such as `@reviewer`, `@task:123`, or `@all`, is more efficient than opening every pane to redirect work.
- Durable mapping between a task/run, pane, CLI session, worktree, and provider account is essential for honest restart and resume.
- The changelog's explicit hard-stop, teardown, and stale-channel recovery work is more instructive than the marketing: orchestration cleanup is a first-class subsystem.

**What Voss should avoid**

- Never require Voss orchestration to obtain terminal grids, worktrees, diffs, agent status, or review.
- Do not put proprietary shared memory in every repo by default. Repository memory should be an explicit, reviewable project choice; user-private and terminal-operational state belongs in app data.
- Do not market large swarm counts as a product goal. The usable constraint is how many independent ownership domains, approvals, diffs, and failure states a human can supervise.
- Roles must be enforceable capability and ownership policies, not prompt personas with authoritative-looking labels.

### Paneflow

**Verified, primary**

- Paneflow starts each pane as a normal shell and tells users to launch the agent they already use. Known agents receive richer status; unknown CLIs remain normal terminal panes. It does not choose models or proxy provider traffic, and each CLI retains its own account, API, and network path. [Paneflow getting started](https://paneflow.dev/docs)
- The product groups panes, branches, diffs, dev servers, and sessions by workspace. It offers working, waiting, stalled, failed, and done state for supported agents. [Paneflow product page](https://paneflow.dev/)
- Its cross-pane MCP capability is read-only: list panes, read output, and search output. JSON-RPC is the separate automation surface for splits, prompts, and layouts. This capability separation reduces the risk of an agent silently controlling peers. [Paneflow product page](https://paneflow.dev/)
- Review opens the chosen CLI in the branch worktree and pre-fills a review prompt, but does not submit it. The human can read and edit before pressing Enter. Multiple reviewers receive different framing to reduce simple agreement. [Paneflow Review](https://paneflow.dev/es/docs/review)
- Paneflow explicitly acknowledges its boundary relative to tmux: Paneflow owns local supervision, while tmux owns durable headless sessions, detach/reattach, SSH, control mode, capture, and automation. [Paneflow versus tmux](https://paneflow.dev/compare/tmux)
- The project states that it is local, open source, requires no account, sends no telemetry, and has no mandatory remote service. [Paneflow introduction](https://paneflow.dev/blog/introducing-paneflow)

**What Voss should copy**

- The core neutrality rule, including user-owned authentication and provider network paths.
- Progressive enhancement: unknown command, known command, hook-enabled agent, and structured protocol agent are different capability levels.
- Read-only pane context should be the default inter-agent bridge. Writing to another pane should require a separate, explicit capability.
- Review prompt prefill without automatic submission is a good trust-preserving handoff between graphical context and a third-party TUI.
- "Next waiting agent" is a more valuable daily-driver command than a decorative fleet animation. Paneflow gives it a dedicated shortcut. [Paneflow keybindings](https://paneflow.dev/docs/keybindings)

**Where Voss can differentiate**

- Paneflow is not tmux-backed and does not provide durable headless detach/reattach. Voss can combine the neutral supervisor UX with tmux's durable engine.
- Paneflow's console is primarily observational. Voss can add an optional, auditable coordination state machine without taking over the third-party CLI runtime.
- Voss can make the same session inventory available locally, over SSH, and through a headless control API.

### Codemux and OpenFlow

**Verified, primary**

- Codemux is an open-source Linux-first workspace with terminal panes, browser panes, worktrees, diff review, notifications, CLI/socket control, and OpenFlow. [Codemux repository](https://github.com/Zeus-Deus/codemux)
- OpenFlow defines orchestrator, planner, builder, reviewer, tester, debugger, and researcher roles; structured `ASSIGN` and `DONE` messages; planning, active, waiting-approval, and completed phases; user message injection; and time-based stuck detection. [OpenFlow documentation](https://docs.codemux.org/openflow)
- Codemux's newer Workflow Orchestration surface requires user approval before execution, exposes the exact script, shows phase progress, agent/tool drill-down, findings, tokens, and elapsed time, and can open referenced files. [Workflow Orchestration](https://docs.codemux.org/workflow-orchestration)
- Agent attention state is hook-based. Codemux modifies Claude settings to send lifecycle events to a local HTTP server; agents without equivalent hooks do not receive the same state UI. [Codemux agent status](https://docs.codemux.org/agent-status)

**The most important negative lessons**

The newer Codemux documentation is unusually candid:

- Workflow orchestration is Claude-only.
- Pause is visible but disabled.
- Per-agent restart is a stub.
- Stop interrupts the entire turn rather than only the workflow.
- Phase and token attribution are heuristic and approximate.
- Long results are truncated.

This is exactly what Voss must prevent. A control surface creates an implied contract. If a button is present, it must be backed by an authoritative command, a scoped target, an acknowledgement, and a terminal failure state. If a metric is estimated, it must be labeled as estimated and show its source.

### Claude Code agent teams

**Verified, primary, experimental**

Anthropic's agent teams are independent Claude Code sessions with a lead, teammates, shared dependency-aware task list, direct teammate messaging, and either an in-process display or split panes using tmux/iTerm2. Claude asks for approval before creating a team. [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams)

The same official page provides important constraints:

- Teams use significantly more tokens and add coordination overhead.
- They work best on genuinely independent research, review, new modules, competing debugging hypotheses, or cross-layer work.
- Sequential work, same-file editing, and tightly coupled tasks are better handled by one session or subagents.
- Task state can lag and block dependencies.
- In-process teammates cannot currently be resumed reliably.
- Shutdown can be incomplete and tmux sessions can be orphaned.
- The team lead may declare completion while tasks remain.

**Implication for Voss**

Voss should treat fan-out as a deliberate execution mode with a decomposition preview, collision analysis, resource estimate, and user confirmation. "More agents" is not the default response to a large task. A shared task list is necessary but not sufficient; task completion needs independent evidence and reconciliation against live process/worktree state.

### OpenAI Codex app and app-server

**Verified, primary**

- The Codex app organizes parallel agent threads by project, gives agents isolated worktrees, embeds diff review and comments, and reuses session history and configuration from the Codex CLI and IDE extension. [Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)
- Later updates added multi-file and terminal views, PR review, remote development over SSH, and an in-app browser. [Codex for almost everything](https://openai.com/index/codex-for-almost-everything/)
- Codex app-server exposes the stronger architectural precedent: structured `Thread`, `Turn`, and `Item` primitives; start/resume/fork; streaming lifecycle events; interrupts; scoped approvals; PTY process control; authentication state; backpressure; and generated version-matched schemas. [Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)

**Implication for Voss**

The Codex product is not provider-neutral, but its event protocol is a good reference. Rich console state should come from structured events with stable IDs and explicit lifecycle transitions. It should not come from scraping the rendered TUI or asking an agent whether it is done. Voss's native protocol can provide this richness while third-party agents stay on progressively weaker capability levels.

### Google Antigravity

**Verified, primary**

- Antigravity 2.0 is now a standalone command center independent of an IDE. It launches and monitors synchronous and asynchronous agents, manages subagents, executes commands, reads/writes files, integrates skills and MCP servers, controls Chrome, and creates plans and artifacts. [Antigravity 2.0 overview](https://www.antigravity.google/docs/overview)
- The earlier IDE model used editor, terminal, browser, parallel local agents, tasks, and artifacts such as Markdown, diffs, diagrams, images, and browser recordings. [Antigravity IDE overview](https://www.antigravity.google/docs/ide-overview)
- Its browser agent uses an isolated Chrome profile and URL allow/deny controls, and can produce screenshots and action recordings. [Antigravity browser documentation](https://antigravity.google/docs/browser?id=GoogleAntigravity)
- Its agent settings scope default file access to project folders and local app data and expose artifact review controls. [Antigravity agent settings](https://www.antigravity.google/docs/agent-settings)

**Cautions**

- Some users object to moving the agent manager into a separate app, particularly when it breaks the work loop between planning and implementation. This is anecdotal but shows that surface separation needs strong deep-linking and preserved state. [Antigravity separation criticism](https://www.reddit.com/r/AntigravityGoogle/comments/1tkmged/why_did_google_split_antigravity_20_into_a/)
- Agentic browser and terminal access creates a compound prompt-injection and containment problem. A Cloud Security Alliance research note describes attacks that combine untrusted content, native tools, filesystem access, and browser exfiltration. The report should be treated as security research, not proof of exploit prevalence, but the architectural class is credible. [CSA Antigravity sandbox-escape research note](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/04/CSA_research_note_agentic-ide-prompt-injection-sandbox_escape_20260422-csa-styled-1.pdf)

**Implication for Voss**

The console can be a distinct mode without becoming a separate product. Switching from terminal to console must preserve workspace, focused pane, selected task, run, and worktree context. Every artifact should be evidence attached to a task or run, not a disconnected gallery. Browser control should arrive after terminal, permissions, worktree isolation, and event/audit foundations are correct.

## The Voss target model

### 1. Terminal plane: authoritative and Voss-free by default

The tmux engine is responsible for:

- Servers, sessions, windows, panes, PTYs, process groups, detach/reattach, resize, raw input/output, and capture.
- Stable tmux identifiers that survive closing and reopening the desktop UI.
- Local and SSH-attached session discovery.
- A faithful terminal even when Voss is uninstalled, disabled, signed out, offline, or broken.

The terminal-only invariant should be testable:

| Resource or behavior | Console off, ordinary shell |
|---|---|
| Voss sidecar processes | 0 |
| Voss network requests | 0 |
| Voss environment variables injected | 0 |
| `.voss` or other project files created | 0 |
| Agent/provider configuration rewritten | 0 |
| CLI command or arguments changed | 0 |
| CLI account/model/network path changed | 0 |

Closing the console must not terminate panes. Restarting or upgrading Voss must not terminate tmux sessions. Uninstalling Voss should leave ordinary tmux sessions discoverable with standard tmux commands.

### 2. Interoperability plane: progressive enhancement, never coercion

Use explicit integration levels rather than a binary "agent/non-agent" classification:

| Level | Name | Source of truth | Console capability |
|---|---|---|---|
| **L0** | Raw process | tmux/process state only | Title, cwd when available, foreground command, output, exit/bell, manual label |
| **L1** | Observed CLI | Shell integration, OSC, prompt markers, process tree | Busy/idle heuristic, attention notification, branch/cwd, command blocks where reliable |
| **L2** | Adapted agent | User-approved hooks or agent-specific adapter | Working/waiting/permission/done, session ID, resume command, usage if the agent exposes it |
| **L3** | Protocol agent | ACP or equivalent structured lifecycle | Messages, plans, tools, approvals, artifacts, interrupt/steer with protocol acknowledgement |
| **L4** | Voss native | Voss REST/SSE or local protocol | Full orchestration, roles, task graph, budgets, gates, audit, replay, policy, delegation |

Rules:

- Users can manually promote or demote a pane's integration level.
- Detection must support arbitrary executable paths, aliases, wrappers, environment managers, and custom commands.
- An adapter defines argv construction, detection, hooks, session/resume behavior, capabilities, and cleanup. There is no universal `--model`, `--cwd`, or prompt grammar.
- An agent keeps its existing credentials and configuration. Voss never imports provider secrets merely to observe a local CLI.
- Hook installation is diff-previewed, scoped, reversible, and never performed because the user opened a terminal pane.
- Unknown state is shown as unknown. Heuristic state is labeled heuristic.

### 3. Voss orchestration plane: attachable to existing work

The user should be able to:

1. Open Voss and use it as an ordinary tmux terminal all day.
2. Start `claude`, `codex`, `gemini`, `opencode`, a wrapper, a local model, or an internal company CLI exactly as they do elsewhere.
3. Optionally choose **Attach to Voss** for one or more existing panes.
4. Give the attached work a task, role, worktree, policy, budget, or review gate.
5. Open **Orchestra** to see the resulting task/run graph.
6. Detach from Voss without stopping the CLI or deleting its worktree.

Attaching does not need to turn a third-party agent into a Voss-native worker. At minimum it can create an external-worker record with a target, owner, worktree, status source, evidence checklist, and operator notes. Voss-native capabilities appear only when supported.

### Console relationship to the terminal

Recommended surface hierarchy:

- **Startup:** Terminal grid, always.
- **Peripheral status:** A quiet, collapsible attention rail showing only running, waiting, blocked, failed, or review-ready items.
- **Fast action:** "Next attention item" moves focus to the relevant terminal or approval.
- **Full console:** A user-invoked `Orchestra` workspace/tab, not a permanent overlay.
- **Return path:** Escape or a terminal shortcut returns to the exact pane, cursor, and scroll position.

The full console should have five views, with no default marketing/dashboard page:

1. **Now:** Attention queue, pending approvals, failed checks, blocked tasks, and stale workers.
2. **Plan:** Dependency-aware tasks with owner, worktree, scope, and definition of done.
3. **Orchestra:** Run tree showing parent/child relationships, provider/CLI, capability level, state source, elapsed time, and resource use.
4. **Review:** Changes, checks, conflicts, evidence, reviewer findings, and integration actions.
5. **Audit:** Append-only event ledger with filters by task, worker, pane, command, approval, artifact, and policy decision.

Memory and configuration belong in settings or context inspectors, not as first-class daily navigation unless user research proves otherwise.

## Authoritative state architecture

### Core entities

| Entity | Stable identity and responsibility |
|---|---|
| **TerminalSession** | tmux server/session identity and connection metadata |
| **Pane** | tmux pane identity, cwd, process group, attachment state |
| **AgentAttachment** | Optional mapping from pane/process to an adapter/protocol and capabilities |
| **Task** | Desired outcome, scope, dependencies, owner, acceptance criteria |
| **Run** | One execution attempt for a task, including start/end and status source |
| **Worktree** | Repo, path, branch, base SHA, ownership, setup and cleanup state |
| **Approval** | Requested action, scope, policy, decision, actor, expiry |
| **Artifact** | Diff, plan, report, log excerpt, screenshot, recording, PR, or patch |
| **Check** | Command or external verification, result, output reference, provenance |
| **Event** | Immutable fact with timestamp, producer, subject IDs, and payload version |

### State must carry provenance

Every prominent console state should answer "who says so?":

- `running` from tmux process existence is observed.
- `waiting_for_permission` from a signed hook or protocol event is reported.
- `done` from an agent message is claimed.
- `verified` from a recorded check exit code and artifact is evidenced.
- `merged` from Git state is reconciled.

Do not collapse these into a single green check. A worker can claim completion while tests fail or a worktree has uncommitted changes.

### Event flow

```text
tmux control mode / process observer ----+
shell integration / OSC ----------------+
agent hooks and adapter events ----------+--> normalized append-only event log
ACP or agent-native protocol ------------+                  |
Voss native REST/SSE --------------------+                  v
Git/worktree/check observers ------------+          materialized console views
operator commands -----------------------+                  |
                                                            v
                                               scoped command + acknowledgement
```

The console reads materialized views. It does not directly mutate arbitrary UI state and assume the runtime followed. Every user control issues a scoped command and waits for an acknowledgement or timeout event.

### Control capability contract

For each worker, advertise only supported actions:

| Action | Minimum backing capability |
|---|---|
| Focus/open pane | Live tmux pane |
| Send text | Explicit pane input permission; visible preview for multi-line/pasted commands |
| Interrupt | PTY/process-group interrupt with acknowledged target |
| Stop | Scoped run or process-group termination with escalation policy |
| Pause/resume | Runtime/protocol support, not a UI-only state |
| Restart | Adapter provides reconstructable argv, cwd, environment policy, and session semantics |
| Resume conversation | Adapter provides a verified session ID and resume command |
| Approve/deny | Protocol or hook request has a stable approval ID and expiry |
| Reassign task | Orchestrator owns task state; does not imply the terminal process received new context |

If Voss cannot stop only the selected run, label the broader consequence before confirmation. Do not repeat Codemux's "Stop workflow" control that actually stops the whole turn.

## Coordination model

### Tasks before roles

The primary unit is a task with scope and evidence, not an agent persona. Roles are reusable policy bundles:

- Allowed paths or ownership domain.
- Read/write/execute/network capabilities.
- Required checks and review gates.
- Context sources.
- Budget and concurrency limits.
- Escalation target.

A "Reviewer" is meaningful when it is read-only, receives a clean diff and requirements, and can block an integration gate. The label alone provides no safety.

### Worktree and file ownership

Worktree isolation should be the default for parallel write-capable tasks, but Voss must show that worktrees delay rather than eliminate conflicts. Before launch:

- Show proposed task decomposition and dependency graph.
- Show worktree and branch allocation.
- Detect overlapping declared paths or packages.
- Require one owner for shared boundaries.
- Designate other workers as read-only reviewers or sequence them.
- Record the base SHA for later drift and merge analysis.

BridgeSwarm's emphasis on file ownership, Warp's explicit planning guidance, Codex's isolated worktrees, and Claude's warning against same-file parallelism all converge on this point. [BridgeSwarm design post](https://www.bridgemind.ai/blog/bridgeswarm-multi-agent-coding-team), [Warp multi-agent guide](https://docs.warp.dev/guides/agent-workflows/how-to-run-multiple-ai-coding-agents/), [Codex app](https://openai.com/index/introducing-the-codex-app/), [Claude Code teams](https://code.claude.com/docs/en/agent-teams)

### Shared context

The default cross-pane tool should be read-only:

- List pane/task/run metadata.
- Read a bounded, redacted slice of scrollback.
- Search pane output.
- Read task artifacts and check results.
- Read ownership and dependency state.

Write operations are separate tools with narrower permission:

- Send a message to an attached structured agent.
- Queue text for a terminal pane with operator approval.
- Assign or update a Voss task.
- Request a shutdown or retry.

This follows Paneflow's useful distinction between read-only MCP context and JSON-RPC automation, while retaining Voss-native messaging for fully opted-in workers.

### Completion and review

Completion is a gate, not a chat message:

1. Worker submits a completion claim and summary.
2. Voss snapshots changed paths and diffstat.
3. Required checks execute or are explicitly waived by a named human.
4. A fresh-context review can inspect requirements, plan, diff, and test evidence.
5. Conflicts and base-branch drift are evaluated.
6. The user chooses integrate, return with findings, keep branch, open PR, or discard.

Paneflow's editable prefilled review, Warp's diff comparison, BridgeSwarm's reviewer gate, and Codex's in-thread diff commenting all support a review surface as the natural endpoint of orchestration. [Paneflow Review](https://paneflow.dev/es/docs/review), [Warp multi-agent guide](https://docs.warp.dev/guides/agent-workflows/how-to-run-multiple-ai-coding-agents/), [BridgeSwarm](https://www.bridgemind.ai/bridgeswarm), [Codex app](https://openai.com/index/introducing-the-codex-app/)

## Recommendation priorities

### P0: Enforce the non-adoption contract

Ship and test these before adding more console views:

- Terminal startup never launches Voss services.
- Plain shells receive no Voss variables, hooks, files, or modified argv.
- Terminal/session persistence uses app data and tmux state, not repository `.voss` state.
- Closing or crashing the desktop does not kill tmux sessions.
- Console launch and Voss attachment are explicit actions with a clear detach path.
- Existing CLI agents keep their own auth, models, config, and TUI.

### P1: Build the neutral supervisor console

- Durable mapping of tmux session, pane, process, workspace, worktree, and optional agent attachment.
- Attention rail and "next attention item."
- Adapter registry with custom executable/alias/wrapper recognition.
- State provenance and confidence labels.
- Notification routing and quiet hours.
- Worktree-aware diff/review with editable prompt handoff to any CLI.
- No Voss task engine required.

This phase should already be valuable to a user who never creates a Voss run.

### P2: Add explicit Voss attachment

- Attach an existing pane/process to a Voss task or external-worker record.
- Start Voss sidecar lazily for the selected workspace.
- Provide task scope, evidence checklist, budgets, approvals, and audit.
- Offer read-only pane/task MCP context.
- Support detach without process termination or project mutation.
- Make console state and controls capability-driven.

### P3: Add native orchestration

- Dependency-aware task graph with decomposition preview.
- Worktree and ownership allocation.
- Structured parent/child runs, direct messaging, scoped steering, and escalation.
- Required verification gates and fresh-context review.
- Accurate usage where protocols expose it; explicitly estimated usage otherwise.
- Crash recovery, idempotent replay, stale-worker reconciliation, hard-stop, and cleanup.

### P4: Remote and automated execution

- Attach to remote tmux sessions over SSH.
- Headless Voss control service with the same run/event schema.
- Isolated environments, secrets, schedules, triggers, API, and web/mobile monitoring only after local lifecycle correctness is proven.
- Separate execution plane from control plane as Warp/Oz does, with explicit disclosure of what data crosses each boundary. [Warp architecture](https://docs.warp.dev/enterprise/enterprise-features/architecture-and-deployment)

## Features ranked by value and fit

| Priority | Feature | Why it matters | Dependency |
|---|---|---|---|
| 1 | tmux detach/reattach and process truth | Makes Voss a credible daily driver | Terminal engine |
| 2 | Attention queue and next-waiting navigation | Solves the immediate multi-agent supervision cost | Observers/adapters |
| 3 | Adapter registry with custom command matching | Prevents lock-in and wrapper breakage | Interop schema |
| 4 | Worktree/task/pane identity | Makes parallel work understandable and recoverable | Git + tmux IDs |
| 5 | Unified diff, checks, and review | Converts agent activity into inspectable outcomes | Git/check runner |
| 6 | State provenance and event ledger | Prevents false confidence and enables audit/recovery | Event model |
| 7 | Explicit attach/detach to Voss | Lets current CLI users adopt capabilities incrementally | Lazy sidecar |
| 8 | Capability-driven control actions | Makes stop/restart/approve trustworthy | Command acknowledgements |
| 9 | Dependency-aware task graph and ownership | Enables safe native fan-out | Voss orchestration |
| 10 | `@`-targeted steering command bar | Efficient control at scale | Structured messaging |
| 11 | Budget, permission, and verification gates | Preserves human control | Native protocol/policy |
| 12 | Remote/cloud fleet console | Extends reach after local correctness | Headless execution |

## Failure modes and required mitigations

| Failure mode | Market evidence | Voss mitigation |
|---|---|---|
| Console replaces or crowds the terminal | Warp user backlash | Terminal is startup/default; console is a user-opened workspace and remembers closed state |
| Proprietary agent becomes required for useful UI | BridgeSwarm requires BridgeSpace; Codex app is Codex-only | Status, worktrees, attention, diff, and review work for raw/third-party CLIs |
| Aliases/wrappers lose recognition | Warp issue #8579 | User-editable adapter matches plus manual attach; never key only on argv[0] |
| Claimed state differs from runtime | Claude task status lag; Codemux heuristic attribution | State provenance, reconciliation, and explicit claimed/observed/verified states |
| UI exposes controls that do not work | Codemux pause/restart stubs | Hide unsupported actions; contract-test every exposed action |
| Stop action has excessive blast radius | Codemux stop interrupts entire turn | Stable target IDs, process-group/run scoping, consequence preview, acknowledgement |
| Resumption targets the wrong account/session/pane | BridgeSpace release history | Persist adapter, provider profile reference, pane ID, cwd, worktree, session ID, and verified resume result |
| Orphaned processes and sessions | Claude team tmux limitation | Reconciliation on startup, owned-resource ledger, graceful/hard stop, safe orphan adoption |
| Parallel agents collide in shared files | BridgeSwarm/Warp/Claude guidance | Worktrees, declared ownership, overlap detection, sequencing, review |
| Swarm wastes tokens coordinating | Claude warning; BridgeSwarm's vendor analysis | Fan-out preview, concurrency/budget limits, independent-task threshold, compact event messages |
| High-output panes freeze renderer | BridgeSpace changelog | tmux capture/backpressure budgets, bounded queues, hidden-pane throttling, byte/escape integrity tests |
| Project gets polluted with orchestration state | BridgeMemory writes `.bridgememory/` | App-data default; repo state only through explicit shareable-project opt-in |
| Cross-pane context becomes cross-pane control | General MCP/tool risk | Read-only MCP by default; separate privileged write/control tools |
| Agent-generated evidence is trusted as fact | Common orchestration failure | Checks captured from process exit and artifacts; fresh-context review; human waiver trail |
| Console security assumes continuous supervision | Antigravity security criticism | Least privilege, worktree scope, approval queue, deny-by-default browser/network controls, audit and recovery |
| Separate console loses implementation context | Antigravity 2.0 user criticism | In-app mode switch and stable deep links to pane/task/run/file with exact focus restoration |

## Release gates for the optional console

Voss should not call the console production-ready until these behaviors are automated or manually demonstrated:

1. **Zero-Voss terminal:** Open a repo, use shells and third-party CLIs for an hour, close/reopen the app, and verify zero Voss process, network, environment, hook, and repository mutation.
2. **Durability:** Kill the UI during high terminal output; all tmux processes continue and reattach with correct pane identity.
3. **Adapter neutrality:** Run raw commands, aliases, wrappers, Claude Code, Codex, Gemini CLI, OpenCode, and an unknown internal CLI. All remain usable; only supported capabilities appear.
4. **Detach safety:** Attach a running CLI to Voss, create task metadata, detach it, stop Voss, and verify the CLI continues unchanged.
5. **Control scoping:** Interrupt, stop, restart, and resume one selected worker while sibling panes continue. Every action records request, acknowledgement, and result.
6. **Crash recovery:** Crash during planning, active work, approval, review, and cleanup. Reconcile task, run, worktree, and process truth without duplicate workers.
7. **State honesty:** Inject missing hooks, late events, contradictory completion claims, and failed checks. The UI must show unknown/stale/claimed/failed states accurately.
8. **Worktree integration:** Run parallel non-overlapping tasks, deliberate overlapping tasks, base-branch drift, merge conflicts, and abandoned branches.
9. **Backpressure:** Stream binary-adjacent bytes, Unicode, ANSI/OSC sequences, and sustained multi-pane output without UI freeze, corruption, or unbounded memory growth.
10. **Permission containment:** Attempt cross-pane writes, out-of-workspace file access, destructive commands, browser exfiltration, and stale approval replay.
11. **No dead controls:** Every rendered command is supported for that selected target; unavailable capabilities have no active button.
12. **Console optionality:** Disable the console feature entirely and verify that the terminal engine, settings, session restoration, and upgrades remain complete.

## Product positioning

Recommended position:

> **Voss is the durable terminal workspace for any CLI agent. Orchestra is the optional control plane when parallel work needs structure, evidence, and governance.**

This is stronger than positioning Voss as another agent:

- Users do not have to choose between Voss and Claude Code, Codex, Gemini CLI, OpenCode, or internal tools.
- Teams can standardize the workspace, review, and audit layer without standardizing one model vendor or harness.
- Voss-native agents can be richer without making third-party agents second-class terminal citizens.
- tmux makes the process/session layer independently durable and inspectable.
- The console earns adoption through attention, worktree, review, and evidence value before a user trusts Voss to orchestrate anything.

## Contradictions and unresolved questions

### Contradictions found

1. **BridgeSpace scale:** Its product and docs emphasize up to 16 terminal panes, while the BridgeMind homepage claims hundreds of agents. Treat 16 visible panes as the supported UI claim and the larger claim as unverified orchestration marketing.
2. **BridgeSpace access:** Technical docs describe a free basic tier with Pro console features, while the current product page says BridgeSpace begins with paid plans. Do not derive product strategy from its packaging claims.
3. **"Agent neutral" status:** Warp and other products use broad universal-support language, but wrapper/alias issues show that enriched behavior depends on integrations. Raw terminal compatibility and rich structured compatibility must be specified separately.
4. **Console truth versus approximation:** Codemux visibly presents phase and usage information while documenting heuristic attribution. Voss must make provenance part of the data model rather than a disclaimer.
5. **Persistence language:** Several products say sessions persist when they mean layouts or resumable agent conversations, not that the original PTY/process remains alive. Voss should reserve "durable session" for tmux process continuity and use "conversation resume" for provider-level reconstruction.

### Open questions for Voss implementation

- Will the first tmux backend use one tmux pane per Voss pane or render a whole tmux window layout? The console data model should not assume either.
- Which state integrations can be achieved without modifying user configuration? Shell integration and process observation should precede hook installation.
- Is ACP mature enough for L3 in the first release, or should the boundary be designed now and implemented later?
- How should Voss authenticate local operator commands so a process in one pane cannot silently control all other panes?
- Which Voss events are durable protocol facts versus UI convenience events today?
- Can Voss task and audit state live entirely in app data until the user explicitly opts into repository-shared `.voss` configuration?
- What is the exact lifecycle for adopting an already running third-party agent whose provider session ID is unknown?

## Confidence and evidence gaps

| Area | Confidence | Gap |
|---|---|---|
| Terminal-first plus optional-console direction | High | Strong convergence across Paneflow, Warp/Oz, tmux-based Claude teams, and user criticism |
| Progressive third-party CLI integration | High | Exact agent hook/API stability changes quickly and needs adapter-level validation |
| BridgeSpace UX vocabulary | Medium-high | Detailed current product and changelog evidence exists |
| BridgeSwarm enforcement and outcome quality | Medium-low | Proprietary system; no credible independent technical evaluation found |
| Codemux limitations | High | Explicitly documented by the product |
| Claude team limitations | High | Explicitly documented as experimental by Anthropic |
| OpenAI app-server event architecture | High | Public protocol documentation is detailed; desktop implementation remains product-specific |
| Antigravity security implications | Medium-high | Architectural risk is credible; incident prevalence and later mitigations were not independently tested |
| Exact console information density and navigation | Medium | Requires usability testing with developers supervising 1, 3, 6, and 10+ concurrent tasks |
| Cross-provider usage/cost normalization | Low | Providers expose incompatible accounting and subscription semantics; estimation should remain labeled |

## Source register

### Warp and Oz

1. [Warp local agents overview](https://docs.warp.dev/agent-platform/local-agents/overview) - official docs; AI disable, third-party CLI agents, review, context, task lists.
2. [Warp agent platform / Oz overview](https://docs.warp.dev/agent-platform) - official docs; terminal versus orchestration platform boundary.
3. [Warp multi-agent workflow guide](https://docs.warp.dev/guides/agent-workflows/how-to-run-multiple-ai-coding-agents/) - official docs; local CLI/worktree and cloud fan-out patterns.
4. [Oz web app](https://docs.warp.dev/agent-platform/cloud-agents/oz-web-app) - official docs; run ledger and management fields.
5. [Oz CLI](https://docs.warp.dev/reference/cli) - official docs; local/cloud launch and configuration.
6. [Oz API and SDK quickstart](https://docs.warp.dev/reference/api-and-sdk/quickstart) - official docs; run IDs, lifecycle, transcript links.
7. [Warp enterprise architecture](https://docs.warp.dev/enterprise/enterprise-features/architecture-and-deployment) - official docs; control/execution plane and hosted/self-hosted boundaries.
8. [Warp interaction and local conversation storage](https://docs.warp.dev/agent-platform/local-agents/interacting-with-agents) - official docs.
9. [Warp privacy](https://www.warp.dev/privacy) - official privacy policy; telemetry and AI plan behavior.
10. [Warp custom wrapper issue #8579](https://github.com/warpdotdev/warp/issues/8579) - public issue; adapter recognition failure mode.
11. [Warp/Oz terminal-focus criticism](https://www.reddit.com/r/warpdotdev/comments/1r404b6/what_have_you_done_to_warp_terminal/) - anecdotal user criticism.
12. [Warp agent-mode customization criticism](https://www.reddit.com/r/warpdotdev/comments/1rgiesj/some_new_settings_restore_old_agent_mode/) - anecdotal user criticism.

### BridgeMind

13. [BridgeSpace documentation](https://docs.bridgemind.ai/docs/bridgespace) - official technical docs.
14. [BridgeSpace product page](https://www.bridgemind.ai/products/bridgespace) - official product claims and UI description.
15. [BridgeSpace interactive demo](https://www.bridgemind.ai/products/bridgespace/demo) - vendor simulation, explicitly labeled.
16. [BridgeSwarm product page](https://www.bridgemind.ai/bridgeswarm) - official product claims.
17. [BridgeSwarm design post](https://www.bridgemind.ai/blog/bridgeswarm-multi-agent-coding-team) - vendor architecture rationale and outcome claims.
18. [BridgeSpace changelog](https://www.bridgemind.ai/changelog) - detailed official release ledger and operational failure fixes.
19. [BridgeMind homepage](https://www.bridgemind.ai/) - vendor scale claims used only to identify inconsistency.

### Paneflow

20. [Paneflow getting started](https://paneflow.dev/docs) - official docs; raw CLI neutrality and provider boundary.
21. [Paneflow product documentation](https://paneflow.dev/) - official docs; state, MCP, sessions, workspaces.
22. [Paneflow Review](https://paneflow.dev/es/docs/review) - official docs; worktree diff and human-submitted review handoff.
23. [Paneflow introduction](https://paneflow.dev/blog/introducing-paneflow) - official project architecture and privacy claims.
24. [Paneflow versus tmux](https://paneflow.dev/compare/tmux) - official comparison; explicit durability boundary.
25. [Paneflow keybindings](https://paneflow.dev/docs/keybindings) - official docs; attention navigation.

### Codemux

26. [Codemux repository](https://github.com/Zeus-Deus/codemux) - public source repository and feature description.
27. [OpenFlow documentation](https://docs.codemux.org/openflow) - official docs; roles, phases, messaging, stuck detection.
28. [Codemux Workflow Orchestration](https://docs.codemux.org/workflow-orchestration) - official docs; detailed panel plus current limitations.
29. [Codemux agent status](https://docs.codemux.org/agent-status) - official docs; hook-based attention state.

### Agent-native command centers

30. [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams) - official docs; experimental team model, tmux panes, and limitations.
31. [Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/) - official OpenAI product architecture.
32. [Codex for almost everything](https://openai.com/index/codex-for-almost-everything/) - official OpenAI update on terminals, SSH, browser, and parallel agents.
33. [Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md) - public official protocol documentation.
34. [Antigravity 2.0 overview](https://www.antigravity.google/docs/overview) - official Google docs; standalone command center.
35. [Antigravity IDE overview](https://www.antigravity.google/docs/ide-overview) - official Google docs; parallel agents and artifacts.
36. [Antigravity browser documentation](https://antigravity.google/docs/browser?id=GoogleAntigravity) - official Google docs; browser isolation and recordings.
37. [Antigravity agent settings](https://www.antigravity.google/docs/agent-settings) - official Google docs; project scope and artifact review.
38. [Antigravity separation criticism](https://www.reddit.com/r/AntigravityGoogle/comments/1tkmged/why_did_google_split_antigravity_20_into_a/) - anecdotal user criticism.
39. [CSA Antigravity prompt-injection research note](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/04/CSA_research_note_agentic-ide-prompt-injection-sandbox_escape_20260422-csa-styled-1.pdf) - independent security research.
