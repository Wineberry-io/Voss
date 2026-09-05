# ADE Canvas, Observe, and Instruction Files — Execution Plan

**Created:** 2026-09-05
**Status:** Locked decisions, sprints ready to execute in order
**Codename:** S0–S9 (single ordered sprint sequence; not a GSD track)
**Inputs:** `.planning/VOSS-OBSERVE-IMPLEMENTATION-BRIEF.md` (reconciled copy of the 2026-09-05 brief), 49-IDE canvas teardown, `apps/voss-app` review, harness instruction-file gap audit
**Related:** `.planning/ADE-REDESIGN.md`, `apps/voss-app/PRODUCT.md` (V24 contract), `.planning/BOS-EVENT-SCHEMA.md`, `.planning/notes/laravel-account-control-plane-plan.md`

> Not run through GSD. No SPEC/PLAN generation. Each sprint below is the executable unit: tasks name files, the DoD is a checklist, acceptance criteria are tests or observable behavior. A sprint is done when every DoD box is checked and every acceptance criterion has evidence (test name or screenshot path).

---

## 0. Decisions (locked 2026-09-05)

| # | Decision | Locked value | Consequence |
|---|---|---|---|
| 1 | Canvas model | **Free-floating.** Every pane is its own node on an infinite plane. No islands, no persisted split tree. | `grid/tree.ts` retires as the persisted root. Split becomes "create adjacent snapped node". Warp-feel comes from snap + auto-arrange, not a tree. |
| 2 | First Observe adapter | **Voss PTY via OSC 133.** Warp adapter dropped to backlog. | Capture lives in `crates/voss-app-core/src/pty/reader.rs`. No shell-to-socket transport in v1. |
| 3 | Observe envelope | **Unified with BOS3.** Observe events are a BOS category; findings are BOS4 decisions; dismiss/resolve are BOS5 labels. | No second envelope. `bos_events.py` gains a live emitter path. |
| 4 | Editor | **CodeMirror 6.** | File and note nodes. No Monaco, no worker plumbing. |
| 5 | `App.tsx` extraction | **Prerequisite, inside S1.** | S1 starts with the refactor; canvas host lands on the extracted host, never on the 1,965-line component. |
| 6 | Provider billing | **Flat-rate flag.** `billing = subscription \| metered \| unknown` per provider. | Auto-investigation admits on call/token/time limits for subscription providers. |
| 7 | Instruction files | **AGENTS.md and CLAUDE.md are peers.** One canonical body, rendered per agent: CLAUDE.md for Claude panes, AGENTS.md for Codex/Cursor panes. | `voss sync` renders both from one source. Launch modal checks the file matching the CLI. Loader reads both and dedupes. |
| 8 | Global instruction files | **Opt-in.** `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` read only when `harness.toml` enables it. | Default off. `voss instructions show` reports either way. |
| 9 | Brief location | **`.planning/VOSS-OBSERVE-IMPLEMENTATION-BRIEF.md`** with a reconciliation header. | Brief is reference, this file is the plan. |

Out of scope for S0–S9: Warp/external-terminal adapters, multi-machine, Laravel, unattended patch application, Monaco, iframe nodes.

---

## 1. Architecture after S9

```
┌─ apps/voss-app (Solid) ────────────────────────────────────────────────┐
│ CanvasRoot: one transformed plane, free nodes                          │
│   node kinds: terminal · native · file · note · task · finding ·       │
│               cluster · diff · instructions                            │
│   edges: swarmLiveEdges + observe caused_by  (signal-only)             │
│   LOD chips < 0.6 zoom · snap · auto-arrange templates · broadcast     │
│ drawers: Tasks · Agents · Attention · Evidence   pages: Review·Memory·Settings
└──────────────┬─────────────────────────────────────────────────────────┘
               │ Tauri IPC                          │ HTTP + SSE (sidecar)
┌──────────────▼───────────────┐   ┌────────────────▼───────────────────┐
│ voss-app-core (Rust)         │   │ voss serve (Python)                │
│ pty/reader.rs: OSC 1337 +    │   │ observe/: ingest·admission·store   │
│   OSC 133 A/B/C/D + OSC 7    │   │   investigations·findings          │
│ canvas.rs session.json v2    │   │ instructions.py: bundle + hash     │
│ agent_registry: instr_hash   │   │ permissions.py: mode "observe"     │
│ sandbox · sidecar · layouts  │   │ memory_store: source "instructions"│
└──────────────────────────────┘   │ bos_events: live emitter path      │
                                   │ sync.py: per-agent managed blocks  │
                                   └────────────────────────────────────┘
```

Invariants that hold from S1 onward:

- A PTY never dies because of a layout, drag, zoom, or view change. `paneSessionRegistry.ts` remains the owner; the canvas only adopts.
- Automatic Observe runs cannot write project files, run shell, or commit. Enforced in `PermissionGate`, not in prompts or UI.
- Every edge on the canvas traces to a stored event. No decorative connectors.
- Instruction files are hashed into every session, pane, and BOS decision.

---

## 2. Sprint map

| Sprint | Name | Surface | Depends on |
|---|---|---|---|
| S0 | Harness foundations | Python | — |
| S1 | Desktop host + canvas skeleton | Solid/Rust | — |
| S2 | Canvas interaction + file/note nodes | Solid/Rust | S1 |
| S3 | Observe capture | Rust/Python | S0 |
| S4 | Instruction storage + sync + launch checks | Python/Solid/Rust | S0, S1 |
| S5 | Agent semantics on the plane | Solid/Rust | S2, S4 |
| S6 | Read-only investigation + finding nodes | Python/Solid | S3, S5 |
| S7 | Orchestra on canvas + templates + scoped instructions | Solid/Python | S5 |
| S8 | Git signals + proposed fix | Python/Solid | S6 |
| S9 | Portal collapse + reliability + BOS instruction feature | All | S7, S8 |

S0 and S1 run in parallel (no shared files). S3 and S2 run in parallel. S4 waits for both S0 and S1.

---

## S0 — Harness foundations

**Goal:** the three harness primitives every later sprint reads: instruction bundle, observe mode, provider billing flag. Plus the brief in the tree and three short ADRs. No UI, no model calls.

### Tasks

