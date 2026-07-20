# Voss ADE Deep Research 09: Competitor Critique and Contradiction Pass

**Research date:** 2026-07-19  
**Scope:** Warp/Oz, BridgeSpace/BridgeSwarm, Paneflow, dmux, workmux, Flowmux, Codemux/OpenFlow, Zed/ACP, tmux constraints, and the current Voss desktop implementation  
**Method:** Cross-checked the local audit and research notes `00` through `06` against official documentation, public repositories, changelogs, issue trackers, and bounded community criticism. More than 40 sources were inspected; primary technical sources carry the most weight.

## Executive Decision

Voss should not compete as another AI terminal, a 16-pane dashboard, or a proprietary replacement for Claude Code, Codex, Gemini CLI, OpenCode, Aider, or internal tools. Those categories are already crowded, and the competitors with the most credible adoption story preserve the user's existing CLI, authentication, provider relationship, and Git workflow.

The differentiated product is:

> **A durable tmux-powered terminal that works completely without Voss, then becomes an auditable agent organization layer only when the user explicitly attaches Voss capabilities.**

This implies three independently useful planes:

1. **Terminal plane:** arbitrary commands, real process continuity through tmux on supported Unix hosts, direct PTY fallback, no Voss environment or repo writes.
2. **Interoperability plane:** progressive enhancement through terminal signals, opt-in hooks, adapters, ACP, and read-only MCP. The CLI still owns auth, models, config, billing, permissions, updates, and its TUI.
3. **Voss plane:** optional task graphs, roles, budgets, gates, messages, evidence, review, audit, and replay attached to selected panes or worktrees.

The current code is strongest in plane 3 and weakest in the terminal and interoperability foundations. The roadmap should reverse that order before adding more orchestration UI.

## Evidence Labels

| Label | Meaning |
|---|---|
| **High** | Directly supported by local source, an official protocol/manual, a public repository, or detailed release notes. |
| **Medium** | Specific first-party product claim that was not independently reproduced. |
| **Low** | Marketing, a simulated demo, isolated issue report, or community criticism useful mainly for finding failure modes. |

Star counts, unsupported benchmark claims, and phrases such as "zero conflicts" are not treated as proof of product quality.

## Decision-Grade Feature Matrix

| Product | Terminal/process authority | Existing CLI neutrality | Agent state | Worktree/review | Orchestration | Platform/remote | Lock-in and evidence |
|---|---|---|---|---|---|---|---|
| **Warp + Oz** | Native terminal; restart restores UI and recent blocks, not documented live process identity | Strong for a named set of CLIs; AI can be disabled | Rich for Warp Agent; selected CLI notifications need setup | Strong Git diff, worktree, inline feedback | Strong proprietary local/cloud run platform | macOS/Linux/Windows; cloud and self-hosted runners; SSH feature gaps | Proprietary and account-centered; product behavior is well documented (**High**) |
| **BridgeSpace + BridgeSwarm** | Native Tauri terminal grid; changelog documents CLI conversation recovery and SSH reconnect, but no tmux authority | Runs several CLI agents, but board/swarm/memory are BridgeMind services | Hook/session-driven for supported agents | Editor/browser and review context; public evidence for a neutral candidate pipeline is weak | Coordinator/builders/scouts/reviewers, mailbox, board, memory, mission tree | Claims macOS/Linux/Windows and SSH | Proprietary paid ecosystem; docs, pricing, demo, and product copy conflict (**Medium**) |
| **Paneflow** | Direct native PTYs; explicitly does not keep processes alive after app exit | Excellent baseline: any binary; provider/auth remain untouched | Hooks/IPC for known agents; unknown CLIs remain terminals | Strong branch/worktree diff and human-submitted review handoff | Local CLI/JSON-RPC flows and read-only MCP; optional auto-submit | macOS/Linux/Windows; explicitly no remote-session persistence | GPL, local-first, no required account; unusually candid boundaries (**High**) |
| **dmux** | tmux is the process authority | Named agents plus plain terminal | Mixed detection and output analysis; notifications on macOS | Worktree per task, file/diff viewer, PR, hooks, two-phase merge | Launcher/supervisor rather than a durable organization model | Unix/tmux oriented | MIT and inspectable; current issues expose send-key, IME, lifecycle, and detection races (**High**) |
| **workmux** | tmux window/session per worktree | User-defined pane commands plus known agent hooks | Hook files; exact capability differs by agent/version | Strong TUI diff/stage, hooks, PR/CI display, merge/rebase/squash/cleanup | Scriptable supervision, no proprietary meta-agent | Unix/tmux; sandbox backends | MIT; extensive changelog reveals the real lifecycle edge-case burden (**High**) |
| **Flowmux** | tmux-backed TUI | Four auto-detected CLIs; forwards input to real panes | Hook/callback-driven status and response preview | Optional worktree and external Git viewer | Lightweight dashboard only | Linux/macOS releases; no Windows | MIT and small/early project; zero open issues is not maturity evidence (**Medium**) |
| **Codemux + OpenFlow** | Detached PTY architecture and session resume claims; not tmux | Presets/custom panes; richer state is uneven | Terminal hooks currently strongest for Claude; chat stream broader | Worktrees, diff, embedded browser | Roles, phases, `ASSIGN`/`DONE`, approval and stuck rescue | Linux product today; Windows OpenFlow disabled; remote work remains partial | Source available under ELv2; marketing outruns some documented behavior (**Medium**) |
| **Zed + ACP** | Direct editor terminals; saved Terminal Threads are recreated | Best conceptual split: native agent, ACP external agent, or raw CLI/TUI thread | Structured through ACP; bell/title signals for raw terminal threads | First-class Git/worktree/editor review | Parallel independent threads, not a policy-heavy organization engine | macOS/Linux/Windows; remote projects supported | Zed is GPL and ACP is open, but ACP v2 and remote transports are still evolving (**High**) |
| **Voss today** | In-process `portable-pty`; layout restoration creates new processes | Intended to be neutral, but generic shells receive Voss env and launch syntax is incorrectly generalized | Strong for native Voss, weak/unreliable for arbitrary CLIs | Voss swarm worktrees exist, but neutral review is absent and CLI swarm auto-merges | Richest local concept: budgets, gates, roles, messages, audit, replay | Tauri targets are broader than tested release readiness | Open code and strong protocol design; foundational behavior contradicts product claims (**High**) |

