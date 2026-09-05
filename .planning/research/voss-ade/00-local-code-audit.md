# Voss ADE Local Code Audit

**Audit date:** 2026-07-19  
**Scope:** `apps/voss-app`, `crates/voss-app-core`, the generated TypeScript SDK integration, V25 swarm server paths, planning/product documents, and available automated tests.

This note is evidence for the final deep dive. It is not a product specification.

## Current implementation

- Desktop stack: Tauri 2, Solid 1.9, Vite 8, Tailwind 4, and xterm.js 5.5.
- Terminal runtime: one `portable-pty` child per pane, held in an in-process Rust `PtyRegistry`.
- UI surfaces: terminal grid, workspaces, command palette, settings/themes/keymaps, agent sidebar/activity/usage, Voss protocol panes, organization cockpit/board/audit/replay, and V25 swarm views.
- Voss connectivity: a Python `voss serve` sidecar with loopback bearer authentication, REST, and SSE. The desktop imports the generated TypeScript SDK source directly.
- Persistence: JSON grid/session/layout data, SQLite agent registry, repo-local `.voss` state, and in-process live PTY handles.
- External agent execution: hard-coded launch choices plus macOS `sandbox-exec` and Linux `bwrap` wrappers when available.

The product already contains significant orchestration and organization UI. Its main deficit is not a lack of screens; it is that terminal lifecycle, workspace identity, agent interoperability, and opt-in boundaries are not yet reliable enough to support those screens as a daily-driver foundation.

## Verified gaps

### 1. The runtime is not tmux-backed

No production path starts, attaches to, or controls tmux. `crates/voss-app-core/src/pty/mod.rs` creates `portable-pty` children and retains them in a process-local registry. Closing the desktop therefore destroys the authority that owns live handles.

**Consequence:** A desktop crash, update, or restart cannot honestly promise live process continuity. The persisted session is a reconstruction recipe, not a durable session.

### 2. Persisted sessions do not preserve process identity

`crates/voss-app-core/src/session.rs` persists layout, pane identity, scrollback, and projectless state. `apps/voss-app/src/pane/PaneComponent.tsx` creates a fresh pane session and spawns a new shell during restoration.

**Consequence:** Planning claims that PTY identity survives reload are not supported by the schema or restore path. The final capability matrix must distinguish visual restoration from process reattachment.

### 3. Ordinary shells receive Voss state

The Tauri `spawn_pty` path in `apps/voss-app/src-tauri/src/lib.rs` injects `VOSS_EMBEDDED=1` and `VOSS_AGENT_ID` for generic shells. `apps/voss-app/src/pane/paneSession.ts` mints the identifier. This conflicts with the product copy in `AgentLaunchModal.tsx` that says Voss injects nothing and with the required terminal-only contract.

**Required invariant:** A terminal-only pane must be byte-transparent and Voss-free: no Voss environment, files, sidecar, network calls, prompt changes, or command rewriting unless the user explicitly enables an integration.

### 4. Per-pane shell selection is not wired to execution

The UI/session tree can retain a shell selection, but the pane transport does not pass that shell through the spawn command. Rust falls back to the global `$SHELL`.

**Consequence:** The visible/persisted configuration can disagree with the actual executable. A terminal engine must store and invoke an explicit argv/environment/cwd launch specification per pane.

### 5. External CLI launch syntax is incorrectly generalized

`apps/voss-app/src/components/AgentLaunchModal.tsx` appends a shared `--model`, `--cwd`, and positional task pattern across Claude, Codex, Gemini, OpenCode, and Aider. These CLIs do not have one grammar.

**Required model:** Raw user command is the universal baseline. Named adapters may contribute versioned executable discovery, argv construction, resume behavior, event hooks, and capability metadata, but must never become a prerequisite for running the CLI.

### 6. Some controls do not match their behavior

- Requested placement modes are currently collapsed to a horizontal split in `apps/voss-app/src/App.tsx`.
- Agent restart and detach callbacks are empty.
- Stop is passed a pane identifier where the PTY transport owns a separate private session identifier.

**Consequence:** The surface implies lifecycle authority it does not possess. Controls should be capability-driven and hidden or disabled when the backing engine cannot perform them.

### 7. Custom-agent persistence is not connected to the UI

Tauri exposes custom-agent load/save commands, while the launch modal hard-codes five CLIs and does not consume that backend.

**Consequence:** The current product cannot fulfill an open-ended "existing CLI agents" promise. It needs user-defined commands first and richer adapters second.

### 8. Workspace-scoped state can leak across workspaces

The Rust agent registry is held as one `Mutex<Option<Connection>>`. Once opened for the first workspace, later workspace requests reuse that connection. Separately, `apps/voss-app/src/voss/liveServer.ts` can reuse the current live server without validating that its cwd matches the requested workspace.