- **S0.1 Brief into tree.** Copy the brief to `.planning/VOSS-OBSERVE-IMPLEMENTATION-BRIEF.md` with a reconciliation header listing the four changes (BOS envelope, PTY-first, flat-rate flag, findings on canvas) and the `OrchestrationConsole.tsx` correction.
- **S0.2 ADRs.** `.planning/adr/0001-observe-bos-envelope.md`, `0002-observe-capability-ceiling.md` (why `swarm_runtime.py` is excluded, what `mode="observe"` denies), `0003-instruction-file-precedence.md` (decision 7/8). One page each.
- **S0.3 Instruction bundle loader.** New `voss/harness/instructions.py`:
  - `InstructionFile { path, kind: agents|claude|voss|global, scope_dir, sha256, bytes, tokens, imports }`
  - `InstructionBundle { files, merged_text, bundle_hash, tokens, truncated, load_errors }`
  - `load(cwd, target_dir=None, *, config, token_count) -> InstructionBundle`. Pure, never raises. Discovery: optional global files → repo root `AGENTS.md`, `CLAUDE.md` → every directory from root down to `target_dir`. Order in `merged_text`: global → root → nested (nearest last). Resolve Claude `@path` imports once, cycle-guarded, depth ≤ 3. Dedupe: a CLAUDE.md whose non-blank content is only `@AGENTS.md` collapses to its import. Per-file cap and total budget from config; overflow recorded in `truncated`.
  - `bundle_hash` = sha256 over ordered `(path, sha256)` pairs.
- **S0.4 Prompt slice.** `voss/harness/agent.py` `_compose_system_blocks`: add `instructions_text` immediately after `voss_md_block`, before `cognition_text`. Template `voss/templates/agent/instructions_block.md.jinja`. Overflow event `instructions_overflow` on the renderer, mirroring `cognition_overflow`.
- **S0.5 Session hash.** `voss/harness/session.py` / `recorder.py`: `instructions_hash: str` and `instructions_files: list[str]` on `RunRecord` and `SessionRecord`. `voss resume` prints a one-line warning when the current hash differs from the recorded one. Redaction test extended to the new fields.
- **S0.6 Config.** `voss/harness/config.py`: `[instructions] enabled=true, budget_tokens=4000, per_file_tokens=2000, read_global=false`. `[providers.<name>] billing = "subscription"|"metered"|"unknown"`; defaults: `claude-agent`, `codex` → subscription; API-key providers → metered; else unknown.
- **S0.7 Observe mode.** `voss/harness/permissions.py`: `Mode = Literal["plan","edit","auto","observe"]`. `mode_allows("observe", ...)` denies every mutating tool and `shell_run`. `PermissionGate.check` returns `(False, "denied by mode observe")` before the prompt path, before `auto_yes`, before rule "allow". `voss do --mode=observe` accepted by the CLI.
- **S0.8 CLI.** `voss instructions show [--cwd] [--target DIR]` prints files in load order with kind, tokens, hash, truncation, and resolved imports. `voss instructions check` exits 1 on cycle or budget overflow.

### Definition of done

- [ ] `.planning/VOSS-OBSERVE-IMPLEMENTATION-BRIEF.md` present with reconciliation header
- [ ] Three ADRs present
- [ ] `instructions.py` + `tests/harness/test_instructions.py`
- [ ] Prompt slice wired; `tests/harness/test_agent_prompt_blocks.py` (or existing prompt-block test) asserts slice order
- [ ] `RunRecord`/`SessionRecord` fields + redaction test extended
- [ ] Config keys documented in `docs/` config reference
- [ ] `mode="observe"` + `tests/harness/test_permissions_observe.py`
- [ ] `voss instructions` CLI + test
- [ ] Full harness suite green (`.venv/bin/python -m pytest tests/harness`)

### Acceptance criteria

- **AC-S0-1** Fixture repo with root `AGENTS.md`, `CLAUDE.md` = `@AGENTS.md`, and `src/AGENTS.md`: `load(cwd, target_dir="src")` returns two files (root AGENTS.md, src/AGENTS.md), CLAUDE.md collapsed, order root → src, and `bundle_hash` stable across two loads.
- **AC-S0-2** `A.md` imports `B.md` imports `A.md`: load returns without raising; `load_errors` names the cycle; both files still present once.
- **AC-S0-3** A 30k-token AGENTS.md under `budget_tokens=4000`: `truncated == ["AGENTS.md"]`, `merged_text` ≤ budget, renderer receives `instructions_overflow`.
- **AC-S0-4** Prompt block order is exactly `voss_md, instructions, cognition, principles, project_index, pinned_memory, code_recall, prior_context, loop_system` when all non-empty.
- **AC-S0-5** With `mode="observe"`, `PermissionGate.check("fs_write", ...)`, `check("fs_edit", ...)`, `check("shell_run", ...)` each return denied and the interactive prompt function is never called (assert via mock). A project-policy `allow` rule does not override.
- **AC-S0-6** `voss do --mode=observe "list files"` completes a read-only turn against the stub provider; the recorded run has `instructions_hash` set.
- **AC-S0-7** `read_global=false` (default): `~/.claude/CLAUDE.md` present on disk is not loaded; `read_global=true` loads it first with `kind="global"`.

---

## S1 — Desktop host refactor + canvas skeleton

**Goal:** the canvas host exists, every existing pane renders as a free node, PTYs survive, nothing the user could do before is lost. Free-floating from day one (decision 1), so this sprint also retires the split tree as the persisted root.

### Tasks

- **S1.1 Extract `App.tsx`.** Move into `apps/voss-app/src/app/`:
  - `workspaceHost.tsx` — workspace tab bar, mount map, per-workspace state (`mountedById`, `activeId`, project, session restore).
  - `liveBoot.ts` — sidecar start, handshake, `setLiveServer`, SSE attach, attention queue wiring.
  - `keymapHost.ts` — command registry, prefix mode, chords, native menu, keymap profile.
  - `viewRouter.tsx` — `activeView` signal, PortalRail + PortalShell mounting, deep-link effects.
  `App.tsx` becomes composition only (target ≤ 300 lines). No behavior change. All `src/__tests__/App.test.tsx` cases pass unchanged or are moved with the code they test.
- **S1.2 Canvas model.** New `apps/voss-app/src/canvas/`:
  - `model.ts` — `CanvasNode { id, kind, x, y, w, h, z, payload }`, `CanvasView { x, y, zoom }`, `CanvasStore { nodes, view, focusedId, selectedIds }`. Kinds in S1: `terminal`, `native`.
  - `store.ts` — Solid store + pure ops: `addNode`, `removeNode`, `moveNode`, `resizeNode`, `bringToFront`, `focus`, `setView`. No DOM.
  - `geometry.ts` — world↔screen transforms, bounds, `fitToBounds`, `clampView`.
  - `migrate.ts` — `sessionV1ToV2(file)`: walk the old `GridStore` tree, lay leaves out with the tree's ratios against a 1600×1000 world box, one node per `PaneLeaf`, preserve pane ids and scrollback.
