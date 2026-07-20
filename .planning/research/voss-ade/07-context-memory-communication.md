# Voss ADE Deep Research 07: Context, Memory, and Inter-Agent Communication

**Research date:** 2026-07-19  
**Scope:** Terminal-first agent environments; Warp Drive/context, BridgeMemory/BridgeSwarm, Paneflow pane context, ACP, MCP, agent-team mailboxes/task graphs, context security, and provenance  
**Product constraint:** Existing shells and CLI agents must remain first-class. Voss context and orchestration are optional capabilities, never prerequisites.  
**Evidence base:** 31 cited sources, prioritizing protocol specifications, official product documentation, government guidance, and standards bodies. Vendor product claims are treated as lower-confidence evidence than specifications or source-visible behavior.

## Executive Findings

1. **"Context" is not one store.** A credible terminal-first ADE needs at least four independently scoped lifecycles: ephemeral terminal/session context, durable project knowledge, private user memory, and durable orchestration/audit state. Combining them creates accidental disclosure, stale instructions, repository pollution, and unclear deletion semantics.

2. **The correct default for arbitrary CLI agents is observation, not injection.** Paneflow's read-only MCP pane tools are the best current pattern: agents can list panes and inspect bounded scrollback, but cannot type into other panes. A raw shell or unknown CLI must work without Voss environment variables, MCP configuration, prompt rewriting, or a Voss account. [Paneflow](https://paneflow.dev/) explicitly preserves each agent's own account, model, API, and network path. [Paneflow's getting-started guide](https://paneflow.dev/docs) also says unknown CLIs remain normal terminal panes.

3. **MCP is useful as an optional context interface, not as the internal source of truth.** MCP distinguishes application-controlled, normally read-only resources from model-controlled tools. Voss should expose terminal observations and curated knowledge as resources; every state-changing operation should be a separately permissioned tool. [MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts) describe exactly this control split, while the [MCP resources specification](https://modelcontextprotocol.io/specification/2025-06-18/server/resources) leaves context selection to the host application.

4. **ACP is the strongest emerging client-agent session interface, but it cannot replace PTY compatibility.** ACP provides capability negotiation, session create/load/resume/close, structured messages, plans, tool calls, usage, and metadata updates. However, an existing TUI agent only benefits if it implements ACP or an opt-in adapter can translate without breaking its native behavior. [ACP's introduction](https://agentclientprotocol.com/get-started/introduction) frames the protocol as an interoperability layer; it does not make unmodified terminal programs structured agents.

5. **Memory must be reviewable, attributable, and scoped.** BridgeMemory's plain Markdown model is inspectable and portable, and Claude Code's separation of user-authored instructions from agent-authored auto-memory is directionally correct. But "every agent reads and writes the same memory" is too permissive as a default. Each fact needs source, author, scope, timestamp, hash, sensitivity, and derivation metadata, with proposed memories reviewed before promotion into team knowledge.

6. **Communication and durable results are different channels.** Agent mailboxes are useful for coordination, but messages are not a reliable audit record. The A2A specification explicitly separates transient Messages from task Artifacts and warns that not every message is guaranteed to be persisted. Voss should use a durable task/event ledger for commitments and results, with mailboxes only for delivery and conversation. [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md).

7. **Provenance is a product feature, not metadata cleanup.** Every injected context item, message, task transition, approval, tool execution, and artifact should be traceable to an actor and source. W3C PROV's entity/activity/agent model is a sound conceptual base; OpenTelemetry can carry operational traces, but neither should dictate the user-facing storage format. [W3C PROV overview](https://www.w3.org/TR/prov-overview/), [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/).

8. **The orchestration console should consume the same event model without owning terminal sessions.** It can be closed indefinitely while tmux sessions and ordinary CLI agents continue. Enabling the console should add task graphs, mailboxes, memory, approvals, and audit views; disabling it should remove those integrations cleanly without changing shell semantics.

## Research Question

How can a tmux-powered, terminal-first Voss ADE provide useful shared context, memory, and agent coordination while preserving these guarantees?

- A user can run `zsh`, `claude`, `codex`, `gemini`, `opencode`, `aider`, or an unknown binary exactly as they do in another terminal.
- Voss does not require replacement authentication, model selection, provider routing, prompts, or agents.
- Terminal processes and tmux sessions outlive the UI and do not depend on the orchestration service.
- Context access is visible, scoped, revocable, and attributable.
- Voss-native orchestration is available when explicitly enabled, without contaminating the baseline terminal experience.

## The Four Context Lifecycles

Treating all retained information as "memory" is the central design error in this category. The following stores have different owners, trust levels, retention requirements, and sharing rules.

| Layer | Examples | Authority | Default retention | Default sharing | Default agent access |
|---|---|---|---|---|---|
| Ephemeral terminal/session context | Current command, CWD, pane title, bounded scrollback, process state, bell/prompt markers | tmux + terminal observer | Session lifetime; bounded local cache | None | None; read-only when explicitly granted |
| Project knowledge | `AGENTS.md`, architecture decisions, build commands, reviewed handoffs, project glossary | Repository maintainers | Versioned with project or local project DB | Team if committed; otherwise local | Read/search; write only through proposal/review |
| User memory | Personal preferences, tool habits, private notes, corrections | User | Until deleted by user | Never by default | Current user's selected agents only |
| Orchestration/audit | Task graph, assignments, messages, approvals, runs, tool events, artifacts, verification results | Voss run/workspace ledger | Policy-defined, append-only events | Workspace/run members | Query by capability; mutation through audited commands |

### 1. Ephemeral terminal/session context

This layer answers "what is happening now?" It includes tmux server/session/window/pane identity, attached clients, foreground process, current directory, exit/bell/prompt markers, and a bounded slice of terminal output.

Paneflow exposes the clearest competitive pattern: `list_panes`, `read_pane`, and `search_pane` are read-only MCP tools, so one agent can inspect another pane's test output without gaining keystroke authority. The product explicitly describes the risk reduction as avoiding collisions between agents. [Paneflow product documentation](https://paneflow.dev/).

Voss should improve on this pattern:

- Expose scrollback as a **resource** or explicitly read-only query, not as a write-capable tool.
- Require pane-level grants: `none`, `metadata`, `last-N-lines`, `search`, or `full-scrollback`.
- Treat captured terminal content as **untrusted data**. ANSI-stripped text can still contain prompt injection, secrets, malicious URLs, or output produced by an untrusted repository.
- Default to a bounded ring buffer and never persist full scrollback into project files.
- Make raw bytes available to the terminal renderer, but make normalized text a separate derived representation with its own content hash and provenance.
- Record whether data was user-selected, rule-selected, or automatically selected when it enters an agent context.
- Never write to a pane as a side effect of granting read access.

The terminal layer should remain useful without any agent semantics. Agent status may be `unknown` when the foreground program does not expose hooks; false precision is worse than an honest unknown state.

### 2. Project knowledge

Project knowledge is shared, reviewable context: build commands, architectural constraints, operational runbooks, decisions, and stable handoffs. Existing tools already create a fragmented but useful convention set:

- Warp recognizes root and nested `AGENTS.md` files, with more specific project rules taking precedence over root and global rules. It also recognizes several vendor-specific rule filenames and can link them to `AGENTS.md`. [Warp Rules](https://docs.warp.dev/agent-platform/capabilities/rules).
- Claude Code uses `CLAUDE.md`, `.claude/rules/`, and an explicit import of `AGENTS.md`. It distinguishes managed, user, project, and local scopes and warns that these files shape behavior but do not enforce security. [Claude Code memory](https://code.claude.com/docs/en/memory).
- BridgeMemory stores project notes as plain Markdown under `.bridgememory/`, uses wikilinks and backlinks, and encourages committing them with code. [BridgeMemory](https://www.bridgemind.ai/blog/bridgememory-persistent-context).
- Warp Drive provides team-shared notebooks, workflows, prompts, rules, and environment-variable definitions, with explicit object sharing and permissions. [Warp Drive](https://docs.warp.dev/knowledge-and-collaboration/warp-drive).

The portable baseline should be the repository's existing files, not a Voss-only knowledge format. Voss can index and present them through a uniform catalog while retaining origin and precedence:

```text
project://<workspace-id>/instructions/AGENTS.md
project://<workspace-id>/instructions/CLAUDE.md
project://<workspace-id>/docs/architecture/auth.md
project://<workspace-id>/decisions/adr-0042
project://<workspace-id>/handoffs/<handoff-id>
```

Recommended rules:

- Do not create `.voss/`, modify `AGENTS.md`, or initialize a knowledge graph merely because a directory was opened in the terminal.
- Offer "Enable project knowledge" as an explicit workspace action with a preview of files and ignore rules.
- Index existing formats before proposing new files.
- Store the local index in application data; store source material in the repository only after explicit creation or adoption.
- Separate **instruction** from **evidence**. An ADR is evidence about a past decision; an `AGENTS.md` rule is intended behavioral guidance; a terminal log is an observation. They should not be flattened into an undifferentiated vector index.
- Preserve precedence and contradiction information. Do not silently blend conflicting rules into a single summary.
- Make writes proposal-based: an agent can draft a memory or documentation patch, but promotion to durable shared knowledge is reviewable like code.

### 3. User memory

User memory is personal and cross-project: preferred tools, interaction style, recurring corrections, and optionally private project notes. It must never be inferred to be team-shared merely because the current directory is a Git repository.

Claude Code offers a useful scope model: auto-memory is machine-local, stored outside the repository under the user's home directory, shared across worktrees of the same repository, inspectable as Markdown, and independently disableable. Only a bounded index is loaded automatically; detailed notes are read on demand. [Claude Code memory](https://code.claude.com/docs/en/memory).

Warp's personal Drive offers a different tradeoff: saved objects sync across devices and can be moved into team scope. Its documentation notes that moving an object into a team workspace shares it with all members and cannot currently be reversed by moving it back; the user must recreate and delete it. [Warp Drive sharing](https://docs.warp.dev/knowledge-and-collaboration/warp-drive). This is a warning for Voss: scope transitions must be explicit, reversible where possible, and logged.

Voss user memory should therefore be:

- Off by default for terminal-only users.
- Stored outside repositories in platform application data.
- Encrypted at rest when it contains personal or sensitive material.
- Inspectable, editable, exportable, and deletable by the user.
- Partitioned by global, organization, repository, and worktree applicability.
- Never automatically exposed to a third-party CLI. Exposure requires a compatible integration and an explicit per-agent or per-profile grant.
- Loaded by retrieval and relevance rather than wholesale startup injection.
- Written as a candidate with provenance, not silently promoted from a model's output.

### 4. Durable orchestration and audit

This layer answers "what did the team intend, do, approve, and produce?" It should survive terminal detach, UI restart, agent replacement, and task reassignment.

The minimum durable model includes:

- Organizations/workspaces/runs
- Actors: user, external CLI process, ACP agent, Voss-native agent, service, hook
- Sessions and tmux pane bindings
- Tasks and dependency edges
- Assignments/claims/leases
- Mailbox messages and acknowledgements
- Permission requests and decisions
- Tool/command observations
- Artifacts and verification results
- State transitions and failure reasons
- Context selections and memory promotions

Claude Code's agent-team architecture validates the usefulness of a shared task list, direct inter-agent messages, task dependencies, self-claiming, file locking, and idle notifications. It also documents important failure modes: task status can lag, shutdown can be slow, in-process teammate sessions do not reliably resume, and the fixed lead can terminate too early. [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams). Voss should treat those as design requirements, not edge cases.

The A2A specification provides a valuable separation:

- `Message` is communication.
- `Task` has a lifecycle.
- `Artifact` is durable output.
- A `contextId` groups related tasks/messages.
- Streaming or push notification is delivery, not storage.
- Critical information must not rely on transient messages because histories may be incomplete.

This distinction is directly applicable even if Voss does not implement A2A in the first release. [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md).

## Product and Standards Findings

### Warp Drive and Warp agent context

Warp combines several kinds of knowledge in Warp Drive: workflows, notebooks, prompts, rules, environment variables, plans, and MCP servers. Objects may be personal or team-shared, sync between clients, and have view/edit/full-access permissions. [Warp Drive](https://docs.warp.dev/knowledge-and-collaboration/warp-drive).

Warp Agent Mode can automatically retrieve relevant Drive objects, rules, MCP servers, and environment-variable context. It displays used items as "References" or "Derived from" and permits disabling the feature in settings. [Warp Agent Mode Context](https://docs.warp.dev/knowledge-and-collaboration/warp-drive/agent-mode-context). Direct `@` selection can attach files, symbols, folders, and blocks from other sessions. [Warp context selection](https://docs.warp.dev/agent-platform/local-agents/agent-context/using-to-add-context).

**What Voss should adopt:**

- Personal/team scope visible at the object level.
- Explicit references attached to generated responses.
- Direct context picker for files, pane output, tasks, artifacts, and memories.
- Reusable context objects that can be invoked from the terminal or console.
- A single switch to disable every Voss context integration.

**What Voss should not copy:**

- Automatic retrieval enabled by default for users who only wanted a terminal.
- Mixing environment variables with general knowledge in one automatic retrieval pool. Warp's own documentation says static Drive variables are not a secret-manager replacement and recommends dynamic secret retrieval. [Warp environment variables](https://docs.warp.dev/knowledge-and-collaboration/warp-drive/environment-variables).
- Cloud sync as the only durable store. Local-only and Git-versioned scopes are both necessary.
- Assuming "Derived from" is sufficient provenance. It identifies a source to the user but does not establish content hashes, derivation steps, redaction, or actor responsibility.

Warp provides meaningful privacy controls, including disabling AI globally, secret redaction, and enterprise zero-data-retention agreements. Its Free plan requires telemetry to use AI, while paid plans can opt out. [Warp privacy and data control](https://docs.warp.dev/support-and-community/privacy-and-security/privacy/). Voss should avoid coupling basic local context functionality to telemetry or account status.

### BridgeMemory, BridgeMCP, and BridgeSwarm

BridgeMemory is the most concrete competitor model for repository-local shared memory. BridgeMind says it uses plain Markdown under `.bridgememory/`, discovers the folder from subdirectories, supports wikilinks/backlinks and MCP tools, uses atomic rename and append patterns, and guards its local MCP launch with a token stored mode `0600`. [BridgeMemory design](https://www.bridgemind.ai/blog/bridgememory-persistent-context).

BridgeSpace positions this memory as shared by every agent, while BridgeSwarm uses a coordinator/builder/scout/reviewer role tree and a shared mailbox. [BridgeSpace product](https://www.bridgemind.ai/products/bridgespace). BridgeMCP exposes project/task/agent configuration across MCP-compatible clients with API-key authentication and a four-state task lifecycle. [BridgeMCP docs](https://docs.bridgemind.ai/docs/mcp).

**What Voss should adopt:**

- Plain-text, inspectable knowledge sources.
- Backlinks and graph exploration as a view, not as the storage contract.
- Atomic concurrent writes.
- Cross-agent access through an open protocol.
- Shared task state that is visible from different agent clients.
- Role-aware mailbox routing.

**What Voss should improve:**

- Separate `read`, `search`, `propose`, `append`, `edit`, and `delete` capabilities. "Every agent reads and writes" is unsafe for durable team knowledge.
- Keep local indexes and session notes out of the repository by default. A committed memory directory should be an explicit team choice.
- Distinguish local BridgeMemory-style storage from cloud BridgeMCP-style task services in the UI and consent flow.
- Show whether a result came from local files, remote project/task APIs, or an agent-authored synthesis.
- Do not require a paid memory service for portable project context.

**Evidence caveat:** Most BridgeMemory and BridgeSwarm evidence is first-party product copy. Claims about atomicity, token comparison, scale, and cross-client behavior lack an independent conformance suite in the reviewed material. BridgeSpace's changelog documents a rollback to a previous terminal implementation after rendering and PATH regressions, which is useful evidence that terminal reliability remains difficult even in a shipping competitor. [BridgeSpace changelog](https://www.bridgemind.ai/changelog).

### Paneflow pane context

Paneflow's design aligns most closely with the user's non-displacement requirement:

- Existing and unknown CLIs run as ordinary processes.
- No sign-in, hosted runtime, or Paneflow API key is required.
- Supported agents get richer state through hooks or shims.
- Cross-pane MCP is read-only.
- Workspaces preserve panes, branch, diff, servers, and agent session references.

[Paneflow getting started](https://paneflow.dev/docs), [Paneflow product overview](https://paneflow.dev/).

**Voss implication:** Build the context feature as a local observer and resource server first. A Voss-native agent can receive richer structured updates, but arbitrary agents should never lose terminal fidelity or be mislabeled when an adapter is absent.

### Agent Client Protocol

ACP standardizes client-to-agent communication using JSON-RPC and reuses MCP content types where possible. Its stated goals include UX clarity, low abstraction overhead, and interoperability between agents and editors. [ACP architecture](https://agentclientprotocol.com/get-started/architecture).

Important current primitives:

- `initialize` negotiates client and agent capabilities.
- `session/new` binds a conversation to an absolute `cwd` and optional MCP servers.
- `session/load` replays history as `session/update` notifications.
- `session/resume` reconnects without replaying history.
- `session/close` cancels work and releases active resources.
- Additional directories expand the effective filesystem root only when explicitly supported.
- `session/prompt` carries typed content blocks.
- `session/update` streams messages, thoughts, plans, tool calls, modes, commands, and session metadata.

[ACP session setup](https://agentclientprotocol.com/protocol/v1/session-setup), [ACP prompt turn](https://agentclientprotocol.com/protocol/v1/prompt-turn), [ACP initialization](https://agentclientprotocol.com/protocol/v1/initialization).

The stabilized session metadata update lets agents push titles and metadata without polling. [ACP Session Info Update](https://agentclientprotocol.com/rfds/session-info-update). The usage/context-window proposal is useful but should be treated carefully because RFD maturity can differ from the stable v1 schema. [ACP Session Usage and Context Status](https://agentclientprotocol.com/rfds/session-usage).

**Voss target:**

- Implement an ACP client as one optional pane backend alongside raw PTY panes, not as the universal terminal engine.
- Preserve agent-owned session IDs separately from tmux pane IDs and Voss run IDs.
- Store capabilities per session; never assume load, resume, filesystem, MCP transport, usage, or metadata support.
- Render structured plans/tool calls when present and retain the native terminal/TUI when the agent prefers it.
- Make ACP-provided state explicitly labeled `reported-by-agent`; corroborate observable process state separately.
- Never invent structured history from scraped terminal output and claim ACP-level fidelity.

ACP's current session model is client-agent, not a complete multi-agent team/mailbox protocol. Voss still needs its own durable coordination model, or a future A2A bridge, above individual ACP sessions.

### Model Context Protocol

MCP provides three relevant interfaces:

- **Resources:** application-selected, generally read-only context with URIs, MIME types, annotations, discovery, and optional subscriptions.
- **Tools:** model-discovered actions with typed schemas and possible side effects.
- **Prompts:** user-invoked templates.

[MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts), [MCP resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources), [MCP tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

MCP roots let a client communicate intended filesystem boundaries, but the specification notes that roots are coordination information, not a security boundary. [MCP roots](https://modelcontextprotocol.io/specification/2025-06-18/client/roots). Voss must enforce filesystem and pane access in its own process boundary regardless of advertised roots.

Recommended Voss MCP surface:

```text
Resources (safe default)
  voss-pane://<workspace>/<tmux-pane>/metadata
  voss-pane://<workspace>/<tmux-pane>/scrollback?tail=200
  voss-project://<workspace>/knowledge/<item-id>
  voss-run://<run-id>/tasks/<task-id>
  voss-run://<run-id>/artifacts/<artifact-id>

Tools (explicit grants)
  search_pane_output
  propose_project_memory
  send_mailbox_message
  claim_task
  update_task
  attach_artifact
  request_permission
```

Do not expose `type_into_pane`, `run_command`, or unrestricted filesystem writes in the read-only context server. If later added, they belong in a separate action server/profile with conspicuous approval and audit.

### Agent teams, mailboxes, and task graphs

Claude Code's agent teams offer a real-world implementation of:

- A lead plus independently contexted teammates.
- Direct messages and automatic delivery.
- A shared task list with pending/in-progress/completed states.
- Dependency edges and automatic unblocking.
- Assignment or self-claim with file locking.
- Idle notifications and lifecycle cleanup.
- tmux/iTerm split-pane visualization.

[Claude Code agent teams](https://code.claude.com/docs/en/agent-teams).

The limitations are equally important:

- Team coordination costs more tokens.
- Task state may lag reality.
- Resuming can leave references to nonexistent teammates.
- Shutdown and cleanup can stall or orphan tmux sessions.
- A fixed lead is a single coordination dependency.
- Messages and task state are stored in product-specific local paths.

Voss should therefore use leases and observed state:

- A task claim has `claimed_by`, `lease_expires_at`, and a renewal heartbeat.
- `in_progress` is a ledger state, not proof that a process is alive.
- Pane/process state and task state are shown separately when they disagree.
- Completion requires an explicit result or verification artifact, not just agent idleness.
- Leads/coordinators are roles, not permanent ownership; the user can reassign them.
- Mailbox delivery is at-least-once with message IDs and idempotent acknowledgement.
- A dead session can be replaced without rewriting task history.

The A2A task model is a useful future interoperability boundary for remote or heterogeneous orchestrators. It supports stateful tasks, messages, artifacts, polling, streaming, subscriptions, push notifications, and capability discovery. It also makes the correct warning: transient messages are not guaranteed durable. [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md), [A2A task lifecycle](https://a2aproject.github.io/A2A/latest/topics/life-of-a-task/).

## Voss Target Model

### Architectural principle: context is a brokered capability

Voss should own a **Context Broker**, not a universal agent memory. The broker inventories sources, evaluates access policy, records provenance, and serves bounded context to compatible consumers. It does not modify the user's shell or agent configuration until the user opts in.

```text
tmux server / ordinary CLI processes
           |
           | observation only
           v
Terminal Observer -----> Context Catalog <----- Project Indexer
                              |                       |
                              |                       +-- AGENTS.md/docs/ADRs
                              |
                    Policy + Provenance
                     /        |        \
                    /         |         \
          MCP resources    ACP client    Voss REST/SSE
          (optional)        (optional)    (optional)
                    \         |         /
                     \        |        /
                      Orchestration Ledger
                      (only when enabled)
```

The Context Broker must not be the tmux session owner. If it exits, terminal processes remain alive. If Voss orchestration is never enabled, the catalog can remain a small local observer or be disabled entirely.

### Progressive integration levels

| Level | User experience | Context behavior | Voss dependency |
|---|---|---|---|
| 0. Raw terminal | Any shell/CLI in tmux | No injection, no indexing, no Voss env | None |
| 1. Observed terminal | Optional CWD/process/bell/prompt status | Local metadata only | Local observer |
| 2. Context-enabled CLI | User configures read-only MCP or adapter | Selected pane/project resources | Optional local broker |
| 3. Structured agent | Agent supports ACP or a trustworthy adapter | Plans, messages, tool calls, resume, context metadata | Optional agent client |
| 4. Voss orchestration | User opens/enables console or starts a Voss run | Tasks, mailbox, memory proposals, approvals, audit | Voss sidecar/service |

Moving upward must be explicit and reversible. Closing the console does not move panes downward or terminate processes. A workspace can contain different levels simultaneously.

### Canonical identities

Do not overload a single `session_id`. Maintain explicit mappings:

```text
workspace_id       Voss ADE local workspace
tmux_server_id     tmux socket/server namespace
tmux_session_id    durable tmux session
tmux_pane_id       terminal process surface
agent_process_id   observed foreground/child process instance
agent_session_id   vendor/ACP conversation identity, if available
voss_run_id        optional orchestration run
task_id            durable work item
actor_id           user, agent, service, or hook
```

Mappings are versioned events. A task can move to a new pane or agent session without losing identity; a pane can host multiple sequential agent processes without inheriting old permissions.

### Context item envelope

Every item entering an agent context should have a durable envelope even if the content itself is ephemeral:

```json
{
  "id": "ctx_...",
  "uri": "voss-pane://ws_123/%7Bpane-id%7D/scrollback?tail=200",
  "kind": "terminal_observation",
  "scope": "session",
  "source_actor_id": "process_...",
  "captured_by": "voss-terminal-observer",
  "workspace_id": "ws_123",
  "pane_id": "%7Bpane-id%7D",
  "task_id": null,
  "content_hash": "sha256:...",
  "captured_at": "2026-07-19T...Z",
  "trust": "untrusted_observation",
  "sensitivity": "unknown",
  "selection": "user_explicit",
  "retention": "session",
  "derived_from": [],
  "redactions": []
}
```

W3C PROV supplies the correct conceptual vocabulary: entities are generated or derived by activities, and agents bear responsibility for them. It also emphasizes versioning, derivation, reproducibility, and provenance of provenance. [W3C PROV overview](https://www.w3.org/TR/prov-overview/). Voss does not need RDF in its local database, but it should retain enough structure to export or map to this model.

### Context selection UX

Every structured agent prompt or orchestration dispatch should expose a compact context receipt:

```text
Context attached (4)
  [user]  src/auth/session.ts lines 20-190
  [user]  pane test-runner, last 120 lines
  [rule]  AGENTS.md (project root)
  [auto]  task T-142 acceptance criteria
```

The user can inspect, remove, pin, or change scope before sending. Afterward, the event ledger records which content hashes were actually supplied. Warp's "References" and "Derived from" UI demonstrates the value of visible source attribution, but Voss should add selection reason, trust, and exact version. [Warp Agent Mode Context](https://docs.warp.dev/knowledge-and-collaboration/warp-drive/agent-mode-context).

Automatic selection should be conservative:

- Allowed only for a context-enabled agent profile.
- Limited by source kind, workspace, sensitivity, and token budget.
- Never include another pane's output unless cross-pane access was granted.
- Never include personal memory in a team or remote agent by inheritance.
- Never include environment-variable values as semantic context.
- Prefer summaries with links, but retain hashes and source ranges so the summary can be challenged.

### Memory promotion workflow

Use a staged state machine instead of unrestricted shared writes:

```text
observation -> candidate -> reviewed -> active -> superseded/archived
```

- **Observation:** raw session fact, terminal excerpt, tool result, or user statement.
- **Candidate:** agent/user proposes a durable learning, with sources and target scope.
- **Reviewed:** accepted by the user or an authorized reviewer.
- **Active:** discoverable as project or user memory.
- **Superseded/archived:** retained for provenance but not automatically retrieved.

The UI should support diffing a candidate against existing memories and detecting contradictions. A memory without provenance or an owner should not become active automatically.

### Mailbox semantics

A Voss mailbox should be an addressable delivery mechanism:

```json
{
  "message_id": "msg_...",
  "run_id": "run_...",
  "from_actor": "agent_reviewer",
  "to": ["agent_builder"],
  "kind": "finding",
  "task_id": "task_...",
  "reply_to": null,
  "body": [{"type": "text", "text": "..."}],
  "artifact_refs": ["artifact_..."],
  "created_at": "...",
  "delivery": "at_least_once",
  "content_hash": "sha256:..."
}
```

Required behavior:

- Immutable message body after send; corrections are new messages referencing the old one.
- Per-recipient delivered/read/acknowledged state.
- Stable IDs for deduplication.
- Direct, role, task, and broadcast addresses.
- Size limits and artifact references rather than large inline logs.
- Backpressure and rate limits.
- No implicit interpretation of a mailbox message as a command.
- No automatic paste into a raw terminal pane. The UI may notify the user and offer to paste or route through a configured adapter.
- Voss-native/ACP agents can receive structured delivery through their supported channels.

This avoids the most dangerous form of "agent interoperability": scraping a third-party agent's terminal, then typing messages into it without its protocol or the user's approval.

### Task graph semantics

Each task should include:

- Stable task ID and parent/run relationships.
- Explicit dependency edges, not ordering inferred from chat.
- Owner/assignee and time-bounded claim lease.
- State plus state reason.
- Acceptance criteria and verification requirements.
- Input context references.
- Artifact outputs.
- Attempt history and replacement agent sessions.
- Human approvals and overrides.

Suggested states:

```text
draft -> ready -> claimed -> running -> blocked|needs_input|review
review -> completed|changes_requested|failed|canceled
```

Do not copy vendor states blindly. The BridgeMCP lifecycle (`todo -> in-progress -> in-review -> complete`) is approachable but too small to represent leases, blocked dependencies, authentication, failure, cancellation, or replacement. [BridgeMCP docs](https://www.bridgemind.ai/docs).

### Audit/event ledger

Store normalized events append-only in a local SQLite database or equivalent durable log. Materialized views can power the console; raw events remain the audit source.

Minimum event fields:

```text
event_id, schema_version, occurred_at, recorded_at
workspace_id, run_id, task_id, pane_id, agent_session_id
actor_id, actor_kind, event_kind
causation_id, correlation_id
payload, payload_hash
source (observed | agent_reported | user_action | service)
sensitivity, redaction_state, retention_policy
```

OpenTelemetry's semantic conventions can export spans and correlate agent/tool operations, but the conventions evolve and telemetry sampling may omit evidence. Use OTel as an export/observability plane, not the canonical local audit log. [OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/), [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/).

Audit capture should default to metadata and hashes. Full prompts, outputs, environment variables, and scrollback can contain secrets and should require an explicit content-retention setting. A verifiable audit trail does not require indiscriminately storing every byte.

## Security and Trust Model

### Context is untrusted, including local context

Local terminal output, repository documentation, issue text, tool descriptions, MCP responses, and agent mailbox messages can all carry adversarial instructions. The NSA's MCP security guidance calls out implicit trust between agents, long-lived or overlapping context leakage, unverified task propagation, and cascading prompt injection through shared context. [NSA MCP Security Design Considerations](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf).

OWASP describes MCP tool poisoning as indirect prompt injection in which apparently normal tool metadata or responses introduce hidden instructions into the model context. [OWASP MCP Tool Poisoning](https://owasp.org/www-community/attacks/MCP_Tool_Poisoning).

Therefore:

- Display source and trust class for context.
- Keep instructions separate from retrieved data in the prompt construction pipeline.
- Sanitize terminal control sequences, but do not claim text sanitization removes semantic prompt injection.
- Apply content and tool policies independently; untrusted text cannot grant a tool capability.
- Inspect and gate outputs before passing them from one agent to another.
- Do not let a project file redirect personal-memory storage or broaden filesystem roots.
- Apply least privilege per session and per MCP server.
- Require reapproval when a server's tool manifest or requested scopes change.

### Authentication is not authorization

MCP security guidance requires audience-bound tokens, prohibits token passthrough, and warns that session IDs must not be used as authentication. [MCP authorization security considerations](https://modelcontextprotocol.io/specification/draft/basic/authorization/security-considerations), [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices).

For Voss:

- Local services bind to loopback or a protected Unix socket.
- Use per-launch, short-lived capabilities rather than a single workspace-wide bearer token.
- Bind grants to user, workspace, session, consumer, resource pattern, operations, and expiry.
- Never pass a third-party provider token through Voss unless Voss is explicitly configured as that provider's client.
- Keep read-only pane context credentials separate from orchestration mutation credentials.
- Revoke grants when a process/session identity changes.
- Treat browser/WebView origins as separate clients with CSRF/origin protections.

### Privacy and retention

Users need independent controls for:

- Terminal scrollback persistence.
- Project indexing.
- Personal memory.
- Orchestration transcripts and audit payloads.
- Remote MCP/context services.
- Telemetry/export.

"Disable AI" should stop context dispatch and Voss model calls without disabling tmux, panes, workspaces, search, or local terminal restoration. Warp documents a global AI toggle, but its Free tier couples AI usage to telemetry; Voss should keep the terminal and local observer fully usable without telemetry. [Warp privacy](https://docs.warp.dev/support-and-community/privacy-and-security/privacy/).

## Anti-Patterns

1. **Injecting Voss environment variables into every shell.** This violates terminal neutrality, contaminates subprocesses, and makes "no Voss" mode dishonest.

2. **Configuring MCP servers for third-party agents without explicit consent.** MCP access changes an agent's tool and trust surface.

3. **Treating scrollback as trusted memory.** Terminal output is ephemeral, incomplete, and adversarially writable.

4. **Automatically persisting full terminal transcripts.** This collects secrets, credentials, proprietary code, and unrelated personal activity.

5. **Writing `.voss/` state merely by opening a repository.** Terminal layout and local indexes belong in application data unless the user explicitly chooses a shareable project configuration.

6. **One vector index for everything.** It erases scope, authority, precedence, contradictions, and retention.

7. **Allowing all agents to edit shared memory.** Agent-authored conclusions need provenance and promotion review.

8. **Using chat as the task database.** Messages can be missed, duplicated, compacted, or not persisted.

9. **Using task state as process truth.** An agent can report "working" while its process is dead, or remain alive after a task is complete.

10. **Typing into arbitrary agent TUIs for coordination.** Screen scraping plus keystroke automation is brittle and can corrupt the user's session.

11. **Inventing common CLI flags or resume semantics.** Agent integrations must be capability- and adapter-specific.

12. **Calling summaries provenance.** A summary without source version, content hash, selection reason, and derivation is not auditable.

13. **Storing secrets in general context objects.** Secret references and secret values require different handling; values should be resolved only into the target process and excluded from memory/retrieval.

14. **Making the console the process supervisor.** Closing or crashing the console must not terminate terminal work.

15. **Equating MCP roots with sandboxing.** Roots communicate intended boundaries; OS enforcement still matters.

## Prioritized Recommendations

### P0: Terminal neutrality and context boundaries

1. Establish and test a hard zero-integration mode: no Voss env, files, services, MCP config, indexing, or network calls for a raw pane.
2. Move terminal/session metadata and indexes to application data by default.
3. Define the canonical identity map for workspace, tmux pane, process, agent session, run, task, and actor.
4. Define the four storage scopes and their retention/deletion behavior before adding more memory UI.
5. Make terminal observations explicitly untrusted and bounded.

**Exit criteria:** A third-party CLI can run, detach, reattach, and exit with byte/behavior parity to tmux; inspecting the workspace shows no Voss-created files unless enabled.

### P1: Read-only context broker

1. Implement a local catalog for pane metadata, bounded scrollback, existing project instruction files, task artifacts, and memory candidates.
2. Add pane-level read grants and a context picker with receipts.
3. Expose an optional read-only MCP server for `list_panes`, `read_pane`, `search_pane`, and project knowledge resources.
4. Add content hashes, source ranges, trust labels, sensitivity, and selection reason.
5. Keep `type_into_pane` and command execution out of this server.

**Exit criteria:** A configured MCP-compatible agent can inspect an explicitly granted test pane, while an unconfigured/unknown CLI sees no Voss changes.

### P2: Durable task/event foundation

1. Create the append-only event ledger and materialized task/run views.
2. Implement tasks with dependencies, leases, acceptance criteria, attempts, artifacts, and verification.
3. Implement mailbox IDs, acknowledgements, idempotency, and artifact references.
4. Surface observed process state separately from reported agent/task state.
5. Make the orchestration console a consumer of this ledger.

**Exit criteria:** The UI can close and reopen while tmux processes continue; task and mailbox history reconstructs deterministically; a dead agent can be replaced without losing task history.

### P3: Structured agent interoperability

1. Add ACP as an optional pane/agent integration with capability negotiation.
2. Store ACP session identity separately and support only declared new/load/resume/close capabilities.
3. Render structured plans, messages, tool calls, permissions, usage, and metadata when provided.
4. Add adapter manifests for non-ACP agents only where stable documented hooks exist.
5. Label adapter-derived state and confidence.

**Exit criteria:** ACP and raw PTY panes coexist in the same workspace; ACP failure degrades to an honest disconnected/terminal state rather than blocking the pane.

### P4: Memory promotion and provenance

1. Implement observation/candidate/reviewed/active/superseded memory states.
2. Index existing `AGENTS.md`, `CLAUDE.md`, rules, docs, and ADRs without rewriting them.
3. Add contradiction detection and source/version display.
4. Add separate private user memory with independent encryption, export, and deletion.
5. Support optional project export in plain Markdown and optional audit export in JSONL/OTel.

**Exit criteria:** Every active memory is attributable and removable; no personal memory crosses into a team/remote agent without an explicit grant.

### P5: Optional Voss-native orchestration

1. Bind Voss runs to existing panes/tasks without assuming ownership of them.
2. Add role/task/broadcast mailboxes and human approvals.
3. Add context budgets and context receipts to dispatch.
4. Add reviewer/verifier artifact requirements.
5. Consider an A2A bridge only after the internal task/artifact semantics are stable.

**Exit criteria:** A user can adopt the console for one run, then return to terminal-only work without migrating their CLI agents, credentials, sessions, or project knowledge.

## Contradictions and Evidence Gaps

### 1. Local-first claims often hide remote dependencies

BridgeMemory is described as a local Markdown directory with no cloud bucket, while BridgeMCP is configured at a hosted URL and connects project/task state to the BridgeMind platform. Other BridgeMind pages also describe BridgeMCP as "runs locally" while documenting remote API communication. The exact boundary between local data, remote metadata, authentication, and paid entitlements is not fully clear in the reviewed documentation. Treat BridgeMind's architecture and security claims as medium confidence until source code or a data-flow specification is available.

### 2. Product claims exceed independently verified behavior

BridgeSpace's product page claims broad multi-agent memory and swarm behavior, but its public demo is a product-controlled experience and the reviewed sources are first-party. Its changelog records a rollback after terminal rendering and PATH regressions. This does not invalidate the design, but it lowers confidence in unqualified reliability claims.

### 3. Read-only does not mean safe

Paneflow's read-only pane server prevents cross-pane keystrokes, which is materially safer, but reading terminal output still exposes secrets and prompt-injection content. Product documentation does not establish a full provenance, redaction, or information-flow policy for retrieved pane data.

### 4. ACP maturity is uneven by feature

Core ACP v1 session and prompt operations are documented as current. Some useful capabilities, including usage/context reporting and v2 prompt lifecycle changes, appear in RFDs and may be draft, recently stabilized, or version-sensitive. Voss must negotiate schema/capabilities rather than implement from prose assumptions.

### 5. MCP interoperability does not solve context trust

MCP standardizes discovery and invocation, not semantic trustworthiness. Official security guidance, NSA guidance, OWASP, and recent research all identify token, session, prompt-injection, confused-deputy, and tool-poisoning risks. A universal MCP endpoint without strong per-resource policy would expand Voss's attack surface.

### 6. Agent-team mailboxes lack common terminal-level interoperability

Claude agent teams demonstrate the UX, but their task/mailbox state is Claude-specific. ACP focuses on client-agent sessions, and A2A focuses on agent services rather than arbitrary local TUI processes. There is no widely adopted standard that lets Voss deliver a structured message into every existing CLI agent. The safe baseline is user-visible notification plus explicit paste/adapter, not simulated universality.

### 7. Audit semantic conventions are still evolving

OpenTelemetry GenAI conventions are useful for export and correlation, but fields have moved or changed stability. They also do not guarantee full content capture, retention, causal completeness, or provenance. Voss needs a versioned internal event schema and should map outward.

### 8. Memory quality is largely unmeasured

The reviewed product sources describe persistence and retrieval features, not controlled evidence that automatic memory improves correctness over time. Stale or incorrect memories can compound just as easily as good ones. Voss should measure retrieval precision, contradiction rate, user rejection rate, and downstream task impact before enabling automatic promotion.

## Evidence Quality

| Evidence class | Confidence | Use in this report |
|---|---:|---|
| MCP, ACP, A2A protocol specifications | High for documented protocol semantics; medium for adoption/support breadth | Interfaces, capability negotiation, task/message/resource distinctions |
| W3C PROV and OpenTelemetry specifications | High for conceptual/telemetry models | Provenance and observability model; not a mandated storage format |
| NSA, NIST, OWASP guidance | High for threat categories and recommended controls | Context isolation, prompt-injection, token/session, and audit requirements |
| Official Warp, Claude Code, Paneflow docs | Medium-high for stated behavior; lower for performance/outcome claims | Competitive patterns, product constraints, documented limitations |
| BridgeMind product/blog/docs | Medium-low to medium | Product direction and claimed implementation; needs independent verification |
| Vendor comparison pages | Low-medium | Discovery only; not used as sole evidence for competitor weaknesses |
| Search snippets, marketing metrics, social posts | Low | Excluded from substantive conclusions |

## Source Inventory

### Terminal context and competitor memory

1. [Paneflow product overview](https://paneflow.dev/) — primary product documentation; raw CLI compatibility and read-only pane MCP.
2. [Paneflow getting started](https://paneflow.dev/docs) — primary product documentation; unknown agents, accounts, telemetry, sessions.
3. [Warp Drive](https://docs.warp.dev/knowledge-and-collaboration/warp-drive) — primary product documentation; object scopes, sharing, offline behavior.
4. [Warp Agent Mode Context](https://docs.warp.dev/knowledge-and-collaboration/warp-drive/agent-mode-context) — primary product documentation; automatic retrieval, citations, toggle.
5. [Warp Agent Context](https://docs.warp.dev/agent-platform/local-agents/agent-context) — primary product documentation; ad hoc context and distinction from persistent sources.
6. [Warp `@` context selection](https://docs.warp.dev/agent-platform/local-agents/agent-context/using-to-add-context) — primary product documentation; explicit file/folder/symbol/session-block context.
7. [Warp Rules](https://docs.warp.dev/agent-platform/capabilities/rules) — primary product documentation; global/project scope and `AGENTS.md` precedence.
8. [Warp Drive CLI context](https://docs.warp.dev/reference/cli/warp-drive) — primary product documentation; saved prompts and referenced objects in CLI runs.
9. [Warp environment variables](https://docs.warp.dev/knowledge-and-collaboration/warp-drive/environment-variables) — primary product documentation; static/dynamic values and secret-manager warning.
10. [Warp privacy and data control](https://docs.warp.dev/support-and-community/privacy-and-security/privacy/) — primary product documentation; telemetry, ZDR, redaction.
11. [BridgeSpace product](https://www.bridgemind.ai/products/bridgespace) — first-party product claims; BridgeMemory, BridgeSwarm, mailbox, terminal grid.
12. [BridgeMemory design article](https://www.bridgemind.ai/blog/bridgememory-persistent-context) — first-party technical claims; Markdown, links, MCP, atomicity, local token.
13. [BridgeMCP documentation](https://docs.bridgemind.ai/docs/mcp) — first-party product docs; task lifecycle, API keys, client compatibility.
14. [BridgeSpace changelog](https://www.bridgemind.ai/changelog) — first-party release evidence; terminal rollback and session recovery changes.
15. [Claude Code memory](https://code.claude.com/docs/en/memory) — primary product documentation; instruction scopes, auto-memory, storage, inspection, limits.
16. [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams) — primary product documentation; tasks, mailbox, tmux display, persistence, and limitations.

### Protocols and standards

17. [MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts) — official overview; tools/resources/prompts and control model.
18. [MCP resources specification](https://modelcontextprotocol.io/specification/2025-06-18/server/resources) — official specification; resource URIs, reads, subscriptions, annotations.
19. [MCP tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) — official specification; model-controlled calls and safety requirements.
20. [MCP roots specification](https://modelcontextprotocol.io/specification/2025-06-18/client/roots) — official specification; intended filesystem scope.
21. [MCP authorization security considerations](https://modelcontextprotocol.io/specification/draft/basic/authorization/security-considerations) — official draft; audience binding and token theft.
22. [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices) — official guidance; session hijacking, authorization, confused deputy, token passthrough.
23. [ACP introduction](https://agentclientprotocol.com/get-started/introduction) — official documentation; client-agent interoperability purpose.
24. [ACP architecture](https://agentclientprotocol.com/get-started/architecture) — official documentation; JSON-RPC, MCP reuse, UX/trust assumptions.
25. [ACP session setup](https://agentclientprotocol.com/protocol/v1/session-setup) — official v1 documentation; session lifecycle, cwd, roots, MCP servers.
26. [ACP prompt turn](https://agentclientprotocol.com/protocol/v1/prompt-turn) — official v1 documentation; structured content and session updates.
27. [ACP Session Info Update](https://agentclientprotocol.com/rfds/session-info-update) — official RFD/stabilized update; dynamic metadata.
28. [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) — official specification; messages, tasks, artifacts, history and delivery semantics.
29. [W3C PROV overview](https://www.w3.org/TR/prov-overview/) — standards-body provenance model and document family.
30. [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/) — official observability conventions; correlation/export model.

### Security and risk

31. [NSA: Model Context Protocol Security Design Considerations](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf) — government guidance; implicit trust, context leakage, cascading injection, scope and monitoring.
32. [OWASP MCP Tool Poisoning](https://owasp.org/www-community/attacks/MCP_Tool_Poisoning) — security-community guidance; indirect prompt injection via tool metadata/results.
33. [NIST AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) — government risk-management guidance; broader lifecycle and governance context.

## Bottom Line

Voss should not compete by making every terminal pane secretly Voss-aware. It should win by being the best terminal even when Voss is absent, then provide a carefully brokered upgrade path:

1. tmux owns durable processes;
2. the ADE observes terminal state locally;
3. users selectively expose read-only context;
4. compatible agents gain MCP or ACP structure;
5. Voss orchestration adds tasks, mailboxes, memory promotion, approvals, and audit only when enabled.

The durable differentiator is not "more memory." It is **context with explicit scope, provenance, capability boundaries, and a reversible adoption path**. That lets Voss leverage its organization and verification capabilities without requiring users to abandon the CLI agents, credentials, models, and terminal habits they already trust.