**Consequence:** Agent registry and Voss sidecar state can point at a different workspace than the terminal UI. All engine, sidecar, worktree, and registry handles need explicit stable workspace binding.

### 9. Frontend dependency boundaries are broken

The app imports source from `sdk/typescript`, but the pnpm workspace includes only `apps/*`, and the app/root dependency graph does not provide `openapi-fetch` and `eventsource-parser` to that imported package.

**Verification on 2026-07-19:**

- `cargo test -p voss-app-core -p voss-app`: 163 tests passed.
- `pnpm --dir apps/voss-app test`: 101 files and 862 tests passed, but 13 suites failed during import because the SDK dependencies could not resolve.
- `pnpm --dir apps/voss-app build`: failed on the same unresolved SDK dependencies, followed by related implicit-type errors.

### 10. OSC handling is not streaming-safe

`crates/voss-app-core/src/pty/reader.rs` describes fragmented-sequence state but the reader loop does not retain an accumulator across reads. Extraction handles a complete sequence in the current buffer rather than a stream containing split or multiple frames.

**Consequence:** Voss metadata can leak into terminal output or be dropped depending on PTY chunk boundaries. Terminal bytes and optional metadata parsing need separate, incremental, bounded pipelines.

### 11. Hyperlink commands appear unimplemented

The frontend invokes Tauri `open_url` and `open_path` commands from `paneSession.ts`; neither command appears in the Rust command set or invoke handler.

### 12. Terminal-only use mutates project state

Structural autosave writes `<workspace>/.voss/session.json`, and other desktop preferences/registries also use repo-local `.voss` paths.

**Required boundary:** Private desktop runtime state belongs in the platform app-data directory or an app database. Repo-local `.voss` should be created only for explicitly shareable Voss configuration, coordination, or audit data.

### 13. Release readiness is not demonstrated

Planning material refers to signed artifacts and updating, but the Tauri configuration has no signing identity, no updater plugin is evident, and repository workflows do not currently exercise the desktop's Rust, Vitest, Playwright, or Tauri build paths.

### 14. Product documentation has drifted

Examples include "Swarm Map" versus the current "Orchestra" name and a process-persistence claim that the implementation cannot satisfy. Older product boundaries also omit surfaces now present in the app.

**Required artifact:** One implementation-linked capability matrix with states such as shipped, partial, prototype, and proposed.

### 15. Background orchestration failures can disappear

The V25 swarm run path in `voss/harness/server/app.py` catches a broad exception in its background driver and discards it.

**Consequence:** An orchestration console can show stale or ambiguous state after server failure. Every managed run needs a durable terminal state and a surfaced causal error event.

### 16. Sidecar workspace authorization is too broad

The current workspace validation path can be invoked with no allowed roots, and memory endpoints accept a caller-supplied cwd. Loopback bearer authentication limits network exposure but does not establish workspace authorization.

**Required invariant:** A workspace-bound sidecar may read/write only its explicitly enrolled roots, with canonical-path validation and auditable permission decisions.

### 17. Composition is concentrated in two files

`apps/voss-app/src/App.tsx` and `apps/voss-app/src-tauri/src/lib.rs` combine many concerns. This is not a reason for a general rewrite. The justified extraction is narrow: a transport-neutral session engine, explicit workspace binding, and optional integration/sidecar interfaces.

## Architectural conclusion from the code

The implementation should be separated into three independently useful planes:

1. **Terminal plane:** tmux-backed session/process authority on supported Unix hosts, with direct PTY as a first-class fallback. It runs arbitrary commands without Voss behavior.
2. **Integration plane:** optional, capability-declared adapters and standard protocols that add status, resume, context, or structured events while preserving each CLI's own auth, configuration, billing, permissions, update path, and TUI.
3. **Voss plane:** an explicitly enabled sidecar and orchestration console that can observe or manage enrolled panes/worktrees, apply budgets and gates, coordinate roles, and retain audit history.

Terminal-only, observed, and Voss-managed modes must be durable product states rather than stages in a forced onboarding funnel.

## Evidence confidence

- **High confidence:** runtime and persistence findings, environment injection, hard-coded argv construction, workspace connection reuse, unresolved imports, test results, and repo-local state paths. These are directly evidenced by code or commands.
- **Medium confidence:** user-visible impact of lifecycle callbacks and hyperlink commands. The paths are evident, but full interactive Tauri verification was not performed.
- **Not verified:** packaged desktop behavior, signing/updater behavior in an external release system, PTY fidelity under a live tmux server, and end-to-end macOS/Linux sandbox behavior.