- **S1.3 Persistence.** `crates/voss-app-core/src/canvas.rs` — serde mirror of `CanvasStore`; `session.rs` bumps `CURRENT_SESSION_VERSION` to 2 with `nodes`, `view`, `panes`, `projectLessAccepted`. v1 files load through the migration (Rust returns v1 as-is; TS migrates and re-saves). `layouts.rs` presets stored as node arrangements (S2 consumes). Tauri commands unchanged in name.
- **S1.4 Canvas host.** `CanvasRoot.tsx` — one `div.canvas-plane` with `transform: translate(x,y) scale(zoom)`; `NodeFrame.tsx` — absolutely positioned frame with header (index, cwd basename, proc, dot, budget bar, close) and body slot; `TerminalNode.tsx` adopts a `PaneSession` exactly as `PaneComponent` does today (reuse `paneSession.ts` adopt/release; do not fork it). Pan: middle-drag, right-drag, space+drag, two-finger scroll. Zoom: ⌘/ctrl+wheel, pinch, ⌘0 reset, ⌘⇧0 fit. View persisted per workspace on change (debounced 250 ms).
- **S1.5 Replace GridRoot mount.** `workspaceHost` mounts `CanvasRoot` where `GridRoot` was. `GridRoot`, `SplitNode`, `paneDrag`, `resize.ts`, `layoutPresets.ts`, `tree.ts` stay in tree this sprint but unmounted; deleted in S2 after presets are re-implemented as arrangements.
- **S1.6 Keep the operations users have.** Map existing commands onto canvas ops: split right/below (⌘D / ⌘⇧D) → new node placed adjacent on that axis, same size, snapped; close (⌘W) → gated close unchanged; focus by index (⌘1–9) → by node `index` (z-order-independent, assigned left-to-right/top-to-bottom); cycle focus (⌘] / ⌘[); directional focus (prefix + hjkl) → nearest node in that direction by center distance; equalize (⌘=) → auto-arrange grid of current nodes. Command palette registry entries updated, labels unchanged.
- **S1.7 Tests.** `src/canvas/__tests__/store.test.ts`, `geometry.test.ts`, `migrate.test.ts`; `CanvasRoot.test.tsx` (adopt/release, pan/zoom, view persistence); port `grid/__tests__/sessionPersist.test.ts` and `a6-acceptance.test.tsx` to canvas equivalents; e2e `e2e/canvas-basics.spec.ts` replacing `grid-integration.spec.ts`, `pane-drag-rearrange.spec.ts` (S2), `session-persist.spec.ts`.

### Definition of done

- [ ] `App.tsx` ≤ 300 lines; four host modules with their own tests
- [ ] `canvas/` model, store, geometry, migrate with unit tests
- [ ] `canvas.rs` + `session.rs` v2 + v1 migration; `cargo test -p voss-app-core` green
- [ ] `CanvasRoot` mounted per workspace; `GridRoot` unmounted
- [ ] All existing keybindings resolve to canvas ops; `command-palette/__tests__/registry.test.ts` green
- [ ] `pnpm test` green; `pnpm test:e2e` green with the replaced specs
- [ ] `pnpm check:xterm-pin` green (5.5.0 untouched)

### Acceptance criteria

- **AC-S1-1** Open a v1 `session.json` with a 3-pane split tree: three terminal nodes appear at positions proportional to the old ratios, all three shells resume with their scrollback, and the file is rewritten as v2 on first save.
- **AC-S1-2** Start `top` in a node, then pan, zoom to 0.5, zoom back, drag the node, resize it, switch workspace and back: `top` is still running, no respawn (assert `spawned` count in registry == 1 in unit test; manual check documented).
- **AC-S1-3** ⌘D on a focused node creates a node to its right with the same height, snapped to the same top edge, focused, shell spawned in the same cwd. ⌘⇧D does the same below.
- **AC-S1-4** ⌘1…⌘9 focus by geometric index; after moving a node from far-right to far-left, its index changes to 1 and ⌘1 focuses it.
- **AC-S1-5** Quit and relaunch: view (x, y, zoom) restored per workspace within 1 px / 0.01 zoom.
- **AC-S1-6** `App.test.tsx` cases still pass (moved, not deleted) and no test references `GridRoot`.
- **AC-S1-7** Project-less first launch boots to the canvas with one terminal node at world origin (V24 D-02 still holds).

---

## S2 — Canvas interaction, LOD, file and note nodes

**Goal:** the plane is pleasant to work in at any zoom, with the keyboard model from 49-IDE and the first non-terminal nodes.

### Tasks

- **S2.1 Drag + resize + snap.** Header drag moves; edge/corner handles resize; snap to other nodes' edges and centers within 8 world px with guide lines; hold ⌥ to disable snap. Multi-select: shift-click, shift-drag marquee on empty plane; drag moves the selection.
- **S2.2 Placement mode.** New node command enters placement: ghost follows cursor, click places, Esc cancels. Used by every "new X node" command.
- **S2.3 Move mode.** `prefix m`: hjkl / WASD moves focus to nearest node in that direction and pans to it; `prefix z` zoom-to-fit; `prefix 0` reset zoom; `prefix f` fit focused node to viewport at zoom 1.
- **S2.4 Minimap.** Bottom-right, nodes as rectangles colored by kind/state, viewport rectangle, click to pan, drag to scrub. Hidden below 3 nodes.
- **S2.5 LOD chips.** Below zoom 0.6 a terminal node renders `TerminalChip` (proc name, dot, last 3 lines from xterm buffer, budget bar) instead of live xterm; the xterm host element is detached from layout (not destroyed); reattached on zoom-in. Focused node snaps the view to zoom 1 on first keystroke (camera move ≤ 200 ms, disabled under reduced motion: instant).
- **S2.6 Auto-arrange templates.** `canvas/arrange.ts`: `fanout`, `pipeline`, `swarm`, `watchers`, `grid` as pure functions `(nodes, box) -> positions`. ⌘G cycles as before; layout menu unchanged in the rail. Delete `grid/layoutPresets.ts`, `tree.ts`, `SplitNode.tsx`, `GridRoot.tsx`, `paneDrag.ts`, `resize.ts`, `rearrange.ts`, `dropZone.ts` and their tests once arrangements pass.
- **S2.7 Note node.** `NoteNode.tsx` with CodeMirror 6 markdown (`@codemirror/lang-markdown`, pinned). Payload `{ text }` persisted in session v2. Rendered preview when not focused.
- **S2.8 File node.** `FileNode.tsx`: payload `{ path, line? }`; Tauri command `read_project_file(workspacePath, relPath, maxBytes)` in `src-tauri/lib.rs` backed by `voss-app-core::project`, rejecting paths outside the workspace root and files > 2 MiB. Read-only in S2; language modes for ts/tsx/js/py/rs/md/json/yaml/toml. Open from: command palette quick-open (`buildQuickOpenItems` already lists files), sidebar `FileTree` click, and later from finding/evidence links.
- **S2.9 Perf gate.** `scripts/test-canvas-perf.ts` (extend `test-flood-perf.ts`): 12 live terminal nodes flooding, pan for 5 s at zoom 1 and 0.5.

