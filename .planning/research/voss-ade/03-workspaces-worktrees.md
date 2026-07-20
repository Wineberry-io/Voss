# Subtopic 03: Workspaces, Sessions, Panes, and Git Worktree Lifecycle

> Research date: 2026-07-19  
> Focus: a terminal-first, tmux-powered Voss ADE that runs arbitrary existing CLI agents and exposes Voss orchestration only as an optional control plane  
> Evidence base: 32 distinct sources consulted; 25 full pages opened; official documentation and project repositories prioritized

## Executive Conclusion

Voss should not model a workspace as a prettier terminal tab or model a restored session as a reconstructed xterm buffer. A useful agentic workspace is a durable task envelope that joins five independently recoverable resources:

1. a human-facing workspace identity;
2. an optional repository and worktree binding;
3. a live tmux session/window/pane binding;
4. one or more ordinary CLI processes, which may be agents but do not have to be;
5. optional Voss orchestration metadata, attached as a sidecar rather than required for execution.

The market has converged on tmux plus Git worktrees because those are inspectable, scriptable primitives that survive tool churn. dmux and workmux automate creation, setup, integration, and cleanup around them; Paneflow adds task context, diffs, dev-server discovery, and cross-pane inspection; Warp separates static launch configurations from last-session restoration; Zellij makes the most important safety choice in this area by reconstructing commands behind an explicit confirmation instead of blindly rerunning them.

For Voss, tmux should become the live process authority. Voss should own a durable metadata and reconciliation layer over tmux and Git, not a second opaque process universe. The desktop app, a plain terminal, and the optional orchestration console should all be clients of the same workspace state. Closing the app must detach, not terminate. On restart, Voss must first reattach to live tmux state, then reconcile worktrees, and only then offer explicit reconstruction for resources that no longer exist.

## Key Findings