## Competitor Findings

### Warp and Oz

Warp is the strongest example of polished progressive enhancement around third-party CLIs. Its current third-party toolbelt recognizes many agents and adds rich input, code review, context attachment, tabs, and remote control; notifications are available for only a subset and require plugins or config changes. That honest feature matrix is a useful model for Voss capability negotiation. [Warp third-party CLI agents](https://docs.warp.dev/agent-platform/cli-agents/overview/)

Warp also demonstrates a clean technical idea: a native agent can be attached to an already-running PTY, read the terminal buffer, and request permission before writing. The ownership transfer is explicit and reversible. [Warp Full Terminal Use](https://docs.warp.dev/agent-platform/capabilities/full-terminal-use)

The strongest product surface to copy is the Git-native review panel. It follows changes regardless of whether the user, an external editor, or an agent made them; supports multiple bases, editing, and hunk/file reverts; and makes agent feedback an action on the diff rather than the source of truth. [Warp Code Review](https://docs.warp.dev/code/code-review), [Interactive Code Review](https://docs.warp.dev/agent-platform/local-agents/interactive-code-review)

The main warning is product gravity. Warp now spans terminal, editor, native agents, third-party agents, cloud agents, schedules, integrations, and Oz infrastructure. Recent user criticism repeatedly asks for a clearer terminal-only experience and less automatic movement toward Agent mode. This is anecdotal, not prevalence data, but it directly validates the user's requirement that Voss never become compulsory. [Warp roadmap issue and enterprise criticism](https://github.com/warpdotdev/warp/issues/9233), [Warp community mode criticism](https://www.reddit.com/r/warpdotdev/comments/1rgiesj/some_new_settings_restore_old_agent_mode/)

**Copy:** independent Git review, explicit PTY handoff, capability matrices, queryable run ledger.  
**Avoid:** making the native agent the default interpretation of terminal input, coupling core terminal value to accounts/credits, or allowing the orchestration brand to swallow the daily terminal.

### BridgeSpace and BridgeSwarm

BridgeSpace is the closest visual competitor to the existing Voss app: Tauri/Rust, up to 16 terminals, editor, browser, task board, memory, and a live swarm tree with coordinator/builders/scouts/reviewers. Its release ledger is more useful evidence than its marketing because it documents heavy-output freezes, backpressure, stale renderer channels, account-bound resume, SSH reconnect, and swarm teardown. [BridgeSpace product](https://www.bridgemind.ai/products/bridgespace), [BridgeSpace changelog](https://www.bridgemind.ai/changelog), [BridgeSwarm](https://www.bridgemind.ai/bridgeswarm)

Its product lesson is not "add more panes." It is that durable identity across workspace, pane, CLI session, worktree, and provider account is required before resume and orchestration controls become trustworthy.

The evidence has material contradictions:

- The browser demo explicitly says it is a simulation. It therefore cannot substantiate runtime behavior even though the product page separately describes its displayed frames as the real app. [BridgeSpace demo](https://www.bridgemind.ai/products/bridgespace/demo)
- Technical docs say BridgeSpace has free basic features and Pro unlocks multi-tab/board capabilities; the current product and pricing pages say BridgeSpace is included in paid Basic and above. [BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace), [BridgeMind pricing](https://www.bridgemind.ai/pricing)
- The changelog proves active product work, but conversation resume after restart is not equivalent to live PTY/process continuity. The source and process authority are not public enough to verify that distinction.

**Copy:** mission-tree navigation, targeted `@agent` steering, bidirectional task board, explicit hard-stop/cleanup states.  
**Avoid:** mandatory proprietary memory, account-gated terminal workflows, swarm-count marketing, and roles that are only prompt personas rather than enforced permissions and ownership.

### Paneflow

Paneflow most directly validates the required adoption boundary. A pane starts as a normal shell, any binary works, known agents receive richer status, and unknown agents stay ordinary terminals. It does not choose the model or proxy provider traffic. [Paneflow getting started](https://paneflow.dev/docs)

It also combines the most relevant neutral workflow features: task-oriented workspaces, branch and server visibility, attention queue, worktree diff review, read-only pane context over MCP, and a local JSON-RPC/CLI control plane. Prompt prefill is the default and automatic submission is explicit. [Paneflow repository](https://github.com/arthjean/paneflow), [Paneflow Review](https://paneflow.dev/docs/review), [Paneflow keybindings](https://paneflow.dev/docs/keybindings)

Paneflow's candid tmux comparison identifies Voss's opportunity: it restores layout, cwd, history, and resumable agent conversations, but it does not preserve running processes and has no durable remote detach/reattach. [Paneflow versus tmux](https://paneflow.dev/compare/tmux)

**Copy:** arbitrary-binary baseline, read-only cross-pane context, next-attention navigation, prompt prefill, explicit untrusted-output marking.  
**Differentiate:** add genuine tmux-backed continuity and a deeper optional governance/evidence model without sacrificing Paneflow's neutrality.

### dmux, workmux, and Flowmux

These tools prove that tmux plus Git worktrees is already a recognizable category. dmux makes a pane/task/worktree bundle, supports a plain terminal, provides file/diff inspection, PR creation, hooks, and a two-phase merge. workmux adds a stronger dashboard, WIP versus committed diff, staging, PR/CI state, sandbox backends, multi-window sessions, and extensive lifecycle controls. Flowmux is the smallest Unix-style version: tmux-backed real CLIs, a status grid, optional worktrees, and an external Git viewer. [dmux repository](https://github.com/standardagents/dmux), [dmux documentation](https://dmux.ai/), [workmux repository](https://github.com/raine/workmux), [Flowmux repository](https://github.com/grouzen/flowmux)

Their issue trackers and changelogs expose the operational cost hidden by a simple demo:

- Both dmux and workmux have open reports for sending commands before shell initialization completes. [dmux issues](https://github.com/standardagents/dmux/issues), [workmux issues](https://github.com/raine/workmux/issues)
- Agent-state capabilities drift. workmux added Codex hooks but an open issue reports that Codex still cannot express the waiting state through the available event. Capability must be versioned per agent and event, not represented as one `supported` boolean.
- Worktree lifecycle accumulates races around checked-out targets, nested agents, port conflicts, stale directories, cleanup from inside a worktree, branch naming, and merged PR detection. The workmux changelog is a practical requirements catalog. [workmux changelog](https://github.com/raine/workmux/blob/main/CHANGELOG.md)
- dmux's "complete isolation" prevents simultaneous filesystem writes to one checkout, not semantic conflicts when changes are integrated. Its own two-phase merge exists because conflicts remain possible.
- Flowmux says it can reconnect after "tmux restarts." A restarted tmux server cannot preserve the child processes it formerly owned, so this wording must mean state reconstruction unless another process authority exists. Voss should never use the same ambiguous phrasing.

**Copy:** tmux as process authority, one-command worktree creation, hooks, plain-terminal mode, close-without-delete, keep-after-merge, next-waiting navigation.  
**Avoid:** sending prompts by timing shell readiness, automatic commit/merge/cleanup as one opaque action, output heuristics presented as fact, and assuming one worktree equals one repository in real projects.

### Codemux and OpenFlow

Codemux combines many Voss-adjacent features: terminals, worktrees, browser automation, diff review, MCP in both directions, a CLI/socket API, attention signals, and OpenFlow roles/phases/messages/stuck detection. [Codemux repository](https://github.com/Zeus-Deus/codemux), [OpenFlow docs](https://docs.codemux.org/openflow), [Codemux status docs](https://docs.codemux.org/agent-status)

Its most useful design is the human-versus-agent execution persona. Human terminals retain desktop integration; agent terminals can strip display access or use an opt-in virtual display. This is more precise than labeling an entire app "sandboxed." [Codemux display isolation](https://docs.codemux.org/display-isolation)

Its main warning is claim precision. The product site says "Detached PTYs survive reboots" and then shows a CLI `--resume` command. A live operating-system process cannot survive a machine reboot; only serialized state and a reconstructable or agent-native resume path can. [Codemux product](https://codemux.org/) The site also describes remote hosts as a current capability while the public issue tracker still lists headless remote access and cross-agent conversation continuity as open work. [Codemux issues](https://github.com/Zeus-Deus/codemux/issues)

**Copy:** persona-scoped execution policy, browser verification beside terminals, explicit stuck state, socket automation.  
**Avoid:** conflating CLI conversation resume, layout resurrection, daemon detach, and live process persistence; exposing pause/restart/stop controls without exact runtime scope.

### Zed and ACP

Zed provides the clearest interoperability taxonomy in the market:

1. Zed Agent, where Zed owns the model and tools.
2. External Agent over ACP, where the agent owns runtime/auth/model/config but renders structured UI.
3. Terminal Thread, where the native CLI/TUI owns everything and Zed only organizes the terminal.

[Zed Agents](https://zed.dev/docs/ai/agents), [Zed External Agents](https://zed.dev/docs/ai/external-agents), [Zed Terminal Threads](https://zed.dev/docs/ai/terminal-threads)

That is almost exactly the capability ladder Voss needs. Zed also makes worktree isolation optional per thread and restores linked worktree Git state independently from conversation history. [Zed Parallel Agents](https://zed.dev/docs/ai/parallel-agents), [Zed Git worktrees](https://zed.dev/docs/git)

ACP is a strong structured integration target, not the universal terminal substrate. Today it is JSON-RPC over stdio for local subprocesses; remote HTTP/WebSocket is still a draft. Its terminal methods create commands on behalf of an agent, which is different from attaching to an arbitrary pre-existing tmux pane. Active ACP v2 work is changing session replay, terminal output, diffs, permissions, and capability structure. [ACP architecture](https://agentclientprotocol.com/get-started/architecture), [ACP transports](https://agentclientprotocol.com/protocol/v1/transports), [ACP schema](https://agentclientprotocol.com/protocol/v1/schema), [ACP v2 proposal](https://agentclientprotocol.com/rfds/v2/overview)

**Copy:** explicit harness types, agent-owned configuration, capability negotiation, structured permissions, per-thread worktree choice.  
**Avoid:** making ACP mandatory, assuming ACP owns an existing terminal process, or freezing Voss domain contracts to a protocol whose v2 shape is still moving.

## Contradiction Ledger

### Voss claims versus current code

| Claim or intent | Current evidence | Required correction | Confidence |
|---|---|---|---|
| tmux-powered durable terminal | No production tmux calls; each pane is an in-process `portable-pty` child | Introduce a transport-neutral engine and real tmux backend; label direct PTY as ephemeral | High |
| Process/PTY identity survives reload | Saved schema contains layout/scrollback, and restore spawns a new shell | Distinguish live reattach, CLI resume, and visual reconstruction in code and copy | High |
| Terminal-only use is zero-Voss | Generic `spawn_pty` injects `VOSS_EMBEDDED` and `VOSS_AGENT_ID` | Remove all Voss env, files, sidecar, prompt changes, and network from the default pane | High |
| Per-pane shell selection | Shell value is visible/persisted but spawn falls back to global `$SHELL` | Persist and execute an explicit argv/env/cwd launch spec | High |
| Bring any existing CLI agent | Modal hard-codes agents and applies one `--model --cwd task` grammar | Raw arbitrary command first; adapter-owned argv templates second | High |
| Placement choices work | Current handler always performs a horizontal split | Make controls capability-driven or remove unavailable choices | High |
| Agent lifecycle controls are authoritative | Restart/detach callbacks are empty; stop identifiers do not match PTY transport identity | Introduce stable process/session IDs and acknowledged scoped commands | High |
| Workspace state is isolated | One registry connection can remain bound to the first workspace; live server reuse can ignore cwd | Bind every registry, sidecar, engine, worktree, and event to a stable workspace ID/root | High |
| Terminal-only use does not adopt Voss | Structural autosave writes repo-local `.voss/session.json` | Put private runtime state in app data; create `.voss` only after explicit project enrollment | High |
| Voss review gates protect integration | CLI swarm commits, merges, marks done, deletes branch/worktree before neutral approval | Stop at immutable `candidate_ready`; review, integrate, verify, and clean up separately | High |
| Desktop is release-ready | Rust tests pass, but frontend build/import graph is broken and desktop CI/signing/updater evidence is absent | Make the capability matrix reflect build and packaging reality before adding features | High |
| Protocol state is reliable | OSC parsing is not stream-safe; background orchestration catches and discards broad exceptions | Incremental bounded parsers and durable surfaced failure events | High |

### Proposed tmux architecture versus platform constraints

1. **tmux is not cross-platform.** It is a Unix-family engine, not a native Windows backend. Voss must retain direct PTY/ConPTY on Windows or adopt a second mux later. A missing tmux binary must degrade cleanly. [tmux repository](https://github.com/tmux/tmux)
2. **tmux survives GUI exit, not reboot.** Reboot resurrection is a declarative relaunch with explicit confirmation; it cannot be marketed as live process continuation.
3. **Control Mode is a protocol, not a renderer.** Voss still owns incremental parsing, input encoding, terminal emulation, state rehydration, backpressure, focus, mouse, clipboard, and accessibility. `%pause` explicitly requires the client to repair state, commonly with `capture-pane`. [tmux Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)
4. **The proposed one-to-one grid mapping conflicts with mixed UI panes.** tmux windows are tiled terminal panes that fill a cell grid. iTerm2 documents that a tmux window cannot freely mix tmux and non-tmux splits and can leave empty regions because GUI divider pixels do not map exactly to cells. [iTerm2 tmux integration](https://iterm2.com/documentation-tmux-integration.html)
5. **Multi-client resizing is shared state.** A tmux window's size is derived from attached clients (`smallest`, `largest`, `latest`, or `manual`). An external terminal attach can resize or viewport-crop the ADE unless Voss defines a policy. [tmux Advanced Use](https://github.com/tmux/tmux/wiki/Advanced-Use)
6. **A private socket is not a sandbox.** Anyone with socket access is fully trusted and can control every process in that server. Read-only flags are convenience, not a security boundary. [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)
7. **Terminal fidelity changes inside tmux.** `$TERM`, terminfo, clipboard, bells, graphics, and passthrough need explicit testing. tmux warns that passthrough state can be undone; SIXEL is not reliably retained across redraw. [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html), [tmux passthrough FAQ](https://github.com/tmux/tmux/wiki/FAQ/d80f82c4c36182ffbc73051c260e33a613a3609d), [tmux SIXEL issue](https://github.com/tmux/tmux/issues/1613)
8. **Agent TUIs expose real mux regressions.** A Codex issue reports Enter becoming unusable after a turn inside tmux, and Zed notes that bells require tmux passthrough. These do not prove tmux is unsuitable; they define required compatibility tests. [Codex tmux input issue](https://github.com/openai/codex/issues/12645), [Zed Terminal Threads](https://zed.dev/docs/ai/terminal-threads)
9. **Environment freshness is subtle.** tmux copies an environment when the server starts and merges session/global environments for new processes; selected variables update on attach. Voss must construct each launch environment explicitly rather than trust a long-lived server snapshot. [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)
10. **Using a private minimal config and respecting the user's tmux are competing goals.** A Voss-owned socket/config improves determinism; attaching the user's existing server preserves habits/plugins. These must be separate modes with separate support promises.

### Recommended topology resolution

Do not force every visual Voss pane into tmux topology. Introduce a **Terminal Group**:

- Workspace -> Voss workspace identity and local app-data record.
- Terminal Group -> one tmux session/window topology rendered by the terminal grid.
- Terminal leaf -> tmux pane with stable `%pane_id`.
- Review, Orchestra, board, browser, editor, and protocol views -> app surfaces beside or above the terminal group, not fake tmux panes.
- Direct-PTY leaf -> supported fallback with an explicit `ephemeral` capability.

Before committing, prototype two mappings:

1. One tmux window with multiple tmux panes per terminal tab: native topology and attach semantics, but stricter geometry/mixed-pane rules.
2. One tmux window per Voss terminal leaf: arbitrary GUI composition, but native tmux users see windows rather than the ADE split layout.

Choose using fidelity and recovery tests, not aesthetics. The first should be preferred only if the product keeps non-terminal surfaces outside the tmux grid.

## Market Differentiation

The market has converged on panes, worktrees, status dots, diff review, and multi-agent launchers. Those are table stakes, not a defensible identity.

Voss can own a less crowded intersection:

| Market category | Typical strength | Typical weakness | Voss position |
|---|---|---|---|
| AI terminal/platform | Polished agent and cloud workflow | Native-agent gravity, account/credit coupling | Better ordinary terminal and existing-CLI contract |
| Native agent workspace | Visible panes, status, review | Direct PTYs die with app; shallow governance | True tmux continuity plus optional evidence/governance |
| tmux/worktree TUI | Durable, composable, open | Limited review/audit/organization model | GUI supervision without hiding real tmux sessions |
| Agent protocol editor | Structured events and review | Editor-first; protocol adoption required for richness | Raw terminal baseline plus optional ACP/Voss promotion |
| Swarm console | Roles, delegation, mission graph | Proprietary runtime and prompt-persona authority | Attach governance to user-owned CLIs and worktrees |

The clearest positioning sentence is:

> **Use Voss as your terminal even if you never use Voss orchestration. When parallel work needs structure, attach the panes you already have and open Orchestra.**

The proof is behavioral: closing Orchestra changes nothing about terminal availability, CLI credentials, tmux sessions, branches, or the neutral review flow.

## Features to Copy, Adapt, and Reject

### Copy directly

- Next-waiting/next-failed navigation and a quiet attention queue.
- Raw user commands and plain shell panes as first-class launch targets.
- Git-native diff review that observes changes regardless of agent identity.
- Worktree creation hooks, port allocation, keep/close/remove separation, and PR handoff.
- tmux-backed detach/reattach with stable pane identity.
- Structured run/task/candidate/check IDs and an inspectable event ledger.
- Read-only pane context as the default MCP capability.
- Explicit source labels: observed, reported, inferred, claimed, verified.

### Adapt carefully

- Warp's third-party toolbelt -> capability-driven per-pane controls, including custom/wrapped commands.
- BridgeSpace's mission tree -> Voss task/run graph with enforceable ownership and evidence links.
- Paneflow's Conductor -> Voss control API, with send/write privileges separate from read privileges.
- workmux/dmux one-command lifecycle -> composable actions with safe presets, never an irreversible black box.
- Zed's three harness types -> Voss integration levels: raw terminal, observed adapter/ACP, Voss managed.
- Codemux execution personas -> per-launch human/agent policy without assuming every named CLI is trusted or autonomous.

### Reject

- Pane-count or swarm-count targets as product goals.
- Universal agent argv construction.
- Status inference from recent text presented without provenance.
- Repo-local memory/config created by opening a terminal.
- Mandatory sign-in, telemetry, model routing, or Voss sidecar for terminal use.
- Automatic merge and cleanup on agent exit or self-reported completion.
- Controls that do not have a scoped runtime command and acknowledgement.
- Claims that layout restore or CLI conversation resume equals process persistence.
- A second full IDE/editor roadmap before terminal, worktree, review, and recovery are trustworthy.

## Prioritized Product Plan

### P0: Make current claims true

1. Remove Voss env injection and repo-local writes from terminal-only panes.
2. Make arbitrary command plus explicit argv/env/cwd the universal launch model; wire per-pane shell selection.
3. Fix workspace binding, lifecycle identifiers, placement behavior, and missing/open controls.
4. Repair the frontend dependency/build boundary and add desktop CI before broadening scope.
5. Replace the OSC extractor with a streaming parser and surface orchestration failures.

**Exit gate:** A clean workspace can use the app for a full day without creating `.voss`, starting a sidecar, changing CLI config, or losing lifecycle truth.

### P1: Build the terminal engine

1. Introduce `SessionEngine` with explicit capabilities and tmux/direct backends.
2. Run a Control Mode go/no-go spike covering fragmented frames, alternate screen, Unicode/IME, mouse, focus, clipboard, OSC, Kitty keyboard, image protocols, large paste, high output, pause/rehydration, crash, and reattach.
3. Use a Voss-owned socket namespace and deterministic config by default; add existing-tmux attach as an explicit advanced mode.
4. Persist stable tmux server/session/window/pane IDs in app data and reconcile on startup.
5. Keep Windows/direct PTY visibly supported as `ephemeral` until a durable native backend exists.

**Exit gate:** Kill the renderer and desktop process during an active TUI, shell job, test watcher, and high-output agent; reopen and reattach without restarting the child or corrupting terminal state.

### P2: Complete the neutral daily workflow

1. Add optional task worktrees with setup, secrets policy, ports, base/head identity, and cleanup state.
2. Add honest attention/status provenance and next-attention navigation.
3. Add Git-native candidate review, saved verification commands, SHA-bound logs/artifacts, PR/local integration, and post-fan-in verification.
4. Store runtime state in platform app data; reserve `.voss` for explicitly shareable Voss project data.

**Exit gate:** A user can go terminal -> worktree -> arbitrary CLI -> attention -> diff -> checks -> PR/merge -> cleanup without enabling Voss.

### P3: Add progressive interoperability

1. Versioned adapter manifests for detection, argv, hooks, resume, status events, and cleanup.
2. Manual `Attach as agent` for wrappers and unknown commands.
3. ACP client support behind capability negotiation; raw terminal remains available for the same agent.
4. Read-only pane/worktree/check MCP server with bounded output and untrusted-data marking.

**Exit gate:** Removing every adapter still leaves a complete terminal/worktree/review product; adapter failure degrades to a raw pane, not a broken session.

### P4: Attach optional Voss orchestration

1. `Attach to Voss` enrolls selected panes/candidates without restarting them where technically possible.
2. Orchestra consumes the neutral session, task, candidate, worktree, check, and event identities.
3. Add roles, scope, budgets, approvals, Reviewer A/B, audit, replay, and targeted messages as optional providers.
4. End external CLI work at `candidate_ready`; never merge from the worker runtime.
5. `Detach from Voss` removes policy/observation while preserving tmux processes, branches, worktrees, and neutral review.

**Exit gate:** The same pane can move terminal-only -> observed -> Voss-managed -> terminal-only without credential migration, CLI replacement, process restart, or data loss.

### P5: Remote and team operation

1. Remote tmux over SSH with capability negotiation and explicit installation ownership.
2. Headless control API using the same identities/events as the desktop.
3. Remote checks, repository-provider status, and team approvals without treating Voss as the final merge authority.

## Unresolved Risks and Required Spikes

| Risk | Decision needed | Validation | Confidence |
|---|---|---|---|
| Control Mode rehydration cannot reproduce arbitrary TUIs faithfully | Go/no-go for full native pane rendering | Differential test against normal tmux client across representative TUIs | Medium |
| tmux topology conflicts with mixed app surfaces | Terminal Group versus one-window-per-leaf mapping | Prototype both and test external attach/resize | High |
| Writable external tmux clients disturb size/focus | Support policy for simultaneous clients | Multi-client test across sizes and active panes | High |
| Windows lacks tmux | Product promise for persistence on Windows | Direct PTY capability labeling; evaluate Zellij/psmux separately | High |
| Hook and CLI versions drift | Adapter update and compatibility policy | Version matrix plus unknown/fallback states | High |
| Cross-pane output becomes prompt injection | Context security boundary | Read-only MCP, output labeling, redaction, explicit enrollment | High |
| Voss attach cannot control an arbitrary live CLI semantically | Minimum useful external-worker contract | Prove task/worktree/evidence attachment without message interception | High |
| tmux socket exposes all sessions to same-user processes | Security posture | Private permissions, disclosure, optional per-workspace servers | High |
| Worktrees multiply ports, secrets, caches, and disk | Setup/cleanup contract | Real monorepo, Docker, mobile, and multi-repo trials | High |
| Orchestration UI again dominates the product | Surface hierarchy and default state | Terminal-only usability study and telemetry-free acceptance test | Medium |

## Final Product Test

The design is correct only if all statements below are simultaneously true:

- A user who never enables Voss gets a credible terminal, tmux persistence, worktrees, attention, review, and integration.
- An unknown internal CLI works without an adapter and without incorrect flags.
- Closing or disabling Voss orchestration does not stop, rewrite, or orphan terminal sessions.
- Richer integrations add capabilities without taking ownership of provider auth/config.
- Every status and gate exposes its provenance; self-reported completion is not verification.
- A Voss-managed run produces more coordination, evidence, budget control, and auditability than a generic pane dashboard.
- The app never claims process persistence where it only has layout restoration or CLI-native conversation resume.

## Source Register

### Terminal substrate and constraints

1. [tmux repository](https://github.com/tmux/tmux)
2. [tmux Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)
3. [tmux Advanced Use](https://github.com/tmux/tmux/wiki/Advanced-Use)
4. [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)
5. [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)
6. [iTerm2 tmux integration](https://iterm2.com/documentation-tmux-integration.html)
7. [tmux passthrough FAQ revision](https://github.com/tmux/tmux/wiki/FAQ/d80f82c4c36182ffbc73051c260e33a613a3609d)
8. [tmux SIXEL issue](https://github.com/tmux/tmux/issues/1613)
9. [Codex tmux input issue](https://github.com/openai/codex/issues/12645)

### Warp and Oz

10. [Warp local agents overview](https://docs.warp.dev/agent-platform/local-agents/overview)
11. [Warp third-party CLI agents](https://docs.warp.dev/agent-platform/cli-agents/overview/)
12. [Warp Full Terminal Use](https://docs.warp.dev/agent-platform/capabilities/full-terminal-use)
13. [Warp Code Review](https://docs.warp.dev/code/code-review)
14. [Warp Interactive Code Review](https://docs.warp.dev/agent-platform/local-agents/interactive-code-review)
15. [Warp session restoration](https://docs.warp.dev/terminal/sessions/session-restoration)
16. [Warp privacy](https://docs.warp.dev/support-and-community/privacy-and-security/privacy)
17. [Warp known issues](https://docs.warp.dev/support-and-community/troubleshooting-and-support/known-issues)
18. [Warp Oz CLI](https://docs.warp.dev/reference/cli)
19. [Warp Oz web app](https://docs.warp.dev/agent-platform/cloud-agents/oz-web-app)
20. [Warp roadmap issue](https://github.com/warpdotdev/warp/issues/9233)

### BridgeMind

21. [BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace)
22. [BridgeSpace product](https://www.bridgemind.ai/products/bridgespace)
23. [BridgeSpace simulated demo](https://www.bridgemind.ai/products/bridgespace/demo)
24. [BridgeSpace changelog](https://www.bridgemind.ai/changelog)
25. [BridgeSwarm product](https://www.bridgemind.ai/bridgeswarm)
26. [BridgeMind pricing](https://www.bridgemind.ai/pricing)

### Local-first agent workspaces and tmux tools

27. [Paneflow docs](https://paneflow.dev/docs)
28. [Paneflow repository](https://github.com/arthjean/paneflow)
29. [Paneflow Review](https://paneflow.dev/docs/review)
30. [Paneflow versus tmux](https://paneflow.dev/compare/tmux)
31. [dmux repository](https://github.com/standardagents/dmux)
32. [dmux documentation](https://dmux.ai/)
33. [dmux issues](https://github.com/standardagents/dmux/issues)
34. [workmux repository](https://github.com/raine/workmux)
35. [workmux changelog](https://github.com/raine/workmux/blob/main/CHANGELOG.md)
36. [workmux issues](https://github.com/raine/workmux/issues)
37. [Flowmux repository](https://github.com/grouzen/flowmux)

### Codemux, Zed, and open protocols

38. [Codemux product](https://codemux.org/)
39. [Codemux repository](https://github.com/Zeus-Deus/codemux)
40. [Codemux issues](https://github.com/Zeus-Deus/codemux/issues)
41. [Codemux OpenFlow](https://docs.codemux.org/openflow)
42. [Codemux agent status](https://docs.codemux.org/agent-status)
43. [Codemux display isolation](https://docs.codemux.org/display-isolation)
44. [Zed Agents](https://zed.dev/docs/ai/agents)
45. [Zed External Agents](https://zed.dev/docs/ai/external-agents)
46. [Zed Terminal Threads](https://zed.dev/docs/ai/terminal-threads)
47. [Zed Parallel Agents](https://zed.dev/docs/ai/parallel-agents)
48. [Zed Git worktrees](https://zed.dev/docs/git)
49. [ACP introduction](https://agentclientprotocol.com/get-started/introduction)
50. [ACP architecture](https://agentclientprotocol.com/get-started/architecture)
51. [ACP transports](https://agentclientprotocol.com/protocol/v1/transports)
52. [ACP schema](https://agentclientprotocol.com/protocol/v1/schema)
53. [ACP v2 proposal](https://agentclientprotocol.com/rfds/v2/overview)

## Confidence Summary

- **High confidence:** local Voss contradictions, tmux lifecycle/security/layout constraints, Paneflow's direct-PTY boundary, Warp's documented third-party feature matrix, Zed's three integration paths, and the operational edge cases evidenced by public changelogs/issues.
- **Medium confidence:** exact BridgeSpace runtime authority, Codemux detached PTY behavior, and real-world maturity of recent small projects. These are specific vendor or repository claims without hands-on reproduction.
- **Low confidence and excluded from central decisions:** claimed agent-count scalability, independent performance comparisons, vendor benchmarks, and isolated social-media quality claims.