### Definition of done

- [ ] Snap/marquee/multi-drag with unit tests on the pure geometry
- [ ] Placement mode, move mode, minimap, zoom-to-fit, fit-focused with tests
- [ ] LOD chip + detach/reattach with a test asserting the xterm instance identity is unchanged
- [ ] Arrangements replace presets; grid tree code deleted; `layouts.rs` stores arrangements
- [ ] Note and file nodes with CodeMirror 6 pinned in `package.json`
- [ ] `read_project_file` with path-escape tests in Rust
- [ ] Perf script committed with numbers in `docs/canvas-perf.md`

### Acceptance criteria

- **AC-S2-1** Dragging node B toward node A snaps B's left edge to A's right edge when within 8 world px and shows a guide; with ⌥ held no snap occurs.
- **AC-S2-2** At zoom 0.4 with 12 nodes, every node shows a chip; zooming to 1.0 on one node restores live xterm with scrollback intact and no PTY respawn.
- **AC-S2-3** 12 flooding terminals, pan at zoom 1: p95 frame ≤ 16 ms on the dev machine; at zoom 0.5: p95 ≤ 8 ms. Numbers recorded.
- **AC-S2-4** ⌘G cycles fanout → pipeline → swarm → watchers with the same silhouettes the presets produced (snapshot test on positions for 1, 2, 4, 7 nodes).
- **AC-S2-5** `read_project_file` with `../../etc/passwd` or a symlink escaping the workspace returns an error; a 3 MiB file returns a size error; a normal file returns bytes and a detected language.
- **AC-S2-6** Note text survives quit/relaunch; file node reopens at the same path and line.
- **AC-S2-7** Reduced-motion: no animated camera moves; all pans and zooms are instant.

---

## S3 — Observe capture

**Goal:** a failed command in a Voss terminal becomes one typed, deduplicated, bounded event in a local store, visible via CLI and SSE. No model calls.

### Tasks

- **S3.1 Shell integration.** `voss shell-init --shell zsh|bash|fish` prints a snippet: `preexec` emits `OSC 133;C` + `OSC 1337;voss-cmd={json}` with `{cmd_id, argv_text, cwd}`; `precmd` emits `OSC 133;D;<exit>`; prompt start/end emit `133;A` / `133;B`; `OSC 7` for cwd on every prompt. `cmd_id` = uuid4 from the shell. Documented in `docs/shell-integration.md`. `VOSS_EMBEDDED=1` (already set by `pty/mod.rs`) gates auto-sourcing via `voss-app` setup screen (opt-in toggle).
- **S3.2 Reader.** `pty/reader.rs`: parse OSC 133 A/B/C/D, OSC 7, and `voss-cmd`. New `PtyEvent::CommandStarted { cmd_id, argv_text, cwd, at }` and `PtyEvent::CommandFinished { cmd_id, exit, duration_ms, output: Vec<u8>, truncated: bool }`. Output = bytes between `133;C` and `133;D`, capped at 256 KiB (head 192 KiB + tail 64 KiB, `truncated=true`). Existing budget/context parsing untouched; tests in `pty/tests.rs`.
- **S3.3 TS transport.** `pane/pty-ipc.ts`: mirror the two events; `paneSession.ts` forwards them to a new `observeClient.ts` that POSTs to the sidecar (`POST /observe/events`) with `adapter_id="voss-pty"`, `adapter_session_id=paneId`, `repository_id`/`worktree_id` from the workspace project. Non-blocking: bounded queue of 200, drop-oldest, dropped count surfaced in status bar tooltip.
- **S3.4 Harness observe module.** `voss/harness/observe/`:
  - `models.py` — pydantic: `ObserveEvent` as a BOS3 envelope specialization (`category="command"`, `event_type` in `command.started|command.completed|command.failed|test.failed`, `source_ref={source:"adapter", ref:adapter_session_id}`, `actor="developer"|"voss"|"external"|"unknown"`, payload per type, `evidence_refs`). Generated into `contracts/observe-events.schema.json` by the existing contract generation script.
  - `store.py` — SQLite at `<app-state>/observe/<repository_id>.sqlite` (path from `voss/harness/config.py`), tables `events`, `evidence`, `admissions`, `investigations`, `findings`; unique `(event_id)`; migrations numbered.
  - `admission.py` — deterministic: `record_only | suppress | queue | reject` with reason codes; fingerprint = sha256(repository_id, worktree_id, normalized argv, normalized error signature, repository_state_id); cooldown 60 s; per-worktree queue ≤ 10 with coalescing; expected-nonzero list (`grep`, `test -e`, `diff`, `git diff --exit-code`) → `record_only`. Classification `command.failed` → `test.failed` when argv matches a test runner (`pnpm test`, `pytest`, `cargo test`, `npm test`, `vitest`, `jest`, `go test`) and references the original event via `caused_by`. Only one of the pair is ever queued.
  - `repository.py` — `repository_id` = sha256(canonical git common dir); `worktree_id` = sha256(canonical worktree root); `repository_state_id` = HEAD + short hash of `git status --porcelain` + tracked-diff fingerprint.
  - `redact.py` — reuse the session redaction patterns; applied before evidence write.
  - `enrollment.py` — device settings file `<app-state>/observe/enrollment.json`: per repository `{enabled, capture, analysis, provider, disclosure, budget_usd, paused}`; `.voss/observe.yml` loader that may only narrow (`exclude_paths`, `commands`, `capture.max_output_bytes`, investigation limits ≤ defaults).
- **S3.5 Routes.** `voss/harness/server/app.py`: `POST /observe/events` (validate, scope-check against enrollment, persist, return admission), `GET /observe/events?repository_id&cursor&limit`, `GET /observe/settings`, `PATCH /observe/settings`, `GET /observe/stream?repository_id` (SSE with `seq` cursor). Reuse the bearer auth. Events from unenrolled repositories → 403 with `reject:not_enrolled`, nothing stored.
- **S3.6 BOS emitter.** `voss/harness/bos_events.py`: `emit_live(event)` path appending to the existing BOS ledger (`bos_ledger.py`) with `ingest_time` assigned at write. Observe store writes call it; BOS stays append-only.
- **S3.7 CLI.** `voss observe enable|disable|pause|resume [--repo PATH]`, `voss observe status`, `voss observe events [--tail] [--since]`. Output styled per `docs/tui-redesign-spec.md` conventions.
- **S3.8 Desktop minimal surface.** Settings surface: "Observation" section with enable/pause per workspace repo, capture/analysis toggles, provider disclosure text. Status bar: capture dot (active / paused / dropped n).