- **A workspace is not a process container.** Warp, Zellij, tmux, dmux, workmux, and Paneflow all separate some combination of task grouping, visual layout, live process state, and reconstructed state. Voss should make those boundaries explicit in its schema.
- **tmux provides continuity, not full crash resurrection.** Clients can detach while programs keep running, but if the tmux server dies, the sessions are gone. Recovery after reboot/server failure is a replay of saved metadata and commands, not preservation of process memory ([tmux getting started](https://github.com/tmux/tmux/wiki/Getting-Started), [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)).
- **tmux control mode is the correct native integration seam.** It is an official text protocol for commands, output blocks, and notifications, avoiding screen scraping or a nested interactive tmux client ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)).
- **Static launch definitions and recent-session snapshots are different products.** Warp stores launch configurations as editable YAML but stores last-session windows/tabs/panes and recent blocks in local SQLite ([launch configurations](https://docs.warp.dev/terminal/sessions/launch-configurations), [session restoration](https://docs.warp.dev/terminal/sessions/session-restoration)). Voss needs the same desired-state versus observed-state split.
- **Safe reconstruction requires a restart policy.** Zellij saves layouts and pane commands but puts resurrected commands behind a confirmation banner to avoid rerunning destructive commands automatically ([session resurrection](https://zellij.dev/documentation/session-resurrection.html)).
- **Worktrees solve file collisions but not environment collisions.** Parallel worktrees still contend for ports, databases, containers, caches, credentials, and external services. workmux documents deterministic port derivation plus availability checks; community reports identify ports as the next failure after source isolation ([workmux](https://github.com/raine/workmux), [Warp community discussion](https://www.reddit.com/r/warpdotdev/comments/1slf86f/we_just_launched_universal_agent_support_in_warp/)).
- **Creation and cleanup must be transactional and separately recoverable.** Git exposes stable machine-readable discovery, worktree locks, repair, prune, and guarded removal. Claude Code locks active worktrees and its cleanup sweep skips dirty, untracked, or unpushed work ([Git worktree](https://git-scm.com/docs/git-worktree), [Claude Code worktrees](https://code.claude.com/docs/en/worktrees)).
- **Merge and cleanup should not be one irreversible gesture.** workmux supports merge, rebase, squash, keep-after-merge, later cleanup, pre-merge checks, and conflict continuation. Voss should default to keeping the lane after integration until verification succeeds ([workmux merge lifecycle](https://github.com/raine/workmux)).
- **Agent compatibility wins when the terminal remains ordinary.** dmux supports many agent CLIs and plain terminal panes; Paneflow runs agents as normal local CLI processes; Warp now explicitly positions itself as usable with arbitrary harnesses ([dmux](https://github.com/standardagents/dmux), [Paneflow](https://paneflow.dev/), [Warp repository](https://github.com/warpdotdev/warp)).
- **Durable identity must not be derived from paths or tmux display names.** Worktrees can move and be repaired; branches can be renamed; tmux runtime IDs disappear after server reconstruction. Voss needs its own UUIDs and explicit bindings to these mutable external identifiers.

## Detailed Notes

### 1. The Models Used by tmux, Zellij, and Warp

#### tmux

tmux has a precise hierarchy:

- a **server** owns the process universe and listens on a Unix socket;
- a **client** attaches to a session;
- a **session** links one or more windows;
- a **window** may be linked into multiple sessions;
- a **pane** contains one pseudo-terminal and its foreground program.

This is more expressive than Voss's current one-tree-per-workspace model. It also means the Voss UI cannot safely assume a one-to-one relation among visual tabs, tmux sessions, and processes. The app should choose and enforce a simpler Voss mapping while preserving import/attach compatibility.

Recommended default mapping:

| Voss concept | tmux binding | Reason |
|---|---|---|
| Workspace | one tmux session | A workspace is independently attachable from any terminal |
| Workspace surface/tab | one or more tmux windows | Allows terminal, review, logs, and orchestration views without one giant pane tree |
| Terminal lane | one tmux pane | One PTY/process per lane; direct status and I/O association |
| App window | tmux control-mode client | The app can close/detach without killing execution |

tmux server sockets can be isolated with `-L <socket-name>` or an explicit `-S <path>`. If a socket file is accidentally removed while the server remains alive, `SIGUSR1` can recreate it. The server itself normally exits when it has no sessions, and a server crash loses live sessions. Access to the socket is effectively full control, not a security boundary, even when read-only convenience flags are used ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html), [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)).

Voss should therefore support two explicit backends:

- `managed`: a dedicated per-user Voss socket namespace, still attachable through ordinary `tmux -L <name> attach`;
- `existing`: attach/import sessions from a user-selected tmux socket without rewriting the user's configuration.

The managed backend should be the predictable default for the desktop UI. Existing-tmux mode is essential for terminal daily-driver adoption and should be a first-class option, not an unsupported import hack.

#### Zellij

Zellij cleanly distinguishes live attachment from resurrection. Its serializer can capture layouts, commands, viewport, and optionally scrollback. On resurrection it reconstructs layout and reruns command panes, but commands remain behind a confirmation banner. That is the right safety model for Voss. Open issues also show why recovery should be observable and debuggable: users have reported sessions not being retained and layout-specific settings disappearing after resurrection ([official resurrection docs](https://zellij.dev/documentation/session-resurrection.html), [issue 4413](https://github.com/zellij-org/zellij/issues/4413), [issue 4156](https://github.com/zellij-org/zellij/issues/4156)).

#### Warp

Warp uses two storage concepts:

- **launch configurations:** editable YAML describing windows, tabs, nested pane layout, absolute working directories, focus, and startup commands;
- **session restoration:** local SQLite state for the last windows/tabs/panes and recent terminal blocks.

This split prevents a transient shutdown snapshot from becoming the user's reusable project template. Voss should adopt this distinction:

- `WorkspaceTemplate`: declarative, shareable, reviewable, no runtime IDs;
- `WorkspaceSnapshot`: local, frequently updated, includes bindings and recent state;
- `WorkspaceRuntime`: live tmux and Git observations, never treated as durable truth by itself.

### 2. Current Voss Model and the Gaps It Creates

The current Voss app has a sound visual/session persistence foundation, but it does not yet model a durable terminal engine:

- `WorkspaceEntry` stores `id`, `name`, a single optional `projectPath`, accent/order, a layout preset, and a profile ([workspaceStorage.ts](../../../apps/voss-app/src/workspaces/workspaceStorage.ts)). It has no repository identity, worktree, branch, base/target, tmux binding, bootstrap state, or port allocation.
- `SessionFile` stores a pane tree, focus, active preset, up to 2,000 scrollback lines per pane, and a project-less flag ([sessionStorage.ts](../../../apps/voss-app/src/grid/sessionStorage.ts), [sessionCommands.ts](../../../apps/voss-app/src/grid/sessionCommands.ts)). It intentionally excludes PTY IDs, process names, environment changes, and agent launch configuration.
- `PaneLeaf` persists only Voss pane ID, cwd, shell, and display index. It cannot distinguish a plain shell, dev server, arbitrary CLI agent, Voss-managed agent, or attachable tmux pane.
- `PtyRegistry` and `PtyTransport` are in-process native PTY state. Remount survival is implemented well inside one app lifetime, but closing/crashing the Tauri process removes the registry and PTY ownership. Restore seeds old text and spawns a new process; it does not reattach to the prior process ([paneSession.ts](../../../apps/voss-app/src/pane/paneSession.ts), [pty-ipc.ts](../../../apps/voss-app/src/pane/pty-ipc.ts)).
- Project sessions are persisted at `<project>/.voss/session.json`, while project-less sessions are keyed by workspace UUID under the user config directory ([session.rs](../../../crates/voss-app-core/src/session.rs)). Two Voss workspaces bound to the same project path therefore resolve to the same project session file and can overwrite each other's layouts. This becomes a hard collision once task workspaces and parallel worktrees are introduced.
- Repository-local `.voss/session.json` also makes desktop terminal state appear to require Voss adoption and can dirty or alter repos merely because they were opened. For a tool intended to work with arbitrary CLI agents and repositories, local runtime state should be user-global by default. A checked-in repo template should be explicit opt-in.
- Current fail-safe loading replaces corrupt workspace metadata with a default workspace. That protects startup, but without a backup/journal/reconciliation layer it can hide recoverable tmux sessions and worktrees from the UI.

The smallest compatible evolution is not to overload `SessionFile` v1 with more optional fields. Introduce a new backend-owned workspace database/schema and migrate the visual tree as one child record. Keep v1 import for existing users.

### 3. Proposed Voss Domain Model

Use distinct stable identities and binding records:

```text
Project
  id, canonicalGitCommonDir, mainWorktreePath?, remotesFingerprint

Workspace
  id, name, projectId?, templateId?, lifecycleState, createdAt, lastOpenedAt
  orchestrationMode = off | observed | managed

CheckoutBinding
  workspaceId, kind = main | linked | external | none
  path, branchRef?, headOid, baseRef?, baseOid, targetRef?
  managedByVoss, lockReason?, setupState, cleanupState

TmuxBinding
  workspaceId, backendId, socketNameOrPath, sessionName, observedSessionId?
  lastSeenServerPid?, attachmentState

Surface
  id, workspaceId, kind = terminal | review | files | browser | orchestration
  tmuxWindowId?, order, title

Pane
  id, surfaceId, tmuxPaneId?, cwd, role, commandSpec?, restartPolicy
  cliAdapter? = generic | claude | codex | opencode | voss | ...
  nativeAgentSessionId?, vossRunId?

PortLease
  workspaceId, serviceKey, host, port, status, allocatedAt

Operation
  id, workspaceId, kind, phase, intentJson, resultJson, startedAt, finishedAt
```

Important invariants:

- Voss workspace IDs never equal branch names, paths, tmux names, pane IDs, or Voss orchestration run IDs.
- A workspace may be plain terminal-only with no project, worktree, agent, or Voss run.
- A workspace may adopt an external checkout without claiming cleanup ownership.
- Only Voss-managed linked worktrees may be automatically removed.
- Every destructive action is conditioned on fresh observed state, not saved metadata.
- `orchestrationMode=off` is fully functional. `observed` adds status and history. `managed` enables budgets, scoped tools, board/run views, and Voss protocol features.

### 4. tmux Engine Architecture

#### Use control mode, not nested tmux rendering

tmux control mode exposes a text protocol for commands, structured output blocks, pane output, layout changes, session changes, and subscriptions. The Rust backend should own one long-lived control-mode client per tmux server and multiplex events to the Solid UI. xterm remains the renderer for selected pane output.

Core adapter responsibilities:

1. discover tmux and validate minimum version;
2. connect/start the selected socket backend;
3. inventory sessions/windows/panes with stable format strings;
4. attach pane output and apply backpressure;
5. translate xterm input to the selected tmux pane without shell interpolation;
6. translate UI splits/resizes/focus into tmux commands;
7. subscribe to pane/session lifecycle notifications;
8. set Voss UUIDs as tmux user options so bindings can be rediscovered after an app crash;
9. never edit `~/.tmux.conf` automatically.

The existing native PTY backend should remain available as `direct` for Windows or environments without tmux. That preserves current portability while making tmux the durable Unix/macOS engine. Do not pretend the direct backend has detach/reattach semantics it cannot provide.

#### Deterministic naming and collision handling

Human names are labels; UUIDs are identity. A tmux session name can be a readable slug plus a short stable suffix, for example `voss-auth-refresh-7f3a2c`. Before creation:

- query the selected server for existing names and Voss user-option IDs;
- if the name exists with the same Voss UUID, attach;
- if it exists without the UUID or with another UUID, allocate a suffix;
- never kill or rename an unknown session to make room.

The same policy applies to branches and paths. Resolve collisions under a per-repository operation lock and record the chosen values before launching processes.

### 5. Complete Worktree Lifecycle

#### A. Repository discovery

Use Git commands, not `.git` path assumptions:

- `git rev-parse --show-toplevel` for the current checkout root;
- `git rev-parse --git-common-dir` / `--absolute-git-dir` for shared repository identity;
- `git worktree list --porcelain -z` for a stable, path-safe inventory.

Git explicitly warns callers not to assume whether data lives under `$GIT_DIR` or `$GIT_COMMON_DIR` ([rev-parse](https://git-scm.com/docs/git-rev-parse), [worktree details](https://git-scm.com/docs/git-worktree.html)). Canonical common-dir identity prevents the main checkout and linked worktrees from appearing as unrelated projects.

#### B. Creation state machine

Recommended phases:

```text
requested -> preflight -> path_reserved -> git_created_locked
          -> files_prepared -> bootstrap_running -> ready -> tmux_started
```

Creation algorithm:

1. Acquire a per-repository filesystem lock.
2. Re-read `git worktree list --porcelain -z`; never rely on cached inventory.
3. Resolve base ref to an immutable OID and persist both.
4. Allocate branch name and worktree path; reject unsafe names and pre-existing non-owned paths.
5. Create with `git worktree add --lock --reason "voss:<workspace-id>" -b <branch> <path> <base-oid>`.
6. Persist the Git result before running hooks.
7. Prepare explicit file strategies.
8. Allocate port leases.
9. Run setup hooks with streamed logs, cancellation, timeout, and recorded exit status.
10. If setup fails, keep the worktree, mark `setup_failed`, and open a rescue shell. Do not silently delete diagnostic state.
11. Create/attach the tmux session and open configured panes.

Git's creation-time `--lock` avoids a race between add and a later lock. Claude Code uses the same active-worktree lock pattern so concurrent cleanup cannot remove a running lane ([Git worktree](https://git-scm.com/docs/git-worktree), [Claude Code worktrees](https://code.claude.com/docs/en/worktrees)).

#### C. Bootstrap, secrets, dependencies, and environment

Adopt a small project-local optional file such as `.voss/workspaces.toml` only when a repo chooses to configure Voss. Generic operation must require no file. Supported hooks should be generic enough to call `make`, `just`, `mise`, `direnv`, or arbitrary project scripts:

```toml
[worktree]
post_create = ["./scripts/worktree-bootstrap"]
pre_integrate = ["just check"]
pre_remove = ["./scripts/worktree-stop"]

[[worktree.files]]
path = ".env"
mode = "copy"

[[worktree.ports]]
key = "web"
preferred = 3000
env = "PORT"
```

Rules:

- Never copy all ignored files automatically; credentials and machine state require an allowlist.
- Prefer package-manager shared caches over symlinking `node_modules`. A symlink can couple branches with incompatible lockfiles and native builds. Expose symlink as an expert option because workmux users do use it, but do not default to it.
- Inject Voss-generated values through `.env.local`, `direnv`, or pane environment overrides without modifying tracked `.env`.
- Preserve the user's shell startup and agent configuration. Voss adds environment metadata such as `VOSS_WORKSPACE_ID`, but an arbitrary CLI does not need to understand it.
- Hooks receive stable variables (`workspace id`, `project root`, `worktree path`, `branch`, `base`, allocated ports) and run from the worktree.

workmux makes a useful UX distinction: blocking post-create hooks delay opening the tmux window, while pane commands can visibly install dependencies or start services in parallel. Voss should let templates mark steps as `blocking` or `pane`, with blocking steps kept minimal ([workmux](https://github.com/raine/workmux)).

#### D. Port allocation

Hash-only port selection is deterministic but not sufficient. Use a persistent lease registry plus a bind/owner check:

1. derive a stable candidate range from project and workspace UUID;
2. lock the registry;
3. reuse the workspace's prior lease if still available or owned by its process;
4. probe candidates and reserve the first free port;
5. persist before process launch;
6. inject ports and display them in workspace status;
7. release only after confirming associated processes are gone.

For multi-service projects, allocate a named bundle. Later, offer a loopback-IP backend on supported platforms, but unique port leases are the portable baseline. Community evidence is strong that worktrees without network namespace/port planning simply move collisions from files to runtime services.

#### E. Rebase and integration

Store `baseRef`, `baseOid`, and `targetRef` at creation; they answer different questions. A branch may be based on another feature branch but ultimately target `main`.

Integration flow:

1. Refresh Git inventory and remote refs if the user opted into fetch.
2. Require the source worktree to be clean or stop with explicit options; do not auto-stash silently.
3. Run `pre_integrate` verification and persist its evidence.
4. Offer `create PR`, `rebase`, `merge`, and `squash` as separate commands.
5. Resolve rebase conflicts inside the source worktree and keep the workspace in `conflicted` until the user continues or aborts.
6. Only merge into a target checkout after verifying it is the intended branch and its index/worktree are clean. Git warns that abort may not reconstruct pre-merge uncommitted state ([git merge](https://git-scm.com/docs/git-merge/2.19.0)).
7. Record the target OID before integration and the resulting OID after it.
8. Mark `integrated` only after `git merge-base --is-ancestor <source-tip> <result>` or equivalent strategy-specific verification.
9. Keep the source workspace by default until post-integration verification or PR merge confirmation.

Do not update a target branch ref behind an open target checkout: even compare-and-swap `git update-ref` can leave that checkout's index and working tree inconsistent. `update-ref` is useful for guarded metadata operations, but it is not a substitute for integrating through the checkout that owns the target branch ([git update-ref](https://git-scm.com/docs/git-update-ref.html)).

#### F. Cleanup

Cleanup is its own state machine:

```text
cleanup_requested -> preflight -> processes_stopped -> tmux_removed
                  -> worktree_removed -> branch_removed? -> leases_released -> archived
```

Safety rules:

- Default removal refuses dirty/untracked files, unpushed commits, an unmerged source tip, active processes, or a locked worktree.
- A force action shows the exact files/commits/processes that will be lost.
- External/adopted worktrees are detached from Voss metadata, never deleted automatically.
- Stop dev servers before releasing ports.
- Remove with `git worktree remove`, not raw directory deletion.
- Delete a branch only after verifying it is integrated into the recorded target or after separate confirmation.
- Run `git worktree prune --dry-run` before prune and use expiry; do not run aggressive prune on every startup.
- Use `git worktree repair` when paths moved; do not treat moved worktrees as abandoned automatically.

### 6. Restore and Crash Recovery

#### Recovery tiers

Voss must label recovery honestly:

| Tier | Condition | Action |
|---|---|---|
| Reattach | tmux server/session/pane still live | Rebind UI; no command replay |
| Reconcile | tmux live but metadata stale, or worktree moved | Discover IDs/options; repair bindings |
| Reconstruct | tmux server gone but worktree and snapshot remain | Rebuild layout; prompt before commands |
| Recover checkout | Git metadata exists but path moved/missing | Offer `worktree repair`, locate, or mark missing |
| Archive | source resources intentionally removed | Preserve transcript, operation history, and integration result |

#### Startup reconciliation order

1. Open the workspace database and operation journal.
2. Discover tmux backends and live sessions.
3. Discover Git worktrees for known repositories with porcelain output.
4. Match by Voss UUID user options and canonical Git common-dir identity.
5. Complete or roll back interrupted idempotent operations.
6. Present unresolved resources as actionable states; do not silently discard them.
7. Attach live sessions first.
8. Offer reconstruction only for missing sessions.

#### Persistence mechanics

Use SQLite in WAL mode for the user-global workspace database plus an append-only operation journal/table. Every lifecycle operation records intent before side effects and results after each phase. Continue atomic snapshot exports for diagnostics, but do not make one JSON file the sole index.

Snapshots should be periodic and event-driven, not only on graceful close. The current Voss close-save path is useful but cannot cover crashes, `kill -9`, power loss, or renderer deadlock. tmux-continuum's default 15-minute save interval illustrates both the value and the possible loss window of periodic snapshots ([continuum FAQ](https://github.com/tmux-plugins/tmux-continuum/blob/master/docs/faq.md)). A practical Voss cadence is:

- immediate journal entry for lifecycle changes;
- debounced structural snapshot after layout/cwd/title changes;
- bounded scrollback checkpoints at a slower interval;
- graceful-close checkpoint as an optimization, not a correctness dependency.

#### Command replay policy

Each pane command needs one of:

- `never`: restore a shell and show the prior command as history;
- `prompt`: default for agents, dev servers, watchers, and unknown commands;
- `always-safe`: only declarative commands explicitly marked by the user/template.

Never automatically replay an arbitrary last foreground command. `tmux-resurrect` deliberately restores only a conservative program list by default, and Zellij requires confirmation. Voss should be at least as conservative ([tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect), [Zellij resurrection](https://zellij.dev/documentation/session-resurrection.html)).

Agent-native resumption is separate from process replay. Where a CLI exposes a stable resume/session ID, an optional adapter may offer `resume`. Generic CLIs remain ordinary commands and must still be usable without an adapter.

### 7. Product Recommendations for Voss

#### P0: Make terminal continuity real

- Add a tmux backend and make closing the desktop app detach rather than kill.
- Add `voss workspace list|new|attach|open|close` commands that operate without invoking the Voss harness.
- Show the exact attach command for every managed workspace.
- Support a fully functional plain terminal workspace with `orchestrationMode=off`.
- Move runtime workspace/session state to a user-global store. Treat repo-local templates as opt-in.

Success test: launch Codex, Claude Code, OpenCode, or a plain long-running shell command; close the desktop app; attach through a normal terminal; reopen the app and reattach without restarting the process.

#### P1: Add managed worktree lanes

- One action creates a branch, locked worktree, tmux session, setup environment, and selected arbitrary CLI.
- Add project/worktree/branch/base/target/dirty/ahead/behind metadata to tabs and command palette.
- Add explicit setup-failed and conflict-recovery states.
- Implement named port leases and display service URLs.
- Add diff/review view per worktree, following Paneflow's task-context model.

Success test: run three different agents in three worktrees, each with an independent dev server and no source or port collisions; restart only the UI and preserve all lanes.

#### P2: Integrate and clean up safely

- Add pre-integration checks, PR creation, rebase, merge, squash, and keep-after-merge.
- Separate integrate and remove actions.
- Add orphan/dirty/unpushed/locked guards with a dry-run summary.
- Reconcile worktrees created outside Voss and mark ownership honestly.

Success test: an interrupted rebase, moved worktree, dirty target checkout, deleted remote branch, and app crash during cleanup all recover to an explainable state without losing work.

#### P3: Layer Voss capabilities on top

- “Adopt into Voss” attaches a terminal lane to a Voss run without respawning the CLI where possible.
- The orchestration console groups existing workspace panes and Voss-managed runs in one view, but does not own basic terminal navigation.
- Budgets, roles, board state, memory, and audit are enhancements carried by Voss IDs; generic lanes show only process/Git/tmux facts.
- Cross-pane inspection should begin read-only, following Paneflow's MCP model, and require explicit permission for input injection.

Success test: the same workspace remains useful when Voss server/harness integration is disabled, then gains orchestration telemetry when enabled.

### 8. Anti-Patterns to Avoid

- Do not make one worktree per pane. A task workspace commonly needs agent, shell, test, and server panes sharing one checkout. dmux explicitly allows multiple panes/agents against the same worktree.
- Do not equate visual restore with live process restore.
- Do not put every desktop runtime snapshot under `.voss/` in the repository.
- Do not require a `.voss` file, Voss agent CLI, or Voss account to create a workspace.
- Do not parse `git worktree list` human output or inspect `.git/worktrees` directly.
- Do not kill or rename unknown tmux sessions to resolve naming collisions.
- Do not auto-run arbitrary saved commands after a server crash.
- Do not auto-copy secrets or symlink dependency trees without explicit configuration.
- Do not auto-stash, auto-commit, merge, and delete in one opaque operation.
- Do not call a worktree “isolated” without disclosing shared Git refs/config, credentials, ports, databases, and external services. Git's repository config is shared by default across worktrees ([Git worktree configuration](https://git-scm.com/docs/git-worktree.html)).

## Notable Quotes and Data Points

- tmux officially defines control mode as a text-only application protocol and emits structured notifications, making it a supported integration surface rather than a private implementation detail ([tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)).
- Git recommends `git worktree list --porcelain -z` for stable script parsing and paths containing unusual characters ([Git worktree](https://git-scm.com/docs/git-worktree)).
- `git worktree add --lock` exists specifically to avoid the race in creating then separately locking a worktree ([Git worktree](https://git-scm.com/docs/git-worktree)).
- Claude Code's cleanup sweep skips worktrees with changed/untracked files or unpushed commits and locks worktrees while agents are active ([Claude Code worktrees](https://code.claude.com/docs/en/worktrees)).
- Warp's launch configuration schema supports nested pane layouts, focused panes, absolute cwd values, and startup commands, while session restoration uses local SQLite ([Warp launch configurations](https://docs.warp.dev/terminal/sessions/launch-configurations), [Warp restoration](https://docs.warp.dev/terminal/sessions/session-restoration)).
- Zellij can serialize viewport and scrollback, but these are disabled by default because they increase resource and cache use ([Zellij options](https://zellij.dev/documentation/options.html)).
- workmux's documented integration sequence includes checking uncommitted changes, running the selected merge strategy, then optionally deleting the tmux window, worktree, and local branch. It also supports keeping those resources for later verification ([workmux](https://github.com/raine/workmux)).
- GitHub Desktop 3.6 added first-class worktree support and explicitly connected it to isolated parallel coding-agent sessions, evidence that worktrees are becoming a standard Git UX rather than an expert-only trick ([GitHub changelog](https://github.blog/changelog/2026-06-26-github-desktop-3-6-worktrees-and-deeper-copilot-integration/)).

## Source Credibility Notes

- **Highest confidence:** tmux manual/wiki, Git documentation, Zellij documentation, Warp documentation, and Anthropic's Claude Code documentation. These define actual product/protocol behavior.
- **High confidence for implementation patterns:** dmux, workmux, tmux-resurrect, and tmux-continuum repositories. They are primary project sources, but their design choices should not be mistaken for universal requirements.
- **High confidence for product behavior, lower for comparative claims:** Paneflow, Codemux, Warp marketing/newsroom, and product sites. Feature descriptions are useful; claims of superiority are not independently validated.
- **Community sources:** Reddit discussions are used only for recurring operational pain such as port collisions and restoration confusion. They are anecdotes, not prevalence estimates.
- **Open issues:** Zellij issues demonstrate possible failure modes, not that every user or current release is affected.
- **Current-market caveat:** Several products and releases are from 2026 and evolving quickly. Architecture recommendations rely on stable primitives (tmux and Git), not current feature-count rankings.

## Gaps and Open Questions

- tmux control mode supports the needed event model, but Voss needs a focused prototype to validate high-throughput full-screen TUI rendering, Unicode/input fidelity, mouse forwarding, and resize behavior through xterm.
- tmux is not native on Windows. Voss needs an explicit support policy: WSL tmux, bundled/managed alternative, or current direct PTY backend with reduced continuity guarantees.
- It is not yet decided whether Voss-managed sessions should default to a dedicated socket or the user's existing server. The recommendation here is dedicated by default plus first-class existing-server mode; user research should validate it.
- Submodules remain an incomplete Git worktree surface according to Git's own documentation. Voss should detect them and warn before promising a fully isolated checkout.
- Port leasing cannot isolate shared databases, queues, cloud accounts, or Docker resource names. Project hooks/templates must declare these resources; Voss cannot infer every collision safely.
- CLI-native resume semantics differ by agent and version. Generic process continuity must ship independently of any adapter.
- Repo-local template format and precedence need product decisions. The central rule should remain: no configuration is required for a plain workspace.
- Remote tmux/SSH workspaces need a later transport and trust model; local socket access patterns should not be generalized to remote multi-user hosts without authentication and policy work.

## All Sources

### Official and Primary Documentation

1. [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html) - authoritative server/session/window/pane hierarchy, sockets, hooks, control mode, exit behavior, and pane restart options.
2. [tmux Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started) - official explanation of detach/reattach and session organization.
3. [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ) - server-crash loss, socket recreation, and socket trust-boundary guidance.
4. [Git worktree documentation](https://git-scm.com/docs/git-worktree) - creation, list, lock, prune, remove, repair, safety checks, and stable porcelain output.
5. [Git worktree details/configuration](https://git-scm.com/docs/git-worktree.html) - shared versus per-worktree config/refs, `$GIT_COMMON_DIR`, locks, and path repair.
6. [Git rev-parse documentation](https://git-scm.com/docs/git-rev-parse) - canonical repository and worktree path discovery.
7. [Git merge documentation](https://git-scm.com/docs/git-merge/2.19.0) - dirty-worktree risks, abort behavior, fast-forward, and no-commit inspection.
8. [Git update-ref documentation](https://git-scm.com/docs/git-update-ref.html) - guarded compare-and-swap ref updates and reflog recording.
9. [Warp session restoration](https://docs.warp.dev/terminal/sessions/session-restoration) - local SQLite snapshot of windows, tabs, panes, and recent blocks.
10. [Warp launch configurations](https://docs.warp.dev/terminal/sessions/launch-configurations) - editable YAML desired-state layouts, cwd, focus, and startup commands.
11. [Warp windows](https://docs.warp.dev/terminal/windows) - each split pane is a unique terminal session.
12. [Warp working directory](https://docs.warp.dev/terminal/more-features/working-directory) - default working-directory behavior for new sessions.
13. [Zellij session resurrection](https://zellij.dev/documentation/session-resurrection.html) - serialized layouts/commands, optional viewport/scrollback, and confirmation-gated replay.
14. [Zellij options](https://zellij.dev/documentation/options.html) - serialization settings and resource tradeoffs.
15. [Zellij layouts](https://zellij.dev/documentation/layouts.html) - declarative KDL pane/tab layout model.
16. [Claude Code worktrees](https://code.claude.com/docs/en/worktrees) - automatic worktree creation, active locks, conservative cleanup, local file inclusion, and non-Git hooks.

### Project Repositories and Product Sources

17. [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect) - reconstructed sessions/windows/panes/layout/cwd and conservative program replay.
18. [tmux-continuum FAQ](https://github.com/tmux-plugins/tmux-continuum/blob/master/docs/faq.md) - periodic save interval, retention, and restore behavior.
19. [dmux repository](https://github.com/standardagents/dmux) - multi-agent/plain-terminal panes, worktree-per-task, multi-project sessions, lifecycle hooks, merge/PR, and visibility controls.
20. [dmux documentation site](https://dmux.ai/) - project, pane, worktree, and merge lifecycle descriptions.
21. [workmux repository](https://github.com/raine/workmux) - create/setup/rebase/merge/remove lifecycle, hooks, file strategies, dashboards, ports, and cleanup guards.
22. [workmux changelog](https://github.com/raine/workmux/blob/main/CHANGELOG.md) - rename/recovery/status and lifecycle hardening evidence.
23. [Paneflow product](https://paneflow.dev/) - normal local CLI processes, task workspaces, Git/diff/server context, session status, and read-only cross-pane MCP.
24. [Paneflow documentation](https://paneflow.dev/docs) - supported terminal/agent/workspace behavior.
25. [Paneflow introduction](https://paneflow.dev/blog/introducing-paneflow) - one-workspace-per-task framing, persistent layouts/sessions, and local-first model.
26. [Codemux](https://codemux.org/) - tmux/Git/worktree/browser composition inside an ADE workspace.
27. [Warp open-source repository](https://github.com/warpdotdev/warp) - explicit bring-your-own CLI-agent positioning.
28. [Warp agent product page](https://www.warp.dev/agents) - branch/worktree/PR metadata and multiple agent CLIs in terminal sessions.

### Recent Releases, Criticism, and Community Signal

29. [GitHub Desktop 3.6 worktrees](https://github.blog/changelog/2026-06-26-github-desktop-3-6-worktrees-and-deeper-copilot-integration/) - recent mainstream worktree UX and agent-parallelism rationale.
30. [Warp ADE open-source announcement](https://www.warp.dev/newsroom/2026/4/28/warp-open-sources-its-agentic-development-environment) - terminal-to-ADE positioning and configurable interface modes.
31. [Warp universal-agent AMA](https://www.reddit.com/r/warpdotdev/comments/1slf86f/we_just_launched_universal_agent_support_in_warp/) - worktree launch patterns and recurring port-conflict reports.
32. [Zellij resurrection issue 4413](https://github.com/zellij-org/zellij/issues/4413) and [settings-loss issue 4156](https://github.com/zellij-org/zellij/issues/4156) - concrete restoration failure modes and the need for inspectable reconciliation.