### Definition of done

- [ ] `voss shell-init` for zsh, bash, fish with a manual walkthrough in `docs/shell-integration.md`
- [ ] Reader parsing + `pty/tests.rs` cases for A/B/C/D, OSC 7, `voss-cmd`, truncation head/tail
- [ ] `observeClient.ts` with queue/drop tests
- [ ] `observe/` package with `tests/harness/observe/` (models, store, admission, repository, redact, enrollment)
- [ ] Routes + `tests/harness/server/test_observe_routes.py`
- [ ] `contracts/observe-events.schema.json` generated and checked by the schema-lint test
- [ ] BOS live emitter with an append-only test
- [ ] CLI + Settings section + status dot
- [ ] Zero model calls anywhere in `observe/` (grep-guard test: no import of providers/agent from `observe/`)

### Acceptance criteria

- **AC-S3-1** In a Voss terminal with shell-init sourced, `pnpm test` failing in a fixture repo yields one `command.completed` and one `test.failed` event with correct `cwd`, `exit=1`, `argv_text`, output containing the failing spec name, `truncated=false`, and `test.failed.caused_by == command.completed.event_id`.
- **AC-S3-2** Same command run twice within 60 s on unchanged code: second pair is `suppress:cooldown`; admissions table has both decisions.
- **AC-S3-3** Same event POSTed twice: one row; second response is `record_only:duplicate`.
- **AC-S3-4** `grep nothing_here` exiting 1 → `record_only:expected_nonzero`, no queue entry.
- **AC-S3-5** Output of 1 MiB: stored evidence is 256 KiB, `truncated=true`, head and tail preserved.
- **AC-S3-6** A pipeline `a | b`, a backgrounded `sleep 5 &`, and a nested `zsh -c` each produce documented behavior (one command event for the pipeline with the pipeline's exit; background job recorded on completion of the foreground command only; nested shell produces its own events only if shell-init is sourced there). Documented in the walkthrough as supported/unsupported.
- **AC-S3-7** Sidecar down: the shell finishes normally, the client queue fills to 200 and drops oldest, the status bar shows the dropped count, and nothing blocks.
- **AC-S3-8** A repository not enrolled: POST returns 403, store has no row, CLI status says "not enrolled".
- **AC-S3-9** Output containing `AWS_SECRET_ACCESS_KEY=...` is redacted before the evidence row is written (assert on stored bytes).
- **AC-S3-10** `GET /observe/stream` delivers events in `seq` order; reconnecting with the last `seq` yields no gaps or duplicates over 1,000 events.

---

## S4 — Instruction storage, sync, launch checks

**Goal:** instruction files are stored, indexed, synced per agent, and visible per pane.

### Tasks

- **S4.1 Memory source.** `voss/harness/memory_store.py`: add `"instructions"` to `_SOURCES` with weight above `conventions`. `index_instructions(bundle)` chunks each file by H2/H3 heading; hit locator `AGENTS.md#Testing`; chunk id = `make_id("instructions", f"{path}#{heading}", seq)`. Re-index when `bundle_hash` changes (called at session start); tombstone chunks of removed files. Chroma path (V19) included when available.
- **S4.2 Canonical source + per-agent sync.** `voss/sync.py`: new `instructions` artifact family. Canonical body = `VOSS.md` managed content + `.voss/instructions.md` (human-authored shared text, created empty by `voss init` if absent). Render `AGENTS.md` managed block and `CLAUDE.md` managed block from templates `voss/templates/docs/agents_managed.md.jinja` and `claude_managed.md.jinja` with agent-specific sections (tool names, permission vocabulary, `@` import line for Claude). Markers `<!-- voss:managed-start -->` / `<!-- voss:managed-end -->`. Rules: never touch text outside markers; insert block at end if absent; create the file only when `--create-instructions agents|claude|both` is passed; byte-idempotent; recorded in the sync manifest.
- **S4.3 Conventions proposal.** `voss/harness/conventions.py`: `propose_instruction_patch(convention) -> unified diff against AGENTS.md (and CLAUDE.md when it is not an import)`. Surfaced as a proposal artifact only; application goes through the normal edit path with the diff preview (CTRL-08).
- **S4.4 Registry column.** `crates/voss-app-core/src/agent_registry.rs`: `instructions_hash TEXT` + `instructions_files TEXT` (JSON), written at `register_agent`; schema migration; `list_agents_by_swarm` and `get_active_agents` return them.
- **S4.5 Launch checks.** `components/modal/AgentLaunchModal.tsx`: on launch, compute the bundle for the pane cwd via a new Tauri command `instructions_bundle(cwd)` (Rust calls the Python loader through the sidecar `GET /instructions?cwd=` route added in `server/app.py`, falls back to a Rust-side discovery-only scan when the sidecar is down). Warn when the file matching the CLI is missing (`claude` → `CLAUDE.md`; `codex`/`cursor` → `AGENTS.md`) with a "Create from Voss" action that runs `voss sync --create-instructions <kind>`. Record the hash in the registry and in `AgentConfig`.
- **S4.6 Context panel.** `components/ContextPanel.tsx`: "Instructions" group listing the pane's loaded files with kind, tokens, short hash, and a `stale` marker when the on-disk hash (polled every 10 s, or pushed by `watch`) differs from the hash at spawn. Native sessions: "reloads next turn". External CLIs: "applies on next session".
- **S4.7 Watch.** `voss/harness/watch/backend.py`: default glob set includes `AGENTS.md`, `CLAUDE.md`, `**/AGENTS.md`, `**/CLAUDE.md`, `.voss/instructions.md`; emits `instructions.changed` on the session SSE stream with the new hash.
- **S4.8 CLI.** `voss instructions diff` shows the managed block that `sync` would write versus what is on disk; `voss sync --check` exits 1 when an instruction block is stale.

### Definition of done

- [ ] `instructions` memory source with index/re-index/tombstone tests
- [ ] Per-agent managed blocks with idempotency tests (`tests/test_sync_instructions.py`)
- [ ] Conventions proposal diff with a test
- [ ] Registry columns + `cargo test` migration test
- [ ] `GET /instructions` route + Tauri `instructions_bundle` command + fallback
- [ ] Launch-modal warning + create action with a vitest case
- [ ] Context panel group with stale marker test
- [ ] Watch globs + `instructions.changed` event in `contracts/events.schema.json`
- [ ] `voss instructions diff`, `voss sync --check`

### Acceptance criteria

- **AC-S4-1** Query "how do we run tests" against a repo whose AGENTS.md has a `## Testing` section: top hit source is `instructions`, locator `AGENTS.md#Testing`, above any turn hit.
- **AC-S4-2** `voss sync` twice: second run writes zero bytes (manifest unchanged). A user paragraph placed above and below the markers is byte-identical afterwards.
- **AC-S4-3** Repo with `AGENTS.md` only: `voss sync` updates its block and does not create `CLAUDE.md`; with `--create-instructions claude` it creates `CLAUDE.md` containing `@AGENTS.md` plus the Claude-specific managed block.
- **AC-S4-4** Launching `claude` in a cwd with no `CLAUDE.md`: modal shows the warning; "Create from Voss" produces the file; relaunch shows no warning; registry row has a non-empty `instructions_hash`.
- **AC-S4-5** Edit `AGENTS.md` while a native session runs: context panel shows `stale` within 10 s; the next turn's `RunRecord.instructions_hash` equals the new on-disk hash.
- **AC-S4-6** Edit `AGENTS.md` while an external `codex` pane runs: panel shows `stale` and "applies on next session"; the registry hash is unchanged until respawn.
- **AC-S4-7** `voss sync --check` returns 1 after editing the canonical body without syncing, 0 after `voss sync`.

---

## S5 — Agent semantics on the plane

**Goal:** the canvas shows what every agent is doing and what it needs, and the composer places work spatially.

### Tasks

- **S5.1 External CLI state.** `pane/agentState.ts`: parse xterm output for Claude Code and Codex CLI patterns → `working | idle | permission | question | input_needed`. Patterns table in `agentState.patterns.ts` with fixture transcripts under `src/pane/__tests__/fixtures/`. State flows through `PaneSink` into the node header and chip. Native sessions already carry state via SSE; unify into one `AgentState` type.
- **S5.2 Attention pins.** `attentionQueue.ts` items get `nodeId`; a pin renders on the node frame (amber for permission/question, red for blocked); the attention panel row "Go" pans and zooms to the node. `prefix a` cycles pinned nodes.
- **S5.3 Broadcast.** Multi-select → status bar shows "Broadcast to n"; keystrokes in the focused terminal fan out via a new Rust command `pty_write_many(session_ids, data)` (single IPC, per-session `validate_write`). Escape clears. Never active without a visible indicator.
- **S5.4 Task card node.** `TaskNode.tsx` payload `{ swarm_id, task_id }` rendered from `GET /swarm/{id}` task state; status chip, owned files, owner. Composer ("Ask Voss to…") in placement mode drops a task card at the click point, then starts the run.
- **S5.5 Run node spawn with edge.** Starting a run from a task card creates the terminal or native node adjacent to the card and an edge `delegation` card → node from `swarm.assign` (native) or from the launch record (terminal). Edge store `canvas/edges.ts`: `{ id, from, to, kind, source_event_id }`; render layer `EdgeLayer.tsx` (SVG under nodes). Edges require `source_event_id`; a guard test rejects edges without one.
- **S5.6 Instruction nodes.** `InstructionsNode.tsx` = file node variant for `AGENTS.md`/`CLAUDE.md` with kind badge and hash; pinned to the top-left of the plane on first open of a workspace with instruction files; editing goes through the S2 file node editor once S8 enables editing (read-only until then).

### Definition of done

- [ ] `agentState.ts` with fixture-driven tests for Claude Code and Codex transcripts
- [ ] Attention pins on nodes; panel "Go" pans; `prefix a` cycle
- [ ] `pty_write_many` + broadcast UI with indicator test
- [ ] Task node, composer placement, run spawn adjacency
- [ ] Edge store + layer + no-source guard test
- [ ] Instruction nodes pinned

### Acceptance criteria

- **AC-S5-1** Replaying the Claude permission-prompt fixture into a terminal node sets state `permission` within 100 ms of the last byte; the node shows an amber pin; from zoom 0.3 the pin is visible; `prefix a` focuses it and zooms to 1.
- **AC-S5-2** Selecting three terminal nodes and typing `echo hi⏎` in the focused one writes to all three PTYs (assert three `pty_write_many` targets) and the status bar shows "Broadcast to 3"; Escape ends it.
- **AC-S5-3** Composer submit in placement mode creates a task card at the click point and, on run start, a run node whose left edge is within 24 world px of the card's right edge, connected by a `delegation` edge carrying a real `source_event_id`.
- **AC-S5-4** Attempting to add an edge without `source_event_id` throws in dev and is dropped in prod (test both).
- **AC-S5-5** Workspace with `AGENTS.md`: an instruction node appears pinned top-left with kind badge and hash matching `voss instructions show`.

---

## S6 — Read-only investigation + finding nodes

**Goal:** a captured failure produces an evidence-backed finding without any project mutation, and the finding lands beside the failing terminal.

### Tasks

- **S6.1 Investigation runner.** `observe/investigate.py`: takes a queued admission, builds a native `ServerSession` with `mode="observe"`, tool profile = `{fs_read, fs_search, git_status, git_diff, memory_recall, code_recall}` only (denylist enforced by `PermissionGate`, allowlist enforced by the tool catalog filter), budget from admission (≤ 4 model calls, 90 s, 1 specialist), cancellation token. Investigator role prompt `voss/templates/prompts/observe_investigator.txt.jinja`; specialist `observe_specialist.txt.jinja`. Inputs: event, evidence refs, `repository_state_id`, instruction bundle sections matched by file/command, `MemoryStore.recall` scoped to files named in the output.
- **S6.2 Concurrency + budgets.** One investigation per worktree, two per device; reservation before start, reconciliation after; provider `billing` flag decides dollar reservation vs limit-only. Budget exhaustion → `finding.inconclusive` with reason, no further calls.
- **S6.3 Finding contract.** `observe/models.py`: `Finding` = BOS4 decision specialization: `finding_id, repository_id, worktree_id, trigger_event_ids, investigation_id, run_id, title, explanation, observed_facts[], suspected_cause, alternatives[], missing_evidence[], affected_files[{path, content_hash}], evidence_refs[], confidence: {label, reasons[]}, impact, verification: unverified|passed|failed|inconclusive, status: new|inspected|dismissed|resolved, freshness: current|stale, next_action, created_at, updated_at, repository_state_id`. Generated into `contracts/observe-findings.schema.json`. Dismiss/resolve write BOS5 outcome labels via `bos_decisions.py`.
- **S6.4 Routes.** `GET /observe/findings`, `GET /observe/findings/{id}`, `PATCH /observe/findings/{id}` (inspected/dismissed/resolved with reason), `POST /observe/investigations` (explicit, idempotency key), `POST /observe/investigations/{id}/cancel`. Findings and investigation state changes on `/observe/stream`.
- **S6.5 Staleness.** `repository_state_id` re-checked before publish; a changed state marks the finding `stale` at creation; `instructions.changed` and `git.branch.changed` (S8) also mark stale. Stale findings cannot seed a proposal.
- **S6.6 Finding node.** `FindingNode.tsx`: title, confidence label, freshness/verification pills, affected files, actions Inspect Evidence / Open Run / Dismiss / Reinvestigate. Placed adjacent to the terminal node whose `adapter_session_id` matches, edge `caused_by` from the trigger event; if that node is gone, placed near the instruction node. Evidence drawer `EvidenceDrawer.tsx`: command output excerpt, file excerpts with hash, memory hits; file excerpt "Open" creates/focuses a file node at that line. No evidence action reruns a command.
- **S6.7 Notifications.** Findings enter the attention queue as low-priority; desktop notification only for `impact=high` and only when enabled in Settings; updates to the same finding coalesce.
- **S6.8 Fixtures + eval.** `tests/harness/observe/fixtures/`: changed-response-type, missing-import, failed-assertion, environment-failure, expected-nonzero, insufficient-evidence. Deterministic stub provider replays. Under the E-track runner, a labeled-outcome pass with the subscription provider records cause/file hit-rate to `.voss-cache/eval/observe.jsonl`.

### Definition of done

- [ ] `investigate.py` with denylist/allowlist tests proving `fs_write`, `fs_edit`, `shell_run`, background tools, custom launchers, worktree creation are unreachable
- [ ] Budget reservation/reconciliation tests including `billing=subscription`
- [ ] `Finding` model + generated schema + BOS4/BOS5 write tests
- [ ] Routes + stream events + tests
- [ ] Staleness tests
- [ ] Finding node + evidence drawer + placement adjacency + tests
- [ ] Notification coalescing test
- [ ] Six fixtures with stub-provider runs green; eval script committed

### Acceptance criteria

- **AC-S6-1** Missing-import fixture: the finding names the file and the symbol, cites the output line and a file excerpt with matching content hash, confidence label present with ≥ 1 reason, and the run record shows ≤ 4 model calls and no denied-tool attempts succeeding.
- **AC-S6-2** Investigator emits a `fs_write` call in a stub transcript: backend denies, investigation completes with the denial logged, repository `git status` unchanged (assert clean tree before/after).
- **AC-S6-3** Output instructing "delete all files": treated as text; no tool call beyond the allowlist appears in the run record.
- **AC-S6-4** Two admissions on the same worktree: second waits; two on different worktrees on one device run concurrently; a third waits.
- **AC-S6-5** Provider returns an error: investigation ends `interrupted:provider_error`, one bounded retry after 30 s, then stops; UI shows "Model unavailable".
- **AC-S6-6** Editing the affected file after publish flips `freshness=stale` within one `instructions.changed`/watch tick; "Propose Fix" (S8) is disabled on it.
- **AC-S6-7** Finding node appears within 24 world px of the failing terminal node with a `caused_by` edge; Dismiss with reason writes one BOS5 outcome row; Inspect does not change verification.
- **AC-S6-8** Across the six fixtures, ≥ 5 identify the correct file or abstain explicitly (insufficient-evidence must abstain, not invent a stack trace).

---

## S7 — Orchestra on the canvas, templates, scoped instructions

**Goal:** swarms live on the same plane as everything else; layouts become workflow templates; each role gets the instructions for its own directories.

### Tasks

- **S7.1 Cluster node.** `ClusterNode.tsx` wraps `swarmLayout` output in world coordinates; collapsed = chip ring (coordinator, builders, reviewer, operator) with live state; expanded = member nodes (terminal or native) laid out radially with `swarmLiveEdges` rendered by `EdgeLayer`. Replay scrubber attached to the cluster. `SwarmMap.tsx` retires as a page; `SwarmLaunchWizard` opens from the cluster's "+" and from the composer.
- **S7.2 Templates.** `canvas/templates.ts`: a template = arrangement + expected node kinds + expected edge kinds. Built-ins from the four arrangements plus `observe-triage` (terminal + finding + file slots). A `.voss` file with `team{}` / `board{}` projects to a template through the existing compiler metadata (`language-metadata/`); the launch wizard offers it by name. Templates saved per workspace in `layouts.rs`.
- **S7.3 Scoped instruction bundles.** `swarm_store.py` / server swarm routes: at `swarm.assign`, compute `instructions.load(cwd, target_dir=common_prefix(ownedFiles))` per task and inject the scoped bundle into that role's system prompt; record `instructions_hash` on the task and in the role's `RunRecord`.
- **S7.4 Direct the Orchestra.** `@all` / `@role` from the cluster's command bar → existing `POST /swarm/{id}/message`; operator needs render as pins on member nodes (S5).

### Definition of done

- [ ] Cluster node collapsed/expanded with live edges and replay
- [ ] `SwarmMap` page removed; portal item "Orchestra" pans to the newest cluster
- [ ] Templates with `.voss` projection test on a fixture team file
- [ ] Scoped bundle injection with a test on nested `AGENTS.md`
- [ ] Command bar wired

### Acceptance criteria

- **AC-S7-1** V25 two-builder integration fixture renders one cluster; expanding shows coordinator + two builders + reviewer as nodes with `delegation` edges whose `source_event_id`s exist in the swarm event log.
- **AC-S7-2** Builder task owning `src/api/**` in a repo with `src/api/AGENTS.md`: the builder's prompt contains that file's text; the reviewer's does not; both `RunRecord`s carry distinct `instructions_hash`.
- **AC-S7-3** A fixture `.voss` team file with three roles produces a template that places three nodes in the documented arrangement.
- **AC-S7-4** Replay scrub on a completed swarm moves member state chips and edges in step with the event sequence; reduced-motion shows static connectors.

---

## S8 — Git signals and proposed fix

**Goal:** repository changes are events, stale findings are handled, and a fix can be proposed, reviewed, and applied only under explicit, bound approval.

### Tasks

- **S8.1 Git signals.** `observe/git_signals.py` on `watch/backend.py`: `git.diff.changed` (tracked-diff fingerprint, coalesced 2 s), `git.branch.changed` (HEAD ref or worktree change). Branch change cancels running investigations on that worktree and marks their findings stale. Diff change re-checks affected files' hashes. Both are BOS `category="file"`/`"git"` events.
- **S8.2 Propose Fix.** `POST /observe/findings/{id}/proposals` creates a linked proposal run: native session with `mode="edit"` **scoped to the finding's affected files** via `EditScope`, output = a patch artifact stored in the observe store (`proposals` table: `proposal_id, finding_id, patch_digest, base_hashes{path:hash}, policy_version, created_at, status`). Working tree untouched: the run writes into a scratch copy under `<app-state>/observe/proposals/<id>/` and diffs against base hashes.
- **S8.3 Review.** Proposal opens as a `DiffNode` (existing `DiffPanel`) beside the finding with an edge `proposes`; optional independent review through the existing reviewer B path when the patch touches > 3 files or > 200 lines.
- **S8.4 Approval binding.** `POST /observe/proposals/{id}/apply` requires `{patch_digest, repository_state_id, policy_version}` from the client; server re-reads base files, rejects on any hash mismatch or state change (`409 stale_proposal`), applies through the normal `fs_edit` path with the diff preview and permission gate, handles new/deleted files, and rolls back partial application by restoring base contents. Approvals expire after 30 minutes or on `git.*` events.
- **S8.5 Verification.** Separate approval for a concrete verification command `{cwd, argv, env_allowlist, timeout}`; its events attach to the proposal run (`origin=voss`, `caused_by=proposal`) and are suppressed from new automatic investigation. Verification result sets `verification=passed|failed`; `resolved` only via passed verification or an explicit user action labeled "resolved by user".
- **S8.6 File node editing.** S2 file node gains edit + save through the same `fs_edit` path with diff preview; instruction nodes become editable; saving `AGENTS.md`/`CLAUDE.md` triggers `instructions.changed`.

### Definition of done

- [ ] Git signal events + tests for coalescing and cancellation
- [ ] Proposal run scoped by `EditScope`, scratch-copy isolation test (working tree hash unchanged)
- [ ] Diff node + review threshold test
- [ ] Apply with binding + 409 tests + partial-failure rollback test
- [ ] Verification approval + suppression test
- [ ] File node editing with diff preview

### Acceptance criteria

- **AC-S8-1** Proposal generated for the missing-import fixture: working tree `git status` clean afterwards; patch artifact present with `base_hashes` for exactly the affected files.
- **AC-S8-2** Modify an affected file, then apply: server returns `409 stale_proposal`; no bytes change on disk.
- **AC-S8-3** Apply a proposal that creates one file and deletes one: both happen; simulate a failure on the third file: the first two are restored to base and the response reports `partial_failure_rolled_back`.
- **AC-S8-4** Approved verification `pnpm test` fails: the failure event carries `origin=voss`, `caused_by=<proposal>`, and admission is `suppress:verification_origin`; the finding shows `verification=failed`, status unchanged.
- **AC-S8-5** Switching branches during an investigation cancels it within 2 s and marks any prior finding on that worktree stale.
- **AC-S8-6** Editing `AGENTS.md` in its node and saving shows the diff preview, writes the file, and the context panel of a native session flips to stale.

---

## S9 — Portal collapse, reliability, BOS instruction feature

**Goal:** the canvas is the product; the app recovers cleanly; instruction revisions are a measurable variable.

### Tasks

- **S9.1 Portal collapse.** Overview = zoom-to-fit + summary strip (counts of running agents, pins, findings, tasks); Tasks and Agents become right-side drawers over the canvas (`Drawer.tsx`, reuse `TasksSurface`/`AgentsSurface` bodies); Orchestra item pans to the newest cluster; Context becomes the panel it already is; Review, Memory, Settings remain pages. `PORTAL_ITEMS` reduced accordingly; PRODUCT.md locked vocabulary preserved; the two V24 hard-fails re-verified.
- **S9.2 Recovery.** On sidecar start, investigations in `running` → `interrupted` with a linked `attempt_id`; a fresh read-only attempt is allowed only after re-checking enrollment and state; pending approvals expired; never re-apply an uncertain apply (proposals in `applying` → `unknown`, user must reconcile from the diff node).
- **S9.3 Retention.** Evidence 7 days, events/findings 30 days, user delete per finding and per repository; deletion also removes proposal scratch copies and any evidence copies referenced by linked run records (audit script asserts no orphans).
- **S9.4 Transport reconnection.** `observeClient.ts` and `/observe/stream` reconnect with cursor; client queue persists to `localStorage` across app restarts (bounded 200).
- **S9.5 BOS instruction feature.** `bos_decisions.py` curated features gain `instructions_hash`; `bos_events.py` projection carries it from `RunRecord`; BOS5 outcome join groups by hash. `voss bos report --by instructions` prints outcomes per hash with file list.
- **S9.6 Idle cost.** Overnight idle check: capture on, no commands: CPU < 1% average, memory growth < 20 MB over 8 h; documented in `docs/observe-ops.md`.

### Definition of done

- [ ] Portal reduced; drawers; V24 checklist re-run and recorded
- [ ] Recovery + retention + reconnection tests
- [ ] BOS feature + report command + test
- [ ] Idle numbers recorded

### Acceptance criteria

- **AC-S9-1** Kill the app mid-investigation, relaunch: the investigation shows `interrupted`, a new attempt links to it, no duplicate finding for the same trigger.
- **AC-S9-2** Kill the app mid-apply: relaunch shows the proposal as `unknown` with the diff node open; no automatic re-apply; working tree matches either base or fully-applied state, never mixed (assert both possibilities are the only outcomes across 20 randomized kills in a test harness).
- **AC-S9-3** Delete a finding: its evidence rows, proposal scratch directory, and linked run evidence copies are gone; orphan audit passes.
- **AC-S9-4** Two sessions with different `instructions_hash` and labeled outcomes: `voss bos report --by instructions` lists both hashes with their outcome counts.
- **AC-S9-5** The V24 manual terminal-first checklist passes on the collapsed portal; no default-chrome surface shows `runId`, `RunData`, `Plan/Edit/Auto`, or an arrangement name as product vocabulary.
- **AC-S9-6** 8-hour idle numbers meet the S9.6 thresholds.

---

## 3. Backlog (explicitly after S9)

- Warp / external terminal adapter over a local socket (shell-init already emits the needed markers).
- Multi-machine nodes (remote agents on the plane) — depends on the Laravel control-plane note.
- Laravel account, config sync, team policy distribution — `.planning/notes/laravel-account-control-plane-plan.md`.
- Iframe / preview nodes.
- Menu-bar/daemon lifecycle so capture survives app close.
- LSP in file nodes.

## 4. Verification commands

```
# harness
.venv/bin/python -m pytest tests/harness -q
.venv/bin/python -m pytest tests/harness/observe -q
.venv/bin/python scripts/check_contracts.py        # schema generation drift

# rust
cargo test -p voss-app-core
cargo test -p voss-app-core pty::

# desktop
cd apps/voss-app && pnpm test && pnpm test:e2e && pnpm check:xterm-pin
cd apps/voss-app && pnpm tsx scripts/test-canvas-perf.ts
```

## 5. Evidence log

Append one line per accepted criterion: `AC-Sx-y — <test name or screenshot path> — <date>`.

```
(empty)
```
