# Roadmap: Voss - Behavioral OS Foundation + Harness/ADE Runtime

**Created:** 2026-05-10
**Mode:** Behavioral OS implementation track -> harness/ADE/swarm substrate -> team control plane -> learning/eval platform
**Granularity:** **BOS-prefixed Behavioral OS implementation phases (BOS1-BOS18)** · M-prefixed milestone phases · T-prefixed gap-closure phases · **A-prefixed voss-app phases** (terminal-grid desktop ADE in `apps/voss-app/`) · **O-prefixed ADE-orchestration phases** (Caged Autonomous Eng Team — design in `.planning/ORCHESTRATION-PLAN.md`) · **F-prefixed substrate feature phases** (v1 Layer 2 features — design in `.planning/Feature Plan.md`) · **V-prefixed agent-org phases** (Agent Engineering Organization Layer — design in `.planning/docs/ORCHESTRATION_LAYERS.md`; supersedes the O-track + absorbs M13) · **E-prefixed internal proof phases** (on-demand e2e + eval suite, internal-only, subscription-backed models — decisions in `.planning/notes/e-track-eval-decisions.md`; supersedes M5 eval scope)
**Requirements covered:** v0.2 BOS implementation requirements 48 / 48; v0.1 locked requirements 64 / 64; v0.2 phases M8–M15 + T1–T8 (T-counts locked, M11–M15 TBD by SPEC.md); voss-app phases A1–A13 (counts TBD by SPEC.md); agent-org phases V0–V25 (requirements namespaced `V*`, locked per V{n}-SPEC.md)
**Source:** BOS milestone discussion (2026-06-18), BOS track restart (2026-06-20), `.planning/seeds/SEED-001-coordination-bus.md`, V25 server-native swarm context, `.vscode/voss_v_0_1_scope_lock.md` (v0.1), `.planning/seeds/` (v0.2 M-phases), `.planning/notes/daily-driver-punch-list.md` (T-phases), `apps/voss-app/CONCEPT.md` + `apps/voss-app/FEATURES.md` (A-phases)
**Last updated:** 2026-06-20 - restarted BOS as one **BOS1-BOS18 implementation track** with traditional BOS-prefixed phase and plan names; split-prefix tracks are deleted as active tracks, and their useful implementation context is folded into BOS3. | 2026-06-17 — added **V25 Server-Native Swarm Runtime** (server+SSE swarm coordination superseding A13's filesystem-as-IPC transport now that Voss has a real daemon; SwarmStore + spawn-gating + PermissionGate ownership enforcement + memory-scoped recall + per-role model routing; `.voss/swarm/` files demoted to audit layer; A13-01 file schema retained, A13-02..06 ⊘ superseded; pairs with V24 Swarm Map as runtime↔observability; SPEC pending). | 2026-06-14 — added **V24 ADE Product Revamp + Swarm Observability** (terminal-first workbench + Linear-like run/agent portal + mission-control swarm map; preserves Warp-style terminal grid while making Voss runs, review, context, budget, scope, and live agent interactions digestible; 8 provisional plans, SPEC pending; depends on V14/V15 and should consume V17/V20 where available). | 2026-06-12 — added **V23 Retrieval-Aware Memory Ranking & Hygiene** (froots.ai/memory teardown: retrieval telemetry → recency×frequency rescore → retrieval-aware eviction, pre-fusion quality floor, mirror reindex/drift gate, pinned always-inject tier; 6 provisional plans, SPEC pending; coordinates with V21 dual-store). | 2026-06-10 — added **E1–E5 Internal Proof Suite** track (on-demand, internal-only e2e + evals proving the product works; subscription-backed flagship models via existing voss auth; hybrid deterministic+LLM-judge scoring; surfaces × repo-shapes matrix; M5 eval scope superseded into E1/E2, packaging smoke M5-06 stays shipped; exploration: `.planning/notes/e-track-eval-decisions.md`). | 2026-06-08 — **V13.4 (C ABI/Schema Doc) ✅ COMPLETE** (1/1 plan, doc-only: `docs/native-embedding.md` native/C consumption reference + `docs/check-native-embedding-refs.sh` refs gate; VSDK-C-01..06; C headers/FFI deferred w/ trigger; zero code). | 2026-06-08 — **V13.3 (Go Local/Headless Client SDK) ✅ COMPLETE** (6/6 plans; `sdk/go/` generated+drift-gated types, 21-member Decode, typed REST/SSE, spawn/attach no-orphan supervisor, permission helper, no-FFI guard; full suite + real-server TestMain green; VSDK-GO-01..08). | 2026-06-07 — moved the contract snapshot + codegen substrate + CI drift gate from V13 into **V13.1** (the first client owns the artifact); V13 is now **docs-only** (VSDK-01..06: strategy/matrix/tiers + `sdk.md`↔`PROTOCOL.md` reconcile + Python/M7 linkage, no code/CI, doable anytime); **V13.1** produces the committed `openapi.json` + event-union snapshot that **V13.2–.4** reuse. | 2026-06-06 — added **V13 External Developer SDK Surfaces** + per-language sub-phases **V13.1 TS / V13.2 Rust / V13.3 Go / V13.4 C-ABI-doc**, each with its own SPEC; deep reader SDKs gated on V1/V3/V4/V9. | 2026-06-05 — added **V0–V12 Agent Engineering Organization Layer** track (design: `.planning/docs/ORCHESTRATION_LAYERS.md`). V supersedes the O-track (V3→O2, V4→O1, V5→O3, V6→O4, V7→O5, V9→O6 — O1–O6 archived-as-superseded; O6's ready plans re-point to V9) and absorbs M13 into V8. Requirement IDs namespaced `V*` (VRFM/VCAP/VPRIN/VTEAM/VTREE/VBOARD/VREV/VEM/VMAG/VADE/VSAFE) to avoid LANG/MAG/ADE clashes with M3/M13/A12. | 2026-06-02 — H0.2 doc reconciliation: verified T1–T5 implemented in code **with tests** (iteration loop, streaming, interrupt, parallel reads/multi-edit, network+MCP, prompt caching, shell ergonomics); flipped their stale `TBD` success-criteria cells to **Implemented**. Added `.planning/HYBRID-REFACTOR-PLAN.md` (H0–H7, supersedes RUST-PORT-PLAN) + `.planning/PROTOCOL.md` (wire contract). | 2026-05-21 — planned F2 (Hybrid Semantic Search), locking FSRCH-01..04 to 3 plans / 3 waves. | 2026-05-19 — inserted A8 (Workspaces, UX Polish, Theming); old A8→A9, A9→A10, A10→A11; A-track now A1–A11. | 2026-05-19 — added F1–F6 substrate feature phases (v1 Layer 2); design in `.planning/Feature Plan.md`. | 2026-05-17 — added O1–O6 ADE-orchestration phases (Caged Autonomous Eng Team); design + decision log in `.planning/ORCHESTRATION-PLAN.md`. | 2026-05-16 — added A1–A11 voss-app Layer-1 phases (terminal-grid scaffold). voss-app is a sibling deliverable to the harness; Layer 2 (Voss integration) and Layer 3 (.voss DSL) lock once L1 ships.
**Milestone update:** 2026-06-20 - BOS restarted as one traditional BOS-prefixed implementation track. Active phase names are BOS1-BOS18 only; split-prefix tracks are removed; completed projection and ledger code are carried forward as BOS3 implementation facts. | 2026-06-18 - started the first docs-first Behavioral OS decomposition. BOS treats V25 server-native swarm as the first ADE event source and reframes `SEED-001` as future external-agent CLI verbs over the existing server/SSE plane, not a parallel coordination bus.

## Phase Order

| Phase | Name | Goal | Requirements | Success Criteria |
|---|---|---|---|---|
| BOS1 | Scope, Wedge, and Track Reconciliation | Reconcile prior BOS material into one active BOS track; lock product wedge, ICP, non-goals, and phase naming | BOS-PROD-01..04, BOS-PLAN-01..04 | 3-5 plans |
| BOS2 | Runtime Architecture and Boundaries | Lock desktop/web/backend/local-runtime boundaries, package shape, storage choices, and stack ownership | BOS-ARCH-01..04, BOS-PROD-04 | 3-5 plans |
| BOS3 | Engineering Event Schema and Runtime Event Substrate | Maintain BOS event schema, project existing session/run/swarm records, and persist projected events in the local ledger | BOS-DATA-01, BOS-DATA-06, BOS-DATA-07 | implemented slices + follow-up plans |
| BOS4 | Decision Ledger Runtime | Record task-to-agent, autonomy, review, validation, escalation, and no-action decisions from runtime gates | BOS-DATA-02 | schema shipped (BOS4-01/02); runtime planned (BOS4-03..05, 3 plans) |
| BOS5 | Outcome Labels and Reward Inputs | Record outcomes/rewards separately from decisions with leakage guards and guardrail metrics | BOS-DATA-03..05 | outcome/reward contract shipped (BOS5-01/02, DATA-03/04); offline-eval contract planned (BOS5-03..05, DATA-05) |
| BOS6 | Privacy and Governance Enforcement | Enforce trust defaults, privacy boundaries, approval/override logging, and guardrail dashboard data | BOS-GOV-01..04 | governance spec shipped (BOS6-01); machine-checkable governance contract planned (BOS6-02..04, 3 plans) |
| BOS7 | Web and Control-Plane Boundary | Build the local/team read model consumed by desktop/web control-plane surfaces without raw code/prompt sync by default | BOS-PROD-04, BOS-SWARM-04, BOS-WORK-03 | 3-5 plans |
| BOS8 | Team, Project, and Work Model | Implement the minimum team/project/task/PR/service/incident entities needed by BOS decisions | BOS-WORK-01..03 | 3-5 plans |
| BOS9 | Recommendation Review Surface and Policy Baselines | Ship heuristic policies and capture approve/override/dismiss/no-op actions, rationale, and training signals | BOS-POL-01..03, BOS-REC-01..03, BOS-BEH-01..03 | 3-6 plans |
| BOS10 | Swarm and ADE Event Integration | Map V25 swarm/ADE/session activity into BOS events, decisions, and outcomes without a parallel bus | BOS-SWARM-01..04 | 3-5 plans |
| BOS11 | External Integration Boundaries | Define and implement first ingestion seams for Git, PM, CI, deploy, observability, and incident sources | BOS-INT-01, BOS-INT-03 | 3-5 plans |
| BOS12 | Identity and Entity Resolution | Resolve tasks, PRs, commits, sessions, agent runs, services, teams, deploys, and incidents across sources | BOS-INT-02 | 3-5 plans |
| BOS13 | Offline Evaluation Export and Replay | Export point-in-time datasets and replay policies without outcome leakage or online autonomy changes | BOS-DATA-05, BOS-POL-03, BOS-RL-02 | 3-5 plans |
| BOS14 | Learning Lab Boundary | Create the Python learning/eval lab boundary for heuristic, bandit, and later RL experiments | BOS-RL-01..03 | 3-5 plans |
| BOS15 | Recommendation Policy Iteration | Iterate recommendation policies from logged verdicts while keeping autonomy unchanged | BOS-POL-03, BOS-REC-02 | 3-5 plans |
| BOS16 | Web Control Plane MVP | Ship the first shared control-plane surface over BOS read/review data while desktop remains local execution | BOS-PROD-04, BOS-SWARM-04 | 3-6 plans |
| BOS17 | Productized Team Workflow Path | Define the path from recommendations/read models into engineering-specific workflow management | BOS-PM-01..03 | 3-5 plans |
| BOS18 | BOS Closeout and Expansion Gate | End-to-end validation, docs cleanup, and next milestone plan based on the completed decision/outcome corpus | BOS-PM-01..03 | 3-5 plans |
| M0 | Scope Lock | Align planning docs around harness-led v0.1 plus `.voss` as workflow control layer | SCOPE-01..04 | 3 |
| M1 | Harness Happy Path | Make the Python harness usable on a real repo with minimal persistence | CLIH-01..10, CTRL-01..09 | 6 |
| M2 | Project Cognition | Make Voss remember useful project facts across sessions | COG-01..08 | 5 |
| M3 | Language Validation | Prove `.voss` is useful for real AI workflow control | LANG-01..10 | 5 |
| M4 | Voss-authored Harness Loop | Dogfood the language on the harness itself | DOG-01..08 | 4 |
| M5 | ⊘ SUPERSEDED by E-track — Eval and Distribution Prep | Eval scope (golden tasks, `voss eval`, judge, tracking) absorbed by E1/E2; packaging smoke shipped (M5-06) | EVAL-01..05 → E1/E2 | superseded |
| M6 | npm Wrapper | Publish `voss` as an npm package that vendors Python + the v0.1 wheel | NPM-01..05 | 5 |
| M7 | SDK Polish | Close the four known public-API holes + stabilize provider registration | SDK-01..05 | 5 |
| M8 | Project Memory (MEM-01) | VOSS.md + cross-session recall layer for the harness using Voss runtime memory primitives | MEM-01..07 | 7 |
| M9 | TUI Shell (TUI-01) | Full-screen Textual interface — diff approval, slash palette, live workflow + budget view | TUI-01..10 | TBD |
| M10 | Codebase Intelligence (CAPS-01a) | LSP polyglot + ast-grep + project index — tools, slash, auto-injection, M9 TUI panel | CODE-01..07 | TBD |
| M11 | Voss-aware Tools (CAPS-01b) | Probable-value inspector, budget tracer, `.voss` lint-as-skill, `.voss`→Python diff viewer | VTOOL-01..05 | 5 |
| M12 | MCP Bridge (CAPS-01c, promotes DIST-03) | Consume external MCP tools + expose harness skills as MCP server | MCP-01..0N (TBD by SPEC.md) | TBD |
| M13 | Multi-agent in Chat (CAPS-01d) — ⊘ ABSORBED into V8 (SHIPPED 2026-06-06) | Expose runtime `spawn`/`gather` to chat session; render via M9 `SubAgentPanel`. V8 delivered the persisted unification: the M13 in-memory `M13Allocator` is superseded by the V4-backed `SessionTreeManager`; M13 artifacts retained as reference. | MAG-01..MAG-08 | 8 |
| M14 | Long-running Tasks + Watch (CAPS-01e) | Background job manager, file-watch-driven re-checks, M9 TUI bottom-pane status strip | WATCH-01..0N (TBD by SPEC.md) | TBD |
| M15 | Skill / Plugin Marketplace (CAPS-01f) | Third-party `.voss` skills installable via `voss skill add`; signed manifests + sandbox boundary | SKILL-01..06 | **Complete** (6/6 plans, 2026-05-20) |
| T6 | PRD §2.4 Slash Debt (v0.1.1 patch) | Ship the slash commands PRD §2.4 promised in v0.1 (`/diff /apply /discard /budget /resume /why /cost --by-`) | SLASH-01..07 | **Complete** (3/3 plans, 2026-05-18) |
| T1 | Iteration Loop + Streaming + Interrupt | Turn single-shot plan→exec→done into a real while-loop agent with streamed text + cancel | ITER-01..06 | **Implemented** (code+tests verified 2026-06-02) |
| T4 | Prompt Caching + Cost Truthfulness | Cache cognition prefix; honest `/cost` including cache reads | CACHE-01..04 | **Implemented** (code+tests verified 2026-06-02) |
| T2 | Parallel Tools + Multi-Edit | Read-only steps gather; `fs_edit_many` atomic batch | PAR-01..04 | **Implemented** (code+tests verified 2026-06-02) |
| T3 | Network Surface (WebFetch + WebSearch + MCP client) | Live docs + MCP ecosystem, gated at the boundary | NET-01..07 | **Implemented** (code+tests verified 2026-06-02) |
| T5 | Shell Ergonomics | 30KB output, background mode, monitor, signal, `voss jobs` | SHELL-01..05 | **Implemented** (code+tests verified 2026-06-02) |
| T7 | Skills Bootstrap | Ship 6 ready skills paired with M5 eval tasks | SKL-01..06 | TBD |
| T8 | Input Bar Ergonomics | Multi-line, `!cmd`, `#mem`, Ctrl-R, paste-image | INPUT-01..05 | **Complete** (5/5 plans, 2026-05-18) |
| A1 | voss-app Tauri Shell | Tauri + Solid empty window, titlebar + theme tokens, local build only (no release pipeline — deferred to A11) | SHL-01..06 | 4 plans, 4 waves |
| A2 | voss-app PTY Pane | One xterm pane wired to native PTY, full TTY support, scrollback, copy/paste | PTY-01..0N (TBD by SPEC.md) | TBD |
| A3 | voss-app Grid Engine | Binary-split tree, splits/focus/resize/close, `⌘1-9` nav, save/load layout | GRD-01..0N (TBD by SPEC.md) | TBD |
| A4 | voss-app Layout Presets | Fanout/pipeline/swarm/watchers visual templates, `⌘G` cycle, reorder w/o killing panes | LAY-01..0N (TBD by SPEC.md) | TBD |
| A5 | voss-app Project Open | Folder picker, recents, `.voss/` lazy create, git branch read, project-less mode | WS-01..0N (TBD by SPEC.md) | TBD |
| A6 | voss-app Session Persist | Pane tree + cwd + truncated scrollback restore across restart | PER-01..0N (TBD by SPEC.md) | TBD |
| A7 | voss-app Cmd Palette + Keymap | `⌘P`/`⌘⇧P`, VSCode-default profile + tmux additions, custom map via `.voss/keymap.json` | CMD-01..0N (TBD by SPEC.md) | TBD |
| A8 | voss-app Workspaces, UX Polish, & Theming | Workspace tab bar (Warp-style), VSCode theme import engine, settings pane, appearance polish, accessibility, profiles, platform-native feel | UXP-01..0N (TBD by SPEC.md) | TBD |
| A9 | voss-app Settings + Theme | Two-pane settings UI, JSON-backed, Variant B token system, font/shell config | CFG-01..0N (TBD by SPEC.md) | TBD |
| A10 | voss-app Status Bar | Project · branch · pane count · cost meter stub · notifications bell · click-to-popover | BAR-01..0N (TBD by SPEC.md) | TBD |
| A11 | voss-app Onboarding + Release Pipeline | First-run wizard, empty state, 24hr soak, **+ full release pipeline** (signing, 3 channels, auto-update). v0 SHIP GATE | OBD-01..0N + REL-01..0N (TBD by SPEC.md) | TBD |
| A12 | voss-app ADE Visual Redesign | Left sidebar (agent list, quick launch, file tree, history) + warm site palette (#ff5b1f accent), pane chrome with role-color accents, branded titlebar. Transforms terminal multiplexer into SOTA ADE. | ADE-01..08 (TBD by SPEC.md) | TBD |
| A13 | voss-app Agent Swarm Orchestration (transport ⊘ SUPERSEDED by V25) | File-mediated multi-agent swarm: coordinator decomposes tasks, spawns parallel agents, monitors via fs events, synthesizes results. Sidebar shows swarm status. **A13-01 file schema retained as V25 audit-layer; A13-02..06 (file-bus spawn/watch/synthesis/UI/persist) superseded by V25 server+SSE runtime.** | SWM-01..12 (file-IPC SWM-04..06 → VSWARM-*) | A13-01 shipped; 02..06 ⊘ superseded by V25 |
| O1 | ⊘ SUPERSEDED by V4 — Session-Tree Substrate + Budget Fan-out | Parent→child session tree; per-card budget envelope; reserved drain budget; hard non-extendable caps (keystone) | OST-01..0N → VTREE-* | superseded |
| O2 | ⊘ SUPERSEDED by V3 — `.voss team{}` Spec + Specialist Roster | `team{}` parser → enriched SubagentSpec (model/mode/scope/budget/tools); EM-immutable ceiling/p; backend/frontend/ui/ai roster | OTEAM-01..0N → VTEAM-* | superseded |
| O3 | ⊘ SUPERSEDED by V5 — Board State Machine + Gated Transitions | Columns, per-column WIP, gate predicates, →Done double gate, critic-loop ceiling+budget, timeout→Blocked | OBRD-01..0N → VBOARD-* | superseded |
| O4 | ⊘ SUPERSEDED by V6 — Reviewer A/B Split | Reviewer-A (idea→bar + tests/eval, `voss/eval/` reuse); Reviewer-B (independent tiered judge: slop/errors/correctness) | ORVW-01..0N → VREV-* | superseded |
| O5 | ⊘ SUPERSEDED by V7 — Engineering Manager Loop | EM full-authority autonomous loop; idea→tickets/AC/DoD; specialist dispatch + routing rationale; kill/re-scope lineage | OEM-01..0N → VEM-* | superseded |
| O6 | ⊘ SUPERSEDED by V9 — Audit Product + Calibration + Liveness (ready plans re-point to V9) | Session-tree review surface; killed-card + routing first-class; calibration telemetry; reserve/timeout; sign-off forcing function | OAUD-01..0N → VAUD-* | superseded (6 plans ready → V9) |
| F1 | Durable Session Persistence | Agent cells resume after restart/crash; SQLite registry + boot-path auto-restart | FPRS-01..05 | 3 plans, 2 waves |
| F2 | Hybrid Semantic Search | BM25 + vector via Reciprocal Rank Fusion; symbol-accurate retrieval | FSRCH-01..04 | 3 plans, 3 waves |
| F3 | Budget & Token Visualization | HUD progress bars for token/budget, live cost updates via IPC | D-01..D-14 (from F3-CONTEXT.md) | 3 plans, 3 waves |
| F4 | Visual Context Heatmap | Context pane showing in-context/compressed files + manual pinning UI | FCTX-01..0N (TBD by SPEC.md) | TBD |
| F5 | Commit with Critique Hook | Pre-commit hook invoking Voss agent to critique diffs against constraints | D-01..D-16 (from F5-CONTEXT.md) | 2 plans, 2 waves |
| F6 | Multi-Model Agent Council | CLI-native multi-model deliberation panel; structured debate + consensus engine | FCNCL-01..0N (TBD by SPEC.md) | TBD |
| V0 | Reframe & Consolidate | Repo/docs reframe to "agent engineering organization layer"; six primitives + terminology table; map M/O/F/A phases to primitives | VRFM-01..05 | TBD by SPEC.md |
| V1 | Capability Surface Hardening | Normalized `Capability` schema over all tools (typed I/O, mutability, scope, network, audit); `voss capabilities list/inspect`; capability groups; unify MCP into registry | VCAP-01..10 | TBD by SPEC.md |
| V2 | Principles Layer | First-class engineering principles (`.voss/principles.yml` + `principles{}`) injected into every agent context, audit-recorded, zero control-flow coupling | VPRIN-01..08 | Plans ready to execute (3 plans, 2 waves; VPRIN-01/03/04/05/06/07; VPRIN-02→V10, VPRIN-08→V9) |
| V3 | Team Spec + Role Cage (supersedes O2) | `.voss team{}` canonical: frozen TeamConfig+SubagentRegistry, compile-time scope/budget containment, default roster, model tiering, `voss team check` | VTEAM-01..10 | TBD by SPEC.md |
| V4 | Session Tree + Budget Fan-out (supersedes O1, KEYSTONE) | Every agent a durable recorded node w/ own budget/scope/status/artifacts; `sum(child)+reserve ≤ parent`; no orphan/overspend; `voss session tree` | VTREE-01..10 | Planned (3 plans, 3 waves) |
| V5 | Board State Machine (supersedes O3) | Board columns/cards/WIP/gates as orchestrator state machine; artifact-gated transitions; agents can't self-Done; `voss board` | VBOARD-01..10 | ✅ COMPLETE — Card fields + self-Done `no-reviewer` guard + `voss board` CLI; shipped O3 surface (VBOARD-01/02/04/05/06/08/09) regressed green |
| V6 | Reviewer A/B Split (supersedes O4) | A authors bar+tests/eval from original idea; B judges narrative-blind w/ idea-divergence authority; persisted review artifacts; `voss review` | VREV-01..10 | TBD by SPEC.md |
| V7 | Engineering Manager Loop (supersedes O5) | Constrained tech-lead: idea→cards→roles→budget→dispatch→integrate→audit; immutable ceiling/p/roster; routing rationale + kill/rescope lineage | VEM-01..10 | ✅ COMPLETE — `voss team run` composes V3–V6 (incl. V6 Reviewer-A/B) + em_loop, RunFinal sidecar persistence + record-only sign-off; cage re-verified; zero frozen-schema drift; O5 superseded |
| V8 | Multi-agent Chat + Live Steering (absorbs M13) | Non-blocking spawn/status/gather/steer in `voss chat`; child budget from parent; recursive budget invariant; quiet-by-default panels | VMAG-10/UNIFY/07/ROOT | ✅ COMPLETE — 3 plans, 3 waves. V8 shipped the V4-backed persisted unification: every chat spawn is a persisted session-tree node; `M13Allocator` removed (single V4 `SessionTreeManager` governs spawns); per-node-manager recursion bounded by the viable-floor (no depth constant); chat-root envelope (60k + 30k reserve) finalized on session exit. MAG-01..09 regressed green; frozen schemas unchanged; no new deps. **ADE child-panel surface deferred to V11** (V8 uses the existing TUI only). |
| V9 | Audit Product (supersedes O6) | Audit as primary trust product: idea/principles/team/budget/scope/board/reviewers/lineage/residual-risk; MD+JSON export; sign-off forcing function; reviewer calibration (AUD-09 ADE render → V11) | VAUD-01..10 | V9-01..06 SHIPPED (7 plans, 6 waves); V9-07 closeout: code+tests GREEN (78 audit tests, zero frozen-schema drift), human verify PENDING |
| V10 | Voss Language as Coordination Spec | Stabilize grammar for principles/team/gate/board/review/memory; diagnostics; `voss ast/check/compile/run`; Python parity tests | VLANG-01..08 | ✅ COMPLETE (5 plans, 5 waves; VLANG-01a/01b/01c/02/08 + VERIFY/GUARD all GREEN; zero frozen-schema drift; coordination-only). |
| V11 | ADE Org Integration | Desktop ADE org panels: roster/board/session-tree/audit/reviewer/budget/scope/diff-drilldown/blocked-decision/replay | VADE-01..10 | ✅ BUILT (8/8 plans + summaries; 10-tab `OrgViewShell` + `org/` panels + CLI-JSON `RunData` + D-02 guard live). **Cockpit redesign of this surface = V14.** |
| V12 | Safety & Factory Fallbacks | Strict rails where autonomy unsafe: irreversible-confirm, deploy/money runbooks, weak-model scaffolds, factory-marked-in-audit, per-dir factory-only | VSAFE-01..07 | Plans ready to execute (4 plans, 4 waves) |
| V13 | External Developer SDK Surfaces (foundation) | SDK strategy (surface matrix, stability tiers, language priority, non-goals) + reconcile `sdk.md`↔`PROTOCOL.md` + Python/M7 linkage. **Docs-only** — the contract snapshot + codegen substrate moved to V13.1. Per-language clients = V13.1–.4 | VSDK-01..06 | TBD by SPEC.md |
| V13.1 | TypeScript Local Client SDK | **Owns the shared contract snapshot** (static `openapi.json`+event-union export, committed, CI drift gate) + serve launcher, REST, SSE typed-event client, permission-reply helpers, typed event union; generated off its own snapshot | VSDK-TS-* | TBD by SPEC.md |
| V13.2 | Rust Local/Native Client SDK | protocol/event types, local server supervisor (reuse voss-tui), auth helpers, session/audit readers; generated off the V13.1 contract snapshot; no orch reimpl | VSDK-RS-* | TBD by SPEC.md |
| V13.3 | Go Local/Headless Client SDK | attach/serve, session CRUD, stream events, approve/deny gates, export audit/session; off the V13.1 contract snapshot; no runtime reimpl | VSDK-GO-* | ✅ COMPLETE (6/6 plans; `sdk/go/` generated+drift-gated types, 21-member Decode, typed REST/SSE, spawn/attach no-orphan, permission, no-FFI guard; full suite + real-server TestMain green; VSDK-GO-01..08). Deviations: go floor→1.24, in-SDK 3.1→3.0 codegen normalizer, 60s spawn handshake. |
| V13.4 | C ABI/Schema Doc | JSON-schema/ABI doc only; generated headers deferred; no full SDK | VSDK-C-* | ✅ COMPLETE (1/1 plan; `docs/native-embedding.md` native/C consumption reference + `docs/check-native-embedding-refs.sh` refs-resolve gate; VSDK-C-01..06; C headers/FFI deferred w/ trigger; zero code). |
| V14 | ADE Run Cockpit (Integrated Redesign + Live Data Unification) | Recompose V11's 10 built panels into an integrated cockpit (Board spine + Card detail drawer + Timeline rail + gate bar); add RunCommandBar intake + global AttentionQueue; normalize the live PTY/SSE registry + static CLI-JSON `RunData` into one UI model with card↔session/pane binding; live SSE wiring gated on V13.1 (snapshot fallback); refreshed quick-launch modal + "Manage with Voss" adopt flow + managed-launch enforcement tiers (OS sandbox/permission-proxy/budget-kill) for external CLIs. Closes the design-contract gaps in `research/ade-ui-design-contract-research.md`. | VCKP-01..13 | ✅ COMPLETE (13/13 plans, operator-approved 2026-06-09; visual contract = recovered mockups in `.planning/sketches/`) |
| E1 | Eval Substrate | Suite loader, TaskSpec, runner, JSONL+summary, hybrid deterministic+judge scoring, subscription-auth model wiring, per-run budget cap (absorbs M5-01..04) | EVSUB-01..07 | planned (5 plans) |
| E2 | Golden Tasks × Repo Matrix | py/rust/ts fixture repos; agent proves cognition + edits per project shape (absorbs M5-05) | EVGLD-01..0N (TBD by SPEC.md) | TBD |
| E3 | Surface E2E | CLI verbs + server plane driven end-to-end with real model inference | EVSRF-01..06 | planned (4 plans, 4 waves) |
| E4 | SDK Proof | `voss.harness` / `voss_runtime` public API exercised as real consumer against live runs | EVSDK-01..08 (minted from CONTEXT) | In Progress (6/7 plans) |
| E5 | TUI + voss-app Autonomous Driving | Drive TUI and voss-app surfaces autonomously; Tauri WebDriver blocked on macOS — approach TBD | EVUI-01..0N (TBD by SPEC.md) | TBD |
| V15 | Live Plane Integration (sidecar handshake + structured pane rendering) | Plug the cockpit into a real `voss serve`: Tauri sidecar command spawns/attaches the server and hands the `{v,port,token}` stdout handshake to the webview (port `voss-sdk` `spawn_with` incl. 60s cold-start + `LITELLM_LOCAL_MODEL_COST_MAP=true`); construct the V13.1 TS client and plug V14's injectable sockets (RunCommandBar native `createSession`, drawer `followUpClient`, SSE → AttentionQueue + model overlay — live label flips for real); Voss-native panes graduate from raw PTY to structured protocol rendering (PROTOCOL §6 event union → DOM: EM task header, tool lines, plan prose, stream deltas) with the inline permission gate (`permission.updated` → Allow/Deny → `POST /permission`, shared with the queue). Visual contract: the pane-content of `.planning/sketches/V14-livework-mockup.html`. Seed: `.planning/notes/seed-structured-pane-rendering.md`. | TBD (SPEC pending) | Added 2026-06-09. Keystone = sidecar handshake (webview cannot spawn `voss serve` — V14 Pitfall 4); spike it first. UI-SPEC before planning (V14 lesson). Out: VCKP-13b permission proxy, rollback/re-run, embedded browser. |
| V24 | ADE Product Revamp + Swarm Observability | Reframe `apps/voss-app` as terminal workbench + agent mission control + review system: quiet top chrome, left portal for Overview/Runs/Agents/Swarm Map/Review/Context/Memory/Settings, humane managed-run intake, layout presets demoted to pane/layout controls, and Swarm Map/Run Graph observability over live agents, tasks, files, tools, gates, budgets, and replay. | VADE2-01..11 | Added 2026-06-14. Preserve terminal-grid behavior and user-owned terminals; do not force every pane through Voss. Depends on V14/V15; consumes V17/V20 signals when available. |
| V25 | Server-Native Swarm Runtime (supersedes A13 transport) | Multi-agent swarm coordinated through the harness server + SSE bus instead of filesystem-as-IPC. `SwarmStore` (sibling to session_store/memory_store) holds roster+tasks server-side; builder sessions spawn-gated to `waiting` until coordinator emits `swarm.assign` (no poll/sleep race); per-task `ownedFiles` enforced at PermissionGate (deny-wins, reuse `.voss/permissions.yml` project-policy layer); per-turn `MemoryStore.recall` scoped to ownedFiles (folds scout into chroma); panes bound to sessions via agent-registry; per-role model routing via existing `_resolve_provider`/router; `.voss/swarm/` files retained as git-diffable audit layer only. | VSWARM-01..11 (locked, V25-SPEC.md) | Planned 2026-06-17: 6 plans, 4 waves. Server+SSE backbone — Voss has a daemon (sidecar+harness); BridgeSwarm/A13 did not. Supersedes A13-02..06; reuses A13-01 file schema for audit. Depends harness server + V15 live plane; pairs with V24 Swarm Map (runtime↔observability). Out: nudge.txt/stdin-injection, PATH bash CLIs, per-agent OS process, scout-as-default-agent. |

---

## BOS-prefixed phases: Behavioral OS Implementation Track

BOS is the only active Behavioral OS implementation track. Phase and plan names
use the normal GSD convention: `BOS1-01`, `BOS1-02`, `BOS2-01`, and so on.
There is no separate implementation prefix.

**Track stance:** BOS1-BOS18 are phase scopes, not a frozen waterfall. Each
phase should still go through discuss, research, plan, and execute before code
work proceeds. Replanning a phase is expected when research or implementation
changes the shape of the work.

**Implementation stance:** docs-only work is allowed only when it locks scope,
research, contracts, or validation for the next code slice. The track should
ship runtime behavior early and repeatedly: projection, ledger, decisions,
outcomes, recommendation logging, read models, and surfaces.

**Runtime stance:** BOS builds over the existing Voss harness/server/ADE/swarm
plane. V25 server/SSE swarm remains the coordination plane. `SEED-001` stays
future external-agent client context and must not become a second runtime bus.

**Carry-forward implementation facts:**
- `voss/harness/bos_events.py` projects session/run/swarm records into BOS
  event dictionaries and belongs to BOS3.
- `voss/harness/bos_ledger.py` persists projected BOS events to
  `.voss/bos/events.jsonl` and belongs to BOS3.
- `tests/harness/test_bos_event_projection.py` and
  `tests/harness/test_bos_event_ledger.py` are the regression gates for those
  slices.

| BOS phase | Scope | Execution shape |
|---|---|---|
| BOS1 | Scope, wedge, and track reconciliation | Reconcile source docs, remove abandoned prefixes, lock phase naming and product boundary |
| BOS2 | Runtime architecture and boundaries | Convert architecture docs into package/storage/interface decisions that implementation phases can consume |
| BOS3 | Engineering event schema and runtime event substrate | Maintain schema, projected event generation from sessions/runs/swarm, and local event ledger |
| BOS4 | Decision ledger runtime | Write decision records from runtime gates and operator choices |
| BOS5 | Outcome labels and reward inputs | Write outcome labels, reward inputs, and no-leakage tests |
| BOS6 | Privacy and governance enforcement | Enforce trust, privacy, approval, override, and guardrail boundaries |
| BOS7 | Web and control-plane boundary | Expose local/team read models for desktop/web control-plane consumption |
| BOS8 | Team, project, and work model | Implement minimum entities and links for team/project/task/PR/service/incident work |
| BOS9 | Recommendation review surface and policy baselines | Ship heuristics and capture approve/override/dismiss/no-op actions |
| BOS10 | Swarm and ADE event integration | Connect V25 swarm/ADE activity to BOS events, decisions, and outcomes |
| BOS11 | External integration boundaries | Add first ingestion seams without pulling secrets or production-sensitive records |
| BOS12 | Identity and entity resolution | Resolve tasks, PRs, commits, sessions, services, teams, deploys, and incidents |
| BOS13 | Offline evaluation export and replay | Export point-in-time datasets and replay policies safely |
| BOS14 | Learning lab boundary | Keep heuristic/bandit/RL experiments behind offline eval boundaries |
| BOS15 | Recommendation policy iteration | Improve policies from logged verdicts while keeping autonomy unchanged |
| BOS16 | Web control plane MVP | Build the first shared control-plane surface over BOS read/review data |
| BOS17 | Productized team workflow path | Define the path toward engineering-specific workflow management |
| BOS18 | Closeout and expansion gate | Validate the end-to-end BOS track and plan the next milestone from evidence |

**Deferred beyond BOS18:** broad PM-suite replacement, production online
learning, autonomy increases, billing/accounts/admin, and any multi-tenant
SaaS behavior not justified by the completed BOS decision/outcome corpus.

## V-prefixed phases: Agent Engineering Organization Layer

V0–V12 reframe Voss as a **controlled AI engineering-organization runtime** — declared roles, first-class principles, bounded budget/scope, independent review, replayable audit. Full per-phase requirements, acceptance criteria, syntax, build order, and rationale live in [`docs/ORCHESTRATION_LAYERS.md`](docs/ORCHESTRATION_LAYERS.md) (the PRD). Each phase's `V{n}-SPEC.md` locks the namespaced requirements before planning (mechanism identical to the M/O/F tracks). **V13 (External Developer SDK Surfaces)** extends the track beyond the PRD's P0–P12 — it has no PRD §P section; its design source is `V13-SPEC.md` + the SDK Surface Matrix added to the PRD. Per-language clients are sub-phases **V13.1–V13.4**, each with its own SPEC. The shared contract snapshot + codegen substrate + CI drift gate live in **V13.1** (the first client owns the artifact); V13.2–.4 generate off the V13.1 snapshot. V13 itself is docs-only.

**Supersession:** the V-track is a superset, not a parallel track. It retires the O-track and absorbs M13. O1–O6 stay in the repo as historical design (`ORCHESTRATION-PLAN.md`) but are archived-as-superseded; M13 scope + planned plans fold into V8. O6's 6 ready plans re-point to V9.

| V-phase | PRD | Supersedes / absorbs | Requirement IDs |
|---|---|---|---|
| V0  Reframe & Consolidate            | P0  | — (docs/identity)         | VRFM-01..05 |
| V1  Capability Surface Hardening     | P1  | hardens M10–M15 tools     | VCAP-01..10 |
| V2  Principles Layer                 | P2  | new                       | VPRIN-01..08 |
| V3  Team Spec + Role Cage            | P3  | **O2**                    | VTEAM-01..10 |
| V4  Session Tree + Budget Fan-out    | P4  | **O1** (keystone)         | VTREE-01..10 |
| V5  Board State Machine              | P5  | **O3**                    | VBOARD-01..10 |
| V6  Reviewer A/B Split               | P6  | **O4**                    | VREV-01..10 |
| V7  Engineering Manager Loop         | P7  | **O5**                    | VEM-01..10 |
| V8  Multi-agent Chat + Live Steering | P8  | **M13**                   | VMAG-01..10 |
| V9  Audit Product                    | P9  | **O6** (reuse O6 plans)   | VAUD-01..10 |
| V10 Voss Language as Coordination    | P10 | extends M3 grammar        | VLANG-01..08 |
| V11 ADE Org Integration              | P11 | builds on A12/A13         | VADE-01..10 |
| V12 Safety & Factory Fallbacks       | P12 | new                       | VSAFE-01..07 |
| V13 External Developer SDK Surfaces  | —   | new (post-P12; docs-only)   | VSDK-01..06 |
| V13.1 TypeScript Local Client SDK    | —   | owns contract snapshot+gate | VSDK-TS-*   |
| V13.2 Rust Local/Native Client SDK   | —   | off V13.1 snapshot          | VSDK-RS-*   |
| V13.3 Go Local/Headless Client SDK   | —   | off V13.1 snapshot          | VSDK-GO-*   |
| V13.4 C ABI/Schema Doc               | —   | doc-only (no full SDK)      | VSDK-C-*    |
| V14 ADE Run Cockpit                  | —   | recomposes **V11**; on A13/V13.1 | VCKP-01..13 |
| V15 Live Plane Integration           | —   | on **V14** + V13.1 SDK + real `voss serve` | VLIVE-01..08 (SPEC locked) |
| V24 ADE Product Revamp + Swarm Observability | — | productizes **V14/V15**; consumes V17/V20 when available | VADE2-01..11 |
| V25 Server-Native Swarm Runtime              | —   | supersedes **A13** transport; pairs w/ V24; on harness+V15 | VSWARM-01..NN (SPEC pending) |

**ID namespacing:** PRD IDs are prefixed `V*` in the roadmap to avoid collisions — PRD `MAG-*`/`LANG-*`/`ADE-*` clash with M13/M3/A12 (different meanings). Inside `docs/ORCHESTRATION_LAYERS.md` the un-prefixed IDs remain; SPEC-phase maps PRD-ID → namespaced roadmap-ID.

**Build order (PRD §7):** V1 → V3 → V4 → V5 → V6 → V7 → V9 first; V2/V10/V11/V12 layer on after; **V14 (ADE Run Cockpit) recomposes V11's built panels and lands after V11, gated on V13.1 only for its live-SSE wave.** **V24 (ADE Product Revamp + Swarm Observability) productizes V14/V15 into a digestible terminal-first workbench and should not start before the live-plane seams are stable enough to feed the Swarm Map honestly.** **V4 (session tree + budget fan-out) is the keystone** — board, reviewers, EM, audit all need durable budgeted nodes first; budget enforcement must be pre-emptive (a node cannot make the call that breaches its envelope), or the cage leaks. Keep `voss do`/`voss chat` working every phase (PRD §9 top risk).

---

## Phase M0: Scope Lock

**Goal:** Align repo and planning docs around harness-led v0.1 plus language control layer.

**Requirements:** SCOPE-01, SCOPE-02, SCOPE-03, SCOPE-04

**Deliverables:**
- `.planning/PROJECT.md` reflects harness-led v0.1.
- `.planning/REQUIREMENTS.md` contains v0.1 harness requirements.
- `.planning/ROADMAP.md` uses M-prefixed phases.
- `.planning/HARNESS-PLAN.md` names the v0.1 direction and defers Rust.

**Success Criteria:**
1. No ambiguity remains between compiler verbs and harness verbs: `voss run` executes `.voss` programs; `voss do` executes natural-language agent tasks.
2. Planning docs clearly state that `.voss` remains central as an AI workflow control language.
3. Rust, MCP bridge, tree-sitter, VSCode marketplace, Linguist upstream, and full telemetry are deferred until the Python harness proves usage.

**Cross-cutting constraints:**
- This phase is planning-only; it should not implement harness behavior.
- Existing phase directories may remain as historical artifacts unless explicitly archived.
- `.vscode/voss_v_0_1_scope_lock.md` is the source of truth.

---

## Phase M1: Harness Happy Path

**Goal:** Make the harness usable on a real repo with minimal persistence.

**Requirements:** CLIH-01..10, CTRL-01..09

**Required commands:**

```bash
voss doctor
voss do "summarize this repo"
voss do "summarize this diff"
voss edit <file>
```

**Capabilities:**
- Provider auth works.
- `fs_*`, `git_*`, `shell_run`, and `voss_check` tools work.
- Permission modes `plan`, `edit`, and `auto` are available.
- Path jail rooted at `--cwd` is enforced.
- Status rendering and tool traces work.
- Basic session snapshot works without storing provider secrets.

**Success Criteria:**
1. `voss` and `voss chat` launch the interactive harness REPL.
2. `voss do "<task>"` runs one natural-language task and exits cleanly.
3. `voss edit <path>` constrains edits to the requested scope unless the user approves broader access.
4. `voss doctor` reports provider/config/tooling setup.
5. Risky filesystem or shell operations require permission prompts with deny, allow once, and allow always choices.
6. `voss run <file.voss>` remains a compiler command and is not overloaded for agent tasks.

**Cross-cutting constraints:**
- Harness can remain Python-authored in M1.
- Compiler commands remain available.
- No provider API keys or equivalent secrets may be written into session payloads.

**Plans:** 7 plans

Plans:
- [ ] M1-01-PLAN.md — Permission tiers + tool descriptors (is_mutating, mode_allows)
- [ ] M1-02-PLAN.md — voss doctor check registry + traffic-light table
- [ ] M1-03-PLAN.md — Session redaction guarantee + CI test
- [ ] M1-04-PLAN.md — voss edit scoped REPL + diff preview
- [ ] M1-05-PLAN.md — REPL /login, /model, /mode (+ --confirm) + config.toml
- [ ] M1-06-PLAN.md — voss tools + voss config commands
- [ ] M1-07-PLAN.md — Per-command mode defaults + happy-path integration + voss run guard

---

## Phase M2: Project Cognition

**Goal:** Make Voss remember useful project facts.

**Requirements:** COG-01..08

**Required commands:**

```bash
voss do "analyze this repo"
voss resume
voss sessions
```

**Project outputs:**
- `.voss/project.json`
- `.voss/architecture.md`
- `.voss/constraints.yml`
- `.voss/permissions.yml`
- `.voss/validation.yml`
- `.voss/plans/`
- `.voss/sessions/`
- `.voss/decisions/`
- `.voss-cache/repo.idx` or a simpler rebuildable file index

**Success Criteria:**
1. Repo analysis creates or updates `.voss/architecture.md`.
2. Agent plans are saved under `.voss/plans/`.
3. Sessions can be listed and resumed.
4. Decisions and validation commands are inspectable under `.voss/`.
5. Repeated sessions improve from stored project context rather than starting from zero.

**Cross-cutting constraints:**
- `.voss/` is durable project knowledge.
- `.voss-cache/` is rebuildable machine state.
- Stored memory must distinguish inspected, changed, and explicitly avoided files.

**Plans:** 7 plans

Plans:
- [ ] M2-00-PLAN.md — Wave 0 test scaffold + pyyaml dep + shared git_repo fixture
- [ ] M2-01-PLAN.md — cognition.py load+drift+repo.idx + strict pydantic YAML schemas
- [ ] M2-02-PLAN.md — Per-cwd session storage + RunRecord + RunRecorder mechanical capture
- [ ] M2-03-PLAN.md — RunRecorder wired into run_turn + record_run privileged close + decisions/*.md mirror
- [ ] M2-04-PLAN.md — /analyze slash + natural-language route + bootstrap + repo.idx rebuild + .gitignore writes
- [ ] M2-05-PLAN.md — Cognition auto-injection in run_turn (6k budget) + renderer surfaces + voss resume prior-context
- [ ] M2-06-PLAN.md — Drift hint + voss sessions --all + doctor cognition rows + permissions.yml layering

---

## Phase M3: Language Validation

**Goal:** Prove `.voss` is useful for real AI workflows.

**Requirements:** LANG-01..10

**Required commands:**

```bash
voss check samples/classify.voss
voss check samples/support.voss
voss check samples/research.voss
voss run samples/classify.voss
```

**Capabilities:**
- Parser supports representative AI workflow syntax.
- Analyzer catches unguarded `probable<T>` usage.
- Codegen emits readable Python.
- Runtime examples pass.
- Language demo shows shorter, clearer workflow code than equivalent Python boilerplate.

**Success Criteria:**
1. Three meaningful `.voss` examples pass `voss check`.
2. At least one representative `.voss` example runs end-to-end.
3. Generated Python is understandable and imports `voss_runtime`.
4. Confidence gates, context budgets, semantic routing, tools, memory, agents, and fallbacks remain first-class.
5. Docs and sample framing describe `.voss` as AI workflow control, not a Python replacement.

**Cross-cutting constraints:**
- Do not chase full Python syntax parity.
- Default verification should stay hermetic with stub providers/fake indexes where possible.
- `voss check` should be fast enough to run after edits.

**Plans:** 6 plans

Plans:
- [ ] M3-01-PLAN.md — Analyzer D-03 static-only check guard + sentinel test
- [ ] M3-02-PLAN.md — Auto-StubProvider fallback + stderr banner + hermetic env propagation
- [ ] M3-03-PLAN.md — D-07 coverage fixtures for memory.semantic + memory.working (parser/analyzer/codegen)
- [ ] M3-04-PLAN.md — Sample extensions (support memory.episodic; research try/catch + use) + raw_python parity + D-14 headers
- [ ] M3-05-PLAN.md — tests/examples repoint to samples/ + slim legacy + extend support/research e2e for raw-parity
- [ ] M3-06-PLAN.md — D-13 per-sample speed gate + README "What is .voss" + docs/voss-vs-python.md

---

## Phase M4: Voss-authored Harness Loop

**Goal:** Dogfood the language on the harness itself.

**Requirements:** DOG-01..08

**Required command:**

```bash
voss check voss/harness/agent/
```

**Target files:**

```text
voss/harness/agent/
├── loop.voss
├── router.voss
├── planner.voss
├── executor.voss
└── reviewer.voss
```

**Success Criteria:**
1. `voss/harness/agent/*.voss` exists and models the harness loop.
2. `voss check voss/harness/agent/` passes in CI.
3. Compiled harness artifacts cache under `.voss-cache/harness/`.
4. Bare `voss` can boot through compiled harness logic once the dogfood loop is enabled.

**Cross-cutting constraints:**
- This should not block the earliest Python harness MVP.
- Harness self-hosting should expose language regressions quickly.
- Python fallback may remain until the compiled harness path is proven.

**Plans:** 5 plans

Plans:
- [x] M4-01-PLAN.md — Wave 0 compiler sub-plan: grammar `use ... as` + codegen auto-await for use-imported callees
- [x] M4-02-PLAN.md — Wave 1 CLI dir-walk + cache infra: sandbox.write_cache, cache.py manifest, StaleHarnessCacheError, voss check/compile <dir>
- [x] M4-03-PLAN.md — Wave 2 `.voss` authoring + boot dispatch: 5 .voss files, _run_step_loop extraction, ToolEntry.invoke_dict, _resolve_run_turn
- [x] M4-04-PLAN.md — Wave 3 parity test + DOG-07 smoke: session-scoped pre-compile fixture, FakeProvider parity, subprocess smoke
- [x] M4-05-PLAN.md — Wave 4 CI gate + docs: voss check CI step, README eager-compile one-liner, doctor harness-cache row

---

## Phase M5: Eval and Distribution Prep — ⊘ SUPERSEDED by E-track (2026-06-10)

> Eval scope (golden tasks, `voss eval` CLI, judge_run, success/cost/confidence tracking — M5-01..05) absorbed into **E1/E2**. Packaging smoke (M5-06) shipped and stands. Decisions: `.planning/notes/e-track-eval-decisions.md`.

**Goal:** Measure quality and prepare shipping.

**Requirements:** EVAL-01..05

**Capabilities:**
- Golden repo tasks for the canonical demo workflow.
- Success rate tracking.
- Mean cost tracking.
- Confidence correlation tracking.
- Package install polish.

**Success Criteria:**
1. Golden tasks cover repo analysis, plan-only change, approved edit, validation, and resume.
2. Eval output records success rate, mean cost, and confidence correlation.
3. Packaging smoke verifies the Python harness and compiler commands install together.
4. Rust/Homebrew work remains deferred unless the Python harness proves real usage.

**Cross-cutting constraints:**
- Full telemetry is deferred; keep v0.1 eval practical and local-first.
- Distribution work should not pull focus from harness behavior.
- Any public-facing docs should reflect the harness-first positioning.

**Plans:** 6 plans

Plans:
- [ ] M5-01-PLAN.md — Wave 0 suite loader + TaskSpec pydantic + fixture isolation helper
- [ ] M5-02-PLAN.md — Wave 1 Verdict + judge_run + auth.resolve role kwarg
- [ ] M5-03-PLAN.md — Wave 2 voss eval CLI + runner + JSONL writer
- [ ] M5-04-PLAN.md — Wave 3 summary.md + stdlib Pearson + .voss/.gitignore guard
- [ ] M5-05-PLAN.md — Wave 4 five golden task fixtures (01-analyze..05-resume)
- [x] M5-06-PLAN.md — Wave 5 wheel-in-tempvenv smoke + README install polish

---

## Phase M6: npm Wrapper

**Goal:** Publish `voss` as an npm package that vendors a pinned Python interpreter + the v0.1 wheel so JS-ecosystem developers can `npm i -g voss` (or `npx voss`) and run the harness without managing Python themselves.

**Requirements:** NPM-01..05

**Required commands (post-install):**

```bash
npx voss --help
npx voss doctor
npx voss check <file-or-dir>
npx voss compile <file>
npx voss do "<task>"
```

**Capabilities:**
- npm package named `voss` (or `@voss/cli`) — naming locked during M6 discuss.
- Bundled-Python distribution pattern (mirrors pyright). Per-platform Python interpreter vendored via postinstall download OR per-platform optionalDependencies subpackages.
- Supported platforms in v0.1: darwin-arm64, darwin-x64, linux-x64, linux-arm64, win32-x64.
- Node-side `bin/voss.js` shim forwards all argv to the vendored `python -m voss.cli` with full exit-code, stdio, and signal passthrough.
- v0.1 wheel from M5 is the source of truth — npm package vendors the same wheel; no parallel implementation.
- Smoke test in a fresh Node project verifies the post-install command surface (see "Required commands").

**Success Criteria:**
1. `npm i -g voss` installs the CLI on at least the five supported platforms.
2. `npx voss --help`, `npx voss doctor`, `npx voss check <sample>`, and `npx voss compile <sample>` all exit 0 immediately after install in a fresh Node project, with no manual Python setup.
3. `voss` bin shim is signal-safe (Ctrl-C interrupts the underlying Python process) and exit-code-faithful.
4. README primary install path is `npm i -g voss`; `pip install voss` is listed as the secondary path.
5. npm package version tracks the Python wheel version 1:1 — publishing `voss@0.1.0` requires `voss==0.1.0` on PyPI (or vendored at the same git tag).

**Cross-cutting constraints:**
- This is distribution work, NOT reimplementation. Python code under `voss/`, `voss_runtime/`, and `voss/harness/` is unchanged by M6.
- DIST-01 (Rust harness shell) stays deferred — M6 buys npm distribution without it. If startup latency under bundled-Python proves painful in M6 dogfood, that's the signal to revisit DIST-01.
- M5 wheel smoke is a prerequisite — M6 vendors the same wheel M5 verifies.
- Windows support enters v0.1 ONLY through npm (REQUIREMENTS "Out of Scope" lists Windows defer for core, but npm wrapper inherits cross-platform Node assumptions). If win32 vendoring proves expensive, drop to mac+linux in v0.1 and document.
- npm publish credentials and `@voss` org reservation happen during M6 — not before.
- No JS reimplementation of the harness, compiler, or runtime in M6. Pure wrapper.

**Plans:** 5 plans

Plans:
- [ ] M6-01-PLAN.md — Wave 1 npm name reservation (@voss org + 6 placeholders at 0.0.0) + delete cargo-dist release.yml + freeze rust.yml + scaffold npm/ directory tree
- [ ] M6-02-PLAN.md — Wave 2 Node bin shim (npm/bin/voss.js) per Biome pattern + per-platform package.json amendments + fast pytest pinning shim invariants
- [ ] M6-03-PLAN.md — Wave 2 build scripts (prune_pbs.py, build_platform.py, bump_version.py) + pbs_manifest.json + unit tests + [BLOCKING] host-platform size-budget verification before M6-04 fan-out
- [ ] M6-04-PLAN.md — Wave 3 release.yml (5-platform GHA matrix + npm publish) + ci.yml version-sync gate + 0.1.0 version bump + [BLOCKING] test-tag exercise of the workflow
- [ ] M6-05-PLAN.md — Wave 4 NPM-04 packaging smoke (tests/packaging/test_npm_install.py) + README.md npm-primary install (NPM-05) + test_readme.py invariants + [BLOCKING] final v0.1.0 release approval

---

## Phase M7: SDK Polish

**Goal:** Close the four known public-API holes documented in `docs/sdk.md` (Known gaps) plus stabilize the provider-registration entry point so third-party embedders and providers can use Voss without reaching into private modules.

**Requirements:** SDK-01..05

**Required surface (post-phase):**

```python
# voss.harness public additions
from voss.harness import (
    Renderer,                    # SDK-01: protocol
    NullRenderer,                # SDK-01: silent default
    tool_entry_from_callable,    # SDK-02: factory
    SessionView,                 # SDK-03: read-only embedder view
)

# voss_runtime public additions
from voss_runtime import (
    RuntimeConfig,               # gains .from_toml(path) and .default() — SDK-04
)
from voss_runtime.providers import register as register_provider  # SDK-05
```

**Capabilities:**
- Embedders can author silent or custom rendering without importing from `voss.harness.render`.
- Embedders can wrap a plain Python callable as a `ToolEntry` with a single factory call — no manual descriptor authoring.
- Embedders can introspect sessions (id, cwd, per-run timestamps/cost/confidence) via a stable read-only view without binding to the on-disk `SessionRecord`/`RunRecord` schema.
- Embedders can load harness config from `~/.config/voss/config.toml` (or a custom path) and overlay env overrides in one call.
- Third-party providers can be registered via a public, documented entry point.

**Success Criteria:**
1. Each new public name appears in the relevant package `__all__` AND in `tests/packaging/test_public_api.py` EXPECTED_*_PUBLIC_API set.
2. `docs/sdk.md` "Known gaps" list shrinks by exactly the five items shipped (SDK-01..05). No private-path workaround examples remain for those five.
3. A new test file exercises the embedding surface end-to-end: build a fake tool from a callable, drive a turn with `NullRenderer`, introspect resulting session via `SessionView`, configure via `RuntimeConfig.from_toml`, register a custom provider — all from `voss.harness.__all__` / `voss_runtime.__all__` symbols only.
4. The on-disk `SessionRecord`/`RunRecord` schemas remain private (not promoted by accident).
5. Stability docstrings updated on `voss.harness/__init__.py` and `voss_runtime/__init__.py` to reflect the expanded public surface.

**Cross-cutting constraints:**
- M7 promotes existing internals; it does not invent new behavior. If a feature isn't shippable as a pure rename + re-export + docstring + test, it doesn't belong in M7.
- No new private surface introduced as a side effect. Every helper added must be either covered by `__all__` or marked `_private` from day one.
- Pre-1.0 versioning carve-out (docs/sdk.md §Versioning) allows shipping M7 in a 0.x minor release without a major bump.
- Ordering: M7 ideally lands BEFORE the first `voss==0.1.0` PyPI publish + `voss@0.1.0` npm publish so the public surface stabilizes before any external caller pins it. If M6 ships first, M7 lands as `0.1.1` and `docs/sdk.md` "Versioning" rules still hold (minor pre-1.0 may break; this would be a minor bump). Plan against both orderings.
- TS/JS SDK, HTTP/remote SDK, formal plug-in framework with entry-points and sandboxing remain explicitly OUT of M7 — those are independent v0.2+ candidates with their own triggers.

---

## Phase M8: Project Memory (MEM-01)

**Goal:** Give the Voss harness a persistent project-memory layer so it stops re-learning the repo every session. Two tiers: a human-curated `VOSS.md` (analog to `CLAUDE.md`) and an agent-curated cross-session recall store built on Voss's own runtime memory primitives (`memory.episodic`, `memory.semantic`).

**Requirements:** MEM-01, MEM-02, MEM-03, MEM-04, MEM-05, MEM-06, MEM-07

**Seed source:** [`seeds/project-memory-voss-md.md`](seeds/project-memory-voss-md.md)
**Thesis context:** [`notes/voss-agent-unfair-advantage.md`](notes/voss-agent-unfair-advantage.md)

**Headline deliverables (subject to SPEC.md refinement):**
- `VOSS.md` loader — read at session start, inject into harness system context. Section conventions (project, build, style, do/don't). Hierarchical resolution (root + per-directory) decided in SPEC.
- Cross-session recall store under `.voss/memory/` — episodic + semantic, file-backed, indexed. Reuses runtime memory primitives.
- Slash command surfaces (`/recall <query>`, `/forget`) — minimal CLI form for v0.1; richer surface lands with [[tui-shell-textual]] (M9).
- End-of-session prompt: agent extracts candidate decisions/conventions from the turn history; user picks what to persist.
- Privacy-first defaults — nothing leaves the repo; no cloud sync in this phase.

**Cross-cutting constraints:**
- Must run with the existing v0.1 harness surface (`voss chat`, `voss resume`, `voss sessions`). No TUI dependency.
- Reuse runtime memory primitives — do not build a parallel store. Phase doubles as proof that `memory.*` earns its keep.
- Hard cap memory store size + provide a vacuum/forget path before shipping.
- Integration with `voss sessions` / `voss resume` (CLIH-05/06/07) must remain backwards compatible — existing session files must continue to load.

**Success Criteria:** TBD by `08-SPEC.md`. Spec-phase will produce pass/fail acceptance checkboxes.

**Out of scope (this phase):**
- Cross-project memory sharing.
- Cloud-backed memory store.
- TUI surfaces for browsing memory (lands in M9).
- Multi-agent memory partitioning (lands in M10).

**Plans:** 7 plans

Plans:
- [ ] M8-00-PLAN.md — Wave 0 scaffold: /save -> /save-session rename, portalocker dep, 4 module skeletons (voss_md/memory_store/conventions/memory_cli), 13 test stubs + conftest fixtures, Req 7 grep-gate test live from day one
- [ ] M8-01-PLAN.md — MEM-01 VOSS.md loader (parse/read_and_inject/read_fence_body/write_fence_body/HashMismatch) + system-context injection in _run_repl + do_cmd + run_turn sys_prompt
- [ ] M8-02-PLAN.md — MEM-02 architecture.md→VOSS.md byte-identical migration + cognition._load_arch read-path rewire + skills/analyze.py write-path rewire (Pitfall 2 closed)
- [ ] M8-03-PLAN.md — MEM-03 + MEM-07 MemoryStore (bind/recall/forget/write_turn/write_ledger/write_note/write_convention/summary) + chroma lazy init + keyword fallback + portalocker per-source locking + 80%/60% hit-rate eval + grep-gate runtime-reuse mock
- [ ] M8-04-PLAN.md — MEM-04 conventions extraction (has_signal D-09 + Pitfall 5 quorum / extract_conventions D-10 strict-JSON / review_candidates D-11 / run_on_clean_exit D-12 8s timeout + config.yml toggle)
- [ ] M8-05-PLAN.md — MEM-05 4 slash commands wired (/recall, /forget --yes gate, /memory, /save manual note + Pitfall 1 regression test) + ctx.memory_store boot binding
- [ ] M8-06-PLAN.md — MEM-06 _maybe_evict per-source quotas D-14/D-16 + MemoryStore.vacuum + voss memory vacuum/adopt/size CLI subcommand group + memory_group registration in AGENT_COMMANDS + voss_md.write_fence_body adopt=True

---

## Phase M9: TUI Shell (TUI-01)

**Goal:** Replace the current `rich`-based line-streamed CLI for `voss chat` / `voss do` with a full-screen TUI (Textual or equivalent). Match Claude Code / Aider interaction depth and expose Voss's language primitives — probable values, budgets, spawn/gather — directly in the UI.

**Requirements:** TUI-01, TUI-02, TUI-03, TUI-04, TUI-05, TUI-06, TUI-07, TUI-08, TUI-09, TUI-10

**Seed source:** [`seeds/tui-shell-textual.md`](seeds/tui-shell-textual.md)

**Headline deliverables (subject to SPEC.md refinement):**
- Textual app shell — header (session id, budget remaining), main turn-history pane, input bar with slash-command palette + autocomplete, modal pane for diff approval + permission prompts.
- Per-hunk diff approval — user accept/reject individual hunks instead of blind apply.
- Live workflow visualization — probable-value confidence bars, `ctx(budget:)` token meter, `spawn`/`gather` sub-agent panels rendered from the recorder stream (`voss/harness/recorder.py`).
- Session resume UX — scroll prior turns, fork from any turn, branch sessions.
- Keybindings — vim-ish navigation, `/` slash palette, `?` help overlay.
- `--plain` flag — preserve current line mode for pipes / CI.

**Cross-cutting constraints:**
- Library choice (Textual vs prompt_toolkit vs hand-rolled) gated by SPEC.md and discuss-phase.
- Must work over the M6 npm wrapper's vendored Python on macOS, Linux, and Windows console.
- Must not regress headless (`--plain`) CLI exit codes, stdout shape, or pipe behavior.
- M8 memory surfaces (`/recall`, memory browser) plug into TUI panels — TUI-01 reserves UI hooks but does not require M8 to ship.

**Success Criteria:** TBD by `09-SPEC.md`.

**Out of scope (this phase):**
- Editor / VSCode integration (EDIT-01/02 track).
- Web UI.
- New runtime hooks — TUI reads from the existing recorder. If hooks need extending, that lands in a follow-up phase.

**Plans:** 7 plans

Plans:
- [ ] M9-01-PLAN.md — Library-choice gate + Textual dep + --plain plumbing + pre-M9 stdout byte baseline (idempotent, locked FakeProvider)
- [ ] M9-02-PLAN.md — Textual app shell (region grid) + TextualRenderer (Renderer-protocol) + locked glyph + locked color stylesheet + ConfidenceBar (16-cell locked) / BudgetMeter (em-dash on zero-total) widgets
- [ ] M9-03-PLAN.md — SlashPalette + HelpOverlay + KEYMAP table + reserved slash names for M8 (4 names: /recall, /forget, /memory, /save) + live `/save` → `/snapshot` rename with deprecation alias
- [ ] M9-04-PLAN.md — Live workflow visualization: SubAgentPanel + RecorderBridge (read-only) + SPAWN_TOOL_NAME constant + runtime-surface hash baseline regression test (4 files)
- [ ] M9-05-PLAN.md — DiffModal (per-hunk) + PermissionModal + BudgetExhaustedModal + permissions_bridge (injects modal-driven prompt_fn)
- [ ] M9-06-PLAN.md — Fork-from-turn data model + backward-compat session schema (additive optional parent_id, parent_turn_index) + ForkConfirmModal + action_fork_turn handler
- [ ] M9-07-PLAN.md — cli.py default-path flip to TextualRenderer + install_tui_permissions wire-up + accent allow-list audit + --no-unicode flag/env + Windows console strategy + phase-final human-verify checkpoint

---

## Phase M10: Codebase Intelligence (CAPS-01a)

**Goal:** Add a codebase-intelligence layer to the Voss harness — polyglot LSP-backed semantic operations + ast-grep-backed structural pattern search, exposed via harness tools, slash commands, system-context auto-injection, and an M9 TUI side panel. Originally the CAPS-01 seed bundled six capabilities; M10 SPEC scope-cut to codebase intel only. The other five capabilities are formal follow-on phases M11–M15.

**Requirements:** CODE-01..07 (minted in `M10-SPEC.md`).

**Seed source:** [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md)
**SPEC:** [`phases/M10-agent-capability-surface-caps-01/M10-SPEC.md`](phases/M10-agent-capability-surface-caps-01/M10-SPEC.md)
**Thesis context:** [`notes/voss-agent-unfair-advantage.md`](notes/voss-agent-unfair-advantage.md)

**Headline deliverables (locked in SPEC):**
- Project index — session-start scan + on-demand refresh, persisted under `.voss-cache/code/`. No file-watch (deferred to M14).
- LSP client + server registry (Python via pyright, JS/TS via typescript-language-server, Rust via rust-analyzer, Go via gopls). Config-driven through `.voss/lsp.yml`.
- ast-grep / tree-sitter structural-search backend with regex fallback when ast-grep absent.
- Four new harness tools: `code_search`, `find_definition`, `find_references`, `code_refresh`.
- Three new slash commands: `/symbol`, `/refs`, `/refresh`.
- Auto-injection: `## Project Index` section in system context (≤ 1500 tokens).
- M9 TUI amendment: `CodeIntelPanel` widget reserving the side region (mode-shares with `SubAgentPanel`).

**Cross-cutting constraints:**
- M9 amendment (Req 7) MUST land + pass plan-checker BEFORE M10 execute. Schedule as `M9-08-PLAN.md` or amendment to `M9-02`.
- ast-grep is a soft dependency via `voss[code]` extra. Tools must function without it via regex fallback.
- LSP servers lazy-launched, reaped on session exit. No orphan processes.
- Session-start scan latency budget: ≤ 5s @ 10K LoC; ≤ 30s @ 100K LoC (partial-index warning beyond).
- Index storage under `.voss-cache/` (rebuildable), not `.voss/` (durable) — matches M2 COG-07.

**Success Criteria:** 17 pass/fail criteria locked in `M10-SPEC.md`.

**Out of scope:** Voss-aware tools (M11), MCP bridge (M12 — promotes DIST-03), multi-agent in chat (M13), long-running/watch tasks (M14), skill marketplace (M15). File-watch-driven refresh, cross-repo search, LSP completion/hover/diagnostics, languages beyond the four headline servers.

---

## Phase M11: Voss-aware Tools (CAPS-01b)

**Goal:** Build the Voss-language-aware tooling that turns the harness's own runtime primitives into visible product surfaces — probable-value inspector, budget tracer, `.voss` lint-as-skill, `.voss` → Python diff viewer. This is the "unfair advantage" axis per [`notes/voss-agent-unfair-advantage.md`](notes/voss-agent-unfair-advantage.md): every feature exposes a runtime primitive to the user.

**Requirements:** VTOOL-01..05 — locked by `M11-CONTEXT.md` + `M11-VALIDATION.md` (no separate SPEC; user declined SPEC during discuss-phase).

**Seed source:** [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md) (capability 2)
**Thesis context:** [`notes/voss-agent-unfair-advantage.md`](notes/voss-agent-unfair-advantage.md) (the primary "why" for this phase)

**Headline deliverables:**
- `.voss` lint/type-check exposed as a first-class agent skill (callable from `.voss` workflows, not just `voss check`).
- Probable-value inspector — show confidence + propagation graph for a chosen value at a recorded runtime point.
- Budget tracer — visualize `ctx(budget:)` token consumption across a workflow run, frame-by-frame.
- `.voss` → Python diff viewer — when the agent edits a `.voss` file, user sees both sides synchronized.
- M9 TUI panels for each (render in main pane or modal — M9 region grid permitting).

**Planning note (2026-05-18):** `M11-CONTEXT.md` constrains the roadmap wording to existing recorded data only: "propagation graph" ships as a confidence-annotated decision sequence from `RunRecord.decisions[]`, and "frame-by-frame budget" ships as a per-agent-iteration token timeline from `RunRecord.iterations[]`. True lineage DAGs and per-`ctx(budget:)` frames require new emit points and are out of M11.

**Cross-cutting constraints:**
- Depends on M9 TUI shell for visual surfaces; can ship CLI-only first if M9 incomplete.
- Reuses `voss_runtime/{probable,budget,agent}.py` read-only (M9-baselined; no new emit points).
- Pairs with M4 dogfood compound — inspectors must work on the harness's OWN `.voss` workflows.

**Success Criteria:**
1. `voss-lint-as-skill` remains first-class reachable and M11 consumes its frozen version-1 JSON schema unchanged.
2. Probable inspector is available through CLI, slash, tool, and read-only TUI modal surfaces using recorded decisions only.
3. Budget tracer is available through CLI, slash, tool, and read-only TUI modal surfaces using recorded iterations only.
4. `voss vdiff voss/harness/agent/planner.voss` shows `.voss` source beside generated Python without source-map claims.
5. No changes land in `voss/harness/recorder.py` or `voss_runtime/{probable,budget,agent}.py`; all M11 tools are `is_mutating=False`.

**Plans:** 5 plans across 5 waves

Plans:
- [ ] M11-01-recorded-data-inspect-core-PLAN.md — Recorded decision sequence + budget timeline core helpers and tests.
- [ ] M11-02-probable-budget-surfaces-PLAN.md — Read-only tools, `voss inspect probable/budget`, `/probable`, `/btrace`.
- [ ] M11-03-lint-schema-integration-PLAN.md — Consume and verify T7 SKL-06 frozen JSON schema.
- [ ] M11-04-voss-python-diff-PLAN.md — `voss vdiff`, `/vdiff`, and `voss_py_diff` over source-vs-generated Python.
- [ ] M11-05-tui-and-final-guards-PLAN.md — Read-only TUI modals and phase-level no-emit acceptance guards.

**Out of scope:** Languages other than `.voss` (Python ecosystem handled by M10). Editor extensions (separate EDIT track). Live-replay debugger.

---

## Phase M12: MCP Bridge (CAPS-01c, promotes DIST-03)

**Goal:** Bridge Voss into the Model Context Protocol ecosystem — consume external MCP tools as harness tools, and expose harness skills as an MCP server so other agent runtimes can invoke Voss capabilities. Promotes the existing v0.2 candidate **DIST-03**.

**Requirements:** MCP-01..0N — TBD by `M12-SPEC.md`.

**Seed source:** [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md) (capability 3)
**Original candidate:** DIST-03 (see "Coding-agent v0.2 phases" section below; DIST-03 retired in favor of this formal phase).

**Headline deliverables (to be refined in SPEC):**
- MCP client — speak MCP over stdio + HTTP, surface remote tools through `voss/harness/tools.py` registry.
- MCP server mode — expose a curated subset of harness tools (`code_search`, `fs_read`, `voss_check`, etc.) as MCP endpoints for external clients.
- `.voss/mcp.yml` config — declare client connections + server-exposed surface.
- Permission scope — MCP tools default to `plan` mode (read-only); upgrade to `edit`/`auto` requires explicit user opt-in per server.

**Cross-cutting constraints:**
- Lazy connect — MCP servers connected on first tool invocation, not session start.
- Token/permission isolation — MCP tools execute in their own permission scope; never inherit unrestricted access.
- Audit trail — every MCP invocation logged through M2 RunRecorder.

**Success Criteria:** TBD by `M12-SPEC.md`.

**Out of scope:** MCP UI for browsing remote tool catalogs (could be M9 TUI panel follow-up). Cross-org MCP service registry. Encrypted MCP transports beyond what the protocol mandates.

---

## Phase M13: Multi-agent in Chat (CAPS-01d)

> ⊘ **ABSORBED into V8 — SHIPPED 2026-06-06.** V8 (V8-01/02/03) delivered the V4-backed persisted unification: the M13 in-memory `M13Allocator` was removed and replaced by the V4 `SessionTreeManager` (every chat spawn a persisted node; per-node-manager recursion bounded by the viable-floor, no depth constant; chat-root envelope finalized on exit). M13 artifacts/plans below are retained as reference (the in-memory design is superseded by V8); do not re-execute.

**Goal:** Expose the runtime `spawn`/`gather` primitives (`voss_runtime/agent.py`) to the user-facing chat session. A `voss chat` user can say "research X" → harness spawns sub-agent in a side panel (M9 `SubAgentPanel`), each sub-agent has its own budget meter, message bus is visible in the TUI.

**Requirements:** MAG-01..MAG-08 (locked by `M13-SPEC.md`).

**Plans:** 6 plans across 5 waves (W0→W1→W2[2 parallel]→W3→W4)

Plans:
- [ ] M13-01-PLAN.md — Wave 0 red scaffolds: shared scripted multi-agent provider conftest fixture + 5 new test files (fanout/steer/recursion/reveal/e2e) + additive keymap-baseline rows; back-compat guard
- [ ] M13-02-PLAN.md — `voss/harness/multiagent.py` foundation: `M13Allocator` (asyncio.Lock check-and-allocate, exactly-once release, viable-floor denial) + `ChildHandle` + `ChildRegistry`; resolves RESEARCH OQ-A1 (reserve/floor defaults)
- [ ] M13-03-PLAN.md — Wave 2A harness fan-out: non-blocking spawn/steer/status/gather tools + `PanelBridgeRenderer` + additive `steer_inbox` kwarg & line-830 drain in `agent.py`
- [ ] M13-04-PLAN.md — Wave 2B TUI bridge + reveal: wire dead `renderer.py:203` seam, `action_toggle_subagent_detail`, quiet-by-default panel body, `ctrl+o` keymap row
- [ ] M13-05-PLAN.md — Wave 3 recursion: slice-scoped sub-allocator handed to child toolset; depth>1 nested budget + nested panels (no depth constant)
- [ ] M13-06-PLAN.md — Wave 4 chat integration: additive `attach_multiagent_tools` in `cli.py` + headline stub-provider `voss chat` e2e

**Seed source:** [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md) (capability 4)
**Existing infra:** `voss/harness/subagents.py` (SubagentSpec/Registry, `attach_subagent_tool`); `voss_runtime/agent.py` (`VossAgent.spawn`, `AgentHandle`, `gather`).

**Headline deliverables (to be refined in SPEC):**
- Sub-agent invocation surface in `voss chat` — slash command + natural-language route.
- M9 `SubAgentPanel` populated by live sub-agent state — running, budget remaining, latest tool call, exit status.
- Cross-agent message bus visible in TUI.
- Budget partitioning — parent agent's `ctx(budget:)` budget split across spawned children, accounted in real time.

**Cross-cutting constraints:**
- Depends on M9 `SubAgentPanel` region (already in M9 plans).
- Compounds with M4 dogfood — the harness's own `.voss` workflows already use spawn/gather; this phase exposes that capability to USER `.voss` workflows + chat-initiated tasks.

**Success Criteria:** TBD by `M13-SPEC.md`.

**Out of scope:** Cross-machine distributed agents (deferred well beyond v0.2). Agent-to-agent direct messaging without harness mediation. Multi-agent memory partitioning beyond per-agent budgets.

---

## Phase M14: Long-running Tasks + Watch (CAPS-01e)

**Goal:** Voss gains a `watchdog`-backed file-watch backend exposed as an `fs_watch` agent tool emitting recorder events, plus a `voss watch <command>` CLI that re-runs a command on watched-file change with an opt-in `--daemon` flag — built on the existing T5 background job engine, headless-only this phase (M9 TUI status strip and M10 `code_refresh` hookback explicitly deferred per M14-SPEC.md).

**Requirements:** WATCH-01, WATCH-02, WATCH-03, WATCH-04, WATCH-05 (locked in `M14-SPEC.md`).

**Seed source:** [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md) (capability 5)

**Headline deliverables (to be refined in SPEC):**
- Background job manager — start/stop/status of long-running processes with structured handles.
- File-watch — register watchers on globs; emit events into the recorder stream for tool consumption.
- Dev-server / test-watcher integrations — `voss watch <command>` keeps a process alive across session lifecycle.
- M9 TUI bottom-pane status strip — running jobs, last-tick result, recent errors.
- M10 hookback — `code_refresh` can subscribe to file-watch events for live index updates.

**Cross-cutting constraints:**
- Depends on M9 TUI shell for status strip; ships headless first if M9 incomplete.
- Background jobs reaped on session exit unless explicitly daemonized via opt-in flag.
- File-watch backend cross-platform: `watchdog` Python lib for macOS/Linux/Windows.

**Success Criteria:** Per `M14-SPEC.md` acceptance criteria — watchdog pinned + importable; matching-glob edit yields exactly one coalesced recorder event in the debounce window; non-matching edit yields zero; `fs_watch` registered in one turn readable via cursor in a later turn; `voss watch 'pytest -q'` re-runs on change; non-daemon reaped on session exit (TERM <=2s/KILL <=5s); `--daemon` survives session exit; WATCH event tests green on macOS + Linux CI; shell allowlist enforced.

**Plans:** 4 plans across 4 waves (serial spine; W3 runs M14-03 ∥ M14-04 file-disjoint).

Plans:
- [x] M14-01-PLAN.md — Wave 0 scaffold: pin watchdog, 10 RED WATCH tests + reset/daemon-PID fixtures, macOS+Linux CI matrix (+ blocking package-legitimacy checkpoint pending before M14-02)
- [x] M14-02-PLAN.md — lifecycle spine: `_WATCHERS` registry + `WatcherRecord` + shared `_read_log_cursor` factor (D-02/D-04, OQ-1) + `watch/backend.py` watchdog Observer/Debouncer/asyncio bridge (D-01) + reap wiring
- [ ] M14-03-PLAN.md — `fs_watch` + `fs_watch_poll` agent tools in make_toolset, both `is_mutating=False` (WATCH-02, OQ-2)
- [ ] M14-04-PLAN.md — `voss watch` CLI (allowlist + re-run via T5 register_job) + `watch/daemon.py` `start_new_session` detach with `--_is-worker` guard (WATCH-03/04, OQ-3)

**Out of scope:** Distributed task scheduling. Cron-like recurring tasks (separate concern). Notification delivery (push/email/etc.).

---

## Phase M15: Skill / Plugin Marketplace (CAPS-01f)

**Goal:** Make third-party `.voss` skills installable via a `voss skill add <name>` workflow with signed manifests, a sandbox boundary, and a permission scope per skill. Build atop the existing `voss/harness/plugins.py` scaffold.

**Requirements:** SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05, SKILL-06 (6 locked — `M15-SPEC.md`).

**Plans:** 6 plans across 5 waves (planned 2026-05-19).

Plans:
- [x] M15-01-PLAN.md — Wave 0: RED skill test suite + cryptography direct dep + signed example bundle (human gate)
- [x] M15-02-PLAN.md — Wave 1: trust.py — Ed25519 detached-sig verify + pinned-key trust store [SKILL-03]
- [x] M15-03-PLAN.md — Wave 1: scope.py — declared scopes → existing PermissionGate (no new engine) [SKILL-04]
- [x] M15-04-PLAN.md — Wave 2: fetch + manifest schema + install/remove/update gating (staging→verify→copy) [SKILL-01, SKILL-05]
- [x] M15-05-PLAN.md — Wave 3: VossSkillAdapter + registry + voss skill CLI + RunRecorder audit [SKILL-02]
- [x] M15-06-PLAN.md — Wave 4: e2e fixture-cycle CI test + documented confinement limitation [SKILL-06]

**Seed source:** [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md) (capability 6)
**Existing infra:** `voss/harness/plugins.py` (`PluginManifest`, user/project plugin dirs, enablement TOML) — scaffold present, unused.

**Headline deliverables (to be refined in SPEC):**
- `voss skill add <name>` / `voss skill remove <name>` / `voss skill list` CLI surface.
- Skill manifest schema — capabilities declared, permission scopes required, dependency declaration.
- Sandbox boundary — third-party skill code runs with a restricted toolset (read-only by default; mutating tools require explicit user grant per skill).
- Manifest signing — cryptographic signature verification before install; trust roots configurable.
- Registry source — initial v0.2 ships GitHub-based registry (skills as repos with `voss-skill.yml` manifest); central registry is later.

**Cross-cutting constraints:**
- Hard prerequisite: sandbox + permission story BEFORE any third-party code runs. This is the highest-risk surface in the v0.2 cycle.
- Coordinates with M1 permission tiers (`plan`/`edit`/`auto`) — skills declare which tier they need.
- Audit trail — every skill invocation logged through M2 RunRecorder.

**Success Criteria:** The 10 acceptance criteria in `M15-SPEC.md` (add/list/run/trust/tamper-refuse/scope-deny/remove/update-tamper-intact/e2e-fixture/no-forbidden-subsystem).

**Out of scope:** Paid skills. Cross-org skill discovery (post-v0.2). Hot-reload of skills mid-session. Skill GUIs beyond TUI palette registration.

---

## T-prefixed phases: Daily-Driver Gap Closure

T-phases close known competitive gaps against Claude Code / Codex / Pi on
the surface that already exists. They add no new product surface — they
make `voss do` / `voss chat` feel like a coding agent users would reach
for daily. Full audit, sequencing rationale, and per-phase requirements
in [`notes/daily-driver-punch-list.md`](notes/daily-driver-punch-list.md).

**Status reconciliation (2026-06-02, H0.2):** T1, T2, T3, T4, T5 are
**implemented in code and covered by tests** — verified directly against the
tree, not inferred. Evidence: iteration while-loop + `max_iterations`
(`agent.py`), 3-provider `stream()` (`providers.py`), interrupt handler
(`agent.py:1052`), `asyncio.gather` read-batches + `fs_read_many`/`fs_edit_many`
(`agent.py`/`tools.py`), `web_fetch`/`web_search`/`net.py`/`mcp/` client+server,
`cache_control: ephemeral` + `cache_read_input_tokens` accounting (`agent.py`),
`shell_run_background` + `voss jobs` (`tools.py`/`cli.py`); test files
`test_anthropic_stream`, `test_openai_stream`, `test_renderer_streaming`,
`test_recorder_iterations`, `test_cache_*`, `test_cost_*`, `test_web_fetch`,
`test_web_search`, `test_cli_mcp`, `test_t5_shell`, … The earlier `TBD` cells
were stale; the harness is more capable than these docs claimed. T7 (Skills
Bootstrap) is **not** verified here — left `TBD`. The "What M5/M6 don't fix"
gap table in the punch-list predates these landings; read it as historical.

**Versioning split:**
- **v0.1.1 patch** — T6 only. PRD §2.4 promised those slashes; shipping
  them is closing a contract bug, not adding a feature.
- **v0.2.0 minor** — T1–T5, T7, T8 (alongside M8 + M9 + M10). Daily-driver
  table stakes complete.
- **v0.3.0+** — M11–M15. Unfair-advantage features (Voss-aware tools,
  MCP server, multi-agent in chat, watch, marketplace).
- **v1.0.0** — API lock once dogfood signals public surface is stable.

### Phase T6 — PRD §2.4 Slash Debt *(v0.1.1 patch)*

**Goal:** Ship the slash commands the PRD promised and the user expects.
Most are 20-line wrappers around existing data. Closes M1's PRD-conformance
gap. Treated as a v0.1.1 patch rather than v0.2 minor because each missing
slash is a documented contract bug from v0.1, not a new capability.

**Requirements (proposed):** SLASH-01..07

- SLASH-01 `/diff` — show pending unapplied edits.
- SLASH-02 `/apply` — apply pending edits explicitly (plan mode).
- SLASH-03 `/discard` — drop pending edits.
- SLASH-04 `/budget <usd>` — adjust remaining session budget at runtime.
- SLASH-05 `/resume <id|name>` — load a prior session into the live REPL.
- SLASH-06 `/why` — render last plan's rationale + `ProbableValue`
  confidence breakdown (PRD's "killer feature").
- SLASH-07 `/cost --by-model` / `--by-tool` flags.

**Success Criteria (Met — 2026-05-18):**
1. **SC#1** — Each slash in PRD §2.4 has ≥1 integration test exercising the happy path (T6-03 completed the set; `/discard` confirmed pre-covered).
2. **SC#2** — `/why` renders confidence + rationale from the most recent `Plan` with **no** provider call (D-07 audit test + existing `_why` implementation).
3. **SC#3** — Grouped in-REPL `/help` (Editing/Session/Insight/Control + Other long-tail) + one-line signpost in **both** production `voss --help` and `python -m voss.harness --help` (T6-02). No slash-list duplication.

All three criteria verified. T6 (v0.1.1 patch) **complete**.

**Cross-cutting constraints:**
- No new persistence. Slashes operate on the live `ReplContext`.
- M9 SlashPalette autocomplete includes all seven (M9-03 reserves slot
  names already).

---

### Phase T1 — Iteration Loop + Streaming + Interrupt *(v0.2 lead)*

**Goal:** Replace the single-shot plan→execute→done flow with a real agent
loop that re-plans on tool results, streams text as it arrives, and
cancels cleanly on user interrupt.

**Requirements (proposed):** ITER-01..06

- ITER-01 `_run_turn_exec` is a while-loop. Exits on agent-emitted `done`,
  max-iteration cap, or budget exhaustion.
- ITER-02 Tool results feed back into model context for next iteration.
- ITER-03 Provider switches from `complete` to `stream`; TurnView renders
  incremental deltas.
- ITER-04 `action_interrupt` (`tui/app.py:79`) cancels the in-flight
  asyncio task and surfaces "interrupted" in the recorder.
- ITER-05 Confidence gate moves from per-turn to per-loop-exit. Mid-loop
  low confidence triggers another iteration, not `/clarify`.
- ITER-06 Telemetry records iteration count, per-iteration cost, exit
  reason (done / max-iter / budget / interrupt).

**Success Criteria (proposed):**
1. M5 golden task #2 ("rename-symbol") completes in one `voss do` without
   user re-prompting.
2. First visible token in TurnView ≤ 500ms after provider acceptance.
3. `action_interrupt` cancels an in-flight turn and produces a closed
   recorder entry within 100ms.
4. Default max iteration = 8, configurable via `harness.toml`. Hit-cap
   produces structured "halted: max-iter" final, not a crash.

**Cross-cutting constraints:**
- Each iteration is a sub-record under one Turn (not N Turns) — preserves
  M2 `RunRecord` schema for `voss resume` compatibility.
- `_substitute_placeholders` is removed. Prior results flow via context.
- This phase is the **breaking behavior change** that justifies v0.2.

**Plans:** 7 plans across 5 waves

Plans:
- [ ] T1-01-PLAN.md — Schema substrate: IterationRecord + additive RunRecord fields + RunRecorder.begin_iteration/end_iteration
- [ ] T1-02-PLAN.md — ProviderStreamEvent union + StreamingProvider Protocol + ParsedPlan terminal event (placeholder stream() bodies)
- [ ] T1-03-PLAN.md — Concrete AnthropicOAuthProvider.stream() + OpenAIOAuthProvider.stream() with OAuth refresh + graceful httpx aclose + parity test
- [ ] T1-04-PLAN.md — TurnView.stream_delta/finalize_stream + RuntimeConfig.max_iterations + [agent] section TOML loader
- [ ] T1-05-PLAN.md — Rewrite _run_turn_exec as while-loop, delete _substitute_placeholders, PLAN_LOOP_SYSTEM + per-iter rider, per-iter telemetry
- [ ] T1-06-PLAN.md — VossTUIApp.active_turn_task + action_interrupt body + CancelledError handler in _run_turn_exec + cli.py register_turn_task
- [ ] T1-07-PLAN.md — SPEC 12-checkbox acceptance suite + grep gate + M5 golden #2 one-shot + CI workflow step

---

### Phase T4 — Prompt Caching + Cost Truthfulness *(v0.2)*

**Goal:** Stop rebuilding the system prompt every turn. Track cost
honestly including cache reads.

**Requirements (proposed):** CACHE-01..04

- CACHE-01 Anthropic provider adds `cache_control: {type: "ephemeral"}`
  to the cognition block + VOSS.md block.
- CACHE-02 Cost accounting reads `cache_creation_input_tokens` +
  `cache_read_input_tokens` from response, prices at Anthropic rates.
- CACHE-03 `/cost` gains `--by-model` / `--by-tool` (overlaps T6 SLASH-07;
  ship whichever lands first).
- CACHE-04 OpenAI provider adopts equivalent caching when model reports
  eligibility.

**Success Criteria (proposed):**
1. Two consecutive turns in a `voss chat` session show
   `cache_read_input_tokens > 0` on the second turn.
2. `/cost --by-model` matches `sum(per-turn cost_usd by model)` to 4
   decimals.
3. Reported cost includes cache cost, not just non-cached input.

**Cross-cutting constraints:**
- Cache key stable across turns; VOSS.md drift invalidates the cache
  (acceptable).
- Cache TTL = 5 minutes (Anthropic default); documented in `harness.toml`.

**Plans:** 6 plans

Plans:
- [x] T4-01-test-scaffold-PLAN.md — Wave 0: 9 failing test stubs + cassette README + pyproject pin bumps (litellm>=1.74.0, vcrpy>=8,<9)
- [x] T4-02-extractor-and-non-streaming-PLAN.md — `_cache_tokens.extract_cache_tokens` + `ProviderResponse` additive fields + LiteLLMProvider wiring (CACHE-02 non-streaming)
- [x] T4-03-agent-composition-PLAN.md — `_compose_system_blocks` + multi-block `messages[0]` + four-drift invalidation tests (CACHE-01, CACHE-06)
- [x] T4-04-streaming-telemetry-recorder-PLAN.md — Usage variant + agent.py Usage consumer + provider.response telemetry payload + IterationRecord round-trip (CACHE-02 streaming, CACHE-07 telemetry/round-trip)
- [x] T4-05-cost-truth-and-cli-PLAN.md — D-09 placeholder edit + LiteLLM cost-differential test + /cost --by-model 4-decimal verification (CACHE-03, CACHE-04)
- [x] T4-06-cassette-integration-PLAN.md — [BLOCKING human-action] one-time live cassette recording + two-turn replay test (CACHE-05, CACHE-07 invariant)


---

### Phase T2 — Parallel Tools + Multi-Edit Primitive *(v0.2)*

**Goal:** Read-only steps execute in parallel (bounded by
`agent.max_parallel_reads`). Mutations stay strictly serialized. File
edits can batch multiple replacements atomically through the M9-05
DiffModal. Prove ≥40% wall-clock drop on a self-contained 6-read
micro-benchmark (M5 eval baseline is empty — own benchmark replaces it).

**Requirements (locked via T2-SPEC.md):** PAR-01..06

- PAR-01 `_run_step_loop` partitions steps into read-only batches +
  mutating singletons. Read-only batches run via `asyncio.gather`
  bounded by `asyncio.Semaphore(agent.max_parallel_reads)`.
- PAR-02 Partition-time invariant: every step in a multi-step batch has
  `ToolEntry.is_mutating == False`; violation raises
  `BatchInvariantError` (additive 5th exit_reason value).
- PAR-03 New tool `fs_edit_many(path, edits=[{old, new}, ...])` —
  validate-then-write-once atomicity through M9-05 DiffModal; reject-any
  or skip-any → batch denied.
- PAR-04 New tool `fs_read_many(paths=[...])` — bundled response
  `=== {path} ===\n{content}\n` per slot, per-slot error envelopes,
  30KB per-file cap, partial-result semantics.
- PAR-05 `harness.toml [agent] max_parallel_reads = 8` (range 1-32,
  out-of-range falls back with RuntimeWarning) + self-contained
  micro-benchmark proving ≥40% wall-clock drop.
- PAR-06 `batch.start` / `batch.end` telemetry events for multi-step
  batches only; per-step `tool.call` / `tool.result` preserved
  unchanged; `IterationRecord.batches: list[BatchRecord]` additive
  M2-compatible schema.

**Success Criteria:**
1. `tests/perf/test_parallel_read_speedup.py` micro-benchmark passes:
   parallel wall-clock ≤ 60% of serial baseline (≥40% drop) on a
   stub-timed 6-read batch.
2. `fs_edit_many` rejects entire batch if any `old` doesn't match
   uniquely; recorder logs offending index; file byte-for-byte unchanged
   on disk after rejection.
3. Mutation step in a read batch raises `BatchInvariantError`; partitioner
   never produces such a batch from author-order input.
4. Read-only steps from a real `voss do` invocation produce visible
   `batch.start`/`batch.end` telemetry events and populate
   `RunRecord.iterations[i].batches`.

**Cross-cutting constraints:**
- Diff modal (M9-05) handles multi-edit via per-hunk approval — `fs_edit_many`
  builds list[Hunk] itself and calls `renderer.show_diff_modal` directly;
  PermissionGate stays single-edit (D-01).
- Mutation classification checked at registration via `ToolEntry.is_mutating`
  (M1 D-06 invariant); no tool-name pattern matching.
- `RunRecord` schema additions are additive-only; pre-T2 records round-trip
  unchanged (M2 + T1 invariant).
- Author order non-negotiable: a read step never executes before a write
  authored earlier in `plan.steps`; reads after a write run in the NEXT
  batch, never hoisted.
- `agent.max_parallel_reads` config knob co-locates with T1's
  `agent.max_iterations` in the same `[agent]` block of
  `~/.config/voss/config.toml`.

**Plans:** 6 plans across 5 waves

Plans:
- [ ] T2-01-PLAN.md — Schema substrate: BatchRecord dataclass + IterationRecord.batches additive field + RunRecorder.begin_batch/end_batch capture API
- [ ] T2-02-PLAN.md — Config knob: RuntimeConfig.max_parallel_reads + get_max_parallel_reads loader (range 1-32 + fallback warning) + cli.py bootstrap wire-in
- [ ] T2-03-PLAN.md — Partition scheduler rewrite + BatchInvariantError + batch.start/end telemetry + recorder wiring + _run_turn_exec exit_reason="batch-invariant" handler
- [ ] T2-04-PLAN.md — fs_edit_many tool (atomic validate-then-write-once, M9-05 DiffModal integration with strict skip-is-deny semantics)
- [ ] T2-05-PLAN.md — fs_read_many tool (bundled response, per-slot error envelopes, 30KB per-file cap, partial-result semantics)
- [ ] T2-06-PLAN.md — Self-contained micro-benchmark (≥40% wall-clock drop) + phase-final human-verify checkpoint

---

### Phase T3 — Network Surface (WebFetch + WebSearch + MCP client) *(v0.2)*

**Goal:** Give the agent access to live documentation and external tools
without inventing a new protocol. Gate network at the harness boundary.

**Requirements (proposed):** NET-01..07

- NET-01 New tool `web_fetch(url)` via `httpx`. Honors `tools.allow_net`
  config flag (HARNESS-PLAN §6 — currently declared, unenforced).
- NET-02 New tool `web_search(query)`. Default no built-in backend; opt-in
  Brave / Tavily via API key. (DuckDuckGo HTML rejected — fragile +
  rate-limited.)
- NET-03 MCP client over stdio — lift Codex's launcher pattern. Configure
  via `.voss/mcp.yml`.
- NET-04 MCP tool permission scope defaults to `plan` (read-only).
  Mutation requires explicit user opt-in per server in `permissions.yml`.
- NET-05 Network tools off by default; `voss --allow-net` or
  `tools.allow_net = true` opts in.

**Required commands:**
```
voss mcp list                   # registered MCP servers
voss mcp call <server> <tool>   # debug: invoke directly
```

**Success Criteria (proposed):**
1. Default install has no network access; opt-in is one config line.
2. `voss mcp call` works against the Anthropic reference MCP filesystem
   server out of the box.
3. M5 eval gains task #6 "fetch + summarize" requiring `web_fetch`.

**Cross-cutting constraints:**
- Path-jail + shell allowlist do not apply to network tools — sandbox is
  per-tool-class.
- MCP server processes reaped on session exit (mirror M10 LSP pattern).
- Network telemetry events `net.request` / `net.response` with redacted URLs.
- This phase reduces M12's scope to "expose harness as MCP server only" —
  the client side ships here.


**Plans:** 9 plans across 6 waves

Plans:
- [ ] T3-01-PLAN.md — Wave 0 scaffolding: lifecycle.py SIGTERM+5s+SIGKILL reap + 9 NET-XX placeholder test files (32 named test stubs)
- [ ] T3-02-PLAN.md — Permission gate net-check + RuntimeConfig.allow_net + [tools] allow_net loader + --allow-net CLI flag (NET-05; ToolEntry.is_network axis)
- [ ] T3-03-PLAN.md — telemetry.redact_url + net.request/response + mcp.request/response event-shape contract (NET-06)
- [ ] T3-04-PLAN.md — rate_limit.py TokenBucket primitive + [net.rate_limits] TOML parser w/ escaped-dot regex (NET-07)
- [ ] T3-05-PLAN.md — net.py NetSession + web_fetch tool (1 MB cap, timeout clamp, error envelopes) + transport-level zero-socket proof (NET-01)
- [ ] T3-06-PLAN.md — web_search.py BraveBackend + NetSession.search + dedup-by-URL + count clamp + 429 handling (NET-02)
- [ ] T3-07-PLAN.md — mcp/{__init__,config,client,registry}.py: ${VAR}/{cwd}/env-allowlist loader + 2025-11-25 handshake + lazy launch + destructiveHint scope mapping (NET-03, NET-04)
- [ ] T3-08-PLAN.md — voss mcp {list,call} click group + --arg JSON-with-string-fallback parsing (NET-03 CLI surface)
- [ ] T3-09-PLAN.md — .github/workflows/mcp-integration.yml CI job + M5 eval task #6 fetch+summarize + httpx MockTransport stub injection (BLOCKING human-verify checkpoint for npm version + read-tool-name pin)

---

### Phase T5 — Shell Ergonomics *(v0.2)*

**Goal:** Real builds and test runs survive the shell tool. Long-running
tasks don't block the agent.

**Requirements (proposed):** SHELL-01..05

- SHELL-01 `shell_run` default output cap raised 4KB → 30KB.
- SHELL-02 New `shell_run_background(cmd) -> handle` — detached process,
  reaped on session exit.
- SHELL-03 New `shell_monitor(handle, since_ms=0) -> chunk` — incremental
  stream.
- SHELL-04 New `shell_signal(handle, signal="INT"|"TERM")`.
- SHELL-05 `voss jobs` CLI lists running background processes for the
  current session.

**Success Criteria (proposed):**
1. A 20-second background job is observable via `shell_monitor` from a
   second agent turn.
2. Orphaned background jobs get SIGTERM within 2s, SIGKILL at 5s on
   session exit.
3. Per-process cap: 100MB memory, 30s no-output watchdog kills the job;
   recorder logs.

**Cross-cutting constraints:**
- Shell allowlist still applies to background commands.
- Background jobs do not inherit the agent's TTY.
- This is the headless half of M14 (file-watch). M14 layers `watchdog`
  on top.

**Plans:** 5 plans

Plans:
- [x] T5-01-test-scaffold-and-psutil-dep-PLAN.md — Wave 1: failing test surface (SHELL-01..05 + SC#1/#2/#3) + emit.py fixture + `_JOBS` reset + `30720` source guard + [BLOCKING human-verify] psutil legitimacy gate then `psutil>=5.9,<8` dep add
- [x] T5-02-shell-run-cap-raise-PLAN.md — Wave 2: SHELL-01 cap 4096→30720 in both `shell_run` AND `_shell_capture` (Flag 1: raise both); envelope + 30s timeout untouched
- [x] T5-03-job-registry-and-background-spawn-PLAN.md — Wave 3: JobRecord + atomic `.meta.json` sidecar + `_JOBS` registry + `register_job`/`reap_jobs`/`signal_job` + single supervisor task (pump+30s+100MB) + `start_new_session`/killpg + `shell.background.reap` + `shell_run_background` (SHELL-02, SC#2/#3, D-01/02/05/08/09/10/11)
- [x] T5-04-monitor-signal-and-permissions-PLAN.md — Wave 4: `shell_monitor` cursor read + `shell_signal` INT/TERM + 2 ToolEntry regs + D-12 edit-mode deny (explicit name-set) + permissions_bridge verbs (SHELL-03/04, SC#1, D-03/06/12)
- [x] T5-05-voss-jobs-cli-and-active-session-PLAN.md — Wave 5: production `make_toolset(session_id=record.id)` wiring (cli.py:1314 `_run_repl` only — closes the cross-process contract; other 5 sites deliberate `_nosession`) + `jail_path` import + `voss jobs` table/`--json` sidecar read + AGENT_COMMANDS + `.active-session` try/finally lifecycle + `--keep-logs` + explicit `reap_jobs()` (SHELL-02/05, D-04/09/11, A4)

---

### Phase T7 — Skills Bootstrap *(v0.2)*

**Goal:** Ship 6 ready-to-use skills so the registry isn't just a hook.

**Requirements (proposed):** SKL-01..06

- SKL-01 `rename-symbol` — anchor + scope-aware rename across the repo.
- SKL-02 `add-test` — locate a public function, generate a unit test.
- SKL-03 `summarize-diff` — pipe `git diff` → PR description.
- SKL-04 `port-py-to-voss` — Python → `.voss` for classify/support/research
  sample shapes.
- SKL-05 `audit-cognition` — re-run analyze against drift; propose a
  paragraph update to `architecture.md`.
- SKL-06 `voss-lint-as-skill` — wraps `voss check` with structured
  diagnostic output. Foundation for M11.

**Success Criteria (proposed):**
1. Every skill invokable via `/skill <id>`, runs to completion on a
   reference repo without permission escalation.
2. Skills pair 1:1 with M5 eval tasks where applicable.

**Cross-cutting constraints:**
- Skills authored in `.voss` where the language expresses them; otherwise
  Python with a `.voss` lint pass demonstrating composability.
- Unblocks M15 (marketplace) but doesn't require it.

---

### Phase T8: Input Bar Ergonomics (v0.2)

**Goal:** The input bar stops being the slowest part of the loop.

**Requirements (proposed):** INPUT-01..05

- INPUT-01 Multi-line input via `Shift-Enter`; `Enter` submits.
- INPUT-02 `!<cmd>` prefix runs an allowlisted shell command without
  spawning a turn.
- INPUT-03 `#<text>` prefix appends a memory note to `VOSS.md` without
  spawning a turn.
- INPUT-04 `Ctrl-R` reverse-search through episodic history.
- INPUT-05 Paste-image detection — if clipboard has an image and the
  model supports it, attach as a vision input.

**Success Criteria (proposed):**
1. All five behaviors covered by Textual snapshot tests.
2. `!` and `#` shortcuts emit recorder events (`shell.local` /
   `memory.note`) and bypass `run_turn`.

**Status:** Complete (5/5 plans summarized, 2026-05-18). Focused T8 verification: 53 tests / 11 snapshots passed.

**Cross-cutting constraints:**
- M9 keymap (`tui/keymap.py`) is the source of truth — this phase only
  adds bindings.

**Plans:** 5 plans across 4 waves (W0 scaffold → W1 TextArea swap → W2 prefix-dispatch ‖ TUI-submit-wiring → W3 Ctrl-R + paste-image)
- [x] T8-01-PLAN.md — Wave 0: pytest-textual-snapshot + hermetic fixtures + `.value`→`.text` migration + red scaffolds (INPUT-01..05 substrate)
- [x] T8-02-PLAN.md — INPUT-01: Input→TextArea swap, Enter/Shift+Enter inversion, autogrow 1-5, slash guard, additive `ctrl+r` keymap line
- [x] T8-03-PLAN.md — INPUT-02/03: `!cmd` via existing T5-D12 gate + `#note` to `## Notes` human section; run_turn bypass; `shell.local`/`memory.note` recorder events
- [x] T8-04-PLAN.md — Enabling deliverable (RESEARCH A4): `on_input_bar_submitted`→run_turn wiring + `_run_repl` interactive Textual loop + `app.history` for Ctrl-R corpus
- [x] T8-05-PLAN.md — INPUT-04 Ctrl-R inline reverse-i-search (per-project episodic) + INPUT-05 paste-image attach / no-vision transient notice

**Scope note (RESEARCH A4 — recorded):** `make_renderer` builds `TextualRenderer(VossTUIApp())` but `app.run()` is never called and `_run_repl` uses synchronous `input()`. Without the T8-04 submit→run_turn wiring INPUT-01..05 are structurally unobservable in a real session. T8-04 is an in-scope ENABLING deliverable (planner option a), not scope creep.

---

## A-prefixed phases: voss-app Desktop ADE

**Track:** voss-app — terminal-grid desktop ADE in `apps/voss-app/`. Sibling deliverable to the Python harness. Tauri (Rust core) + Solid (webview UI) + xterm.js + `portable-pty`.

**Layering** (full detail in `apps/voss-app/CONCEPT.md`):
- **Layer 1 / v0 = A1–A11** — terminal-grid scaffold. **Zero Voss code in binary.** Ships as competitive Warp/Wezterm alternative.
- **Layer 2 / v1 = A12+** — Voss harness substrate. Promote-to-cell, streaming render, permissions, reviewer-as-pair-programmer demo. Locks once L1 ships.
- **Layer 3 / v2 = A21+** — `.voss` DSL features (hot-reload, inter-cell DSL wiring, curated loop library).
- **Layer 4+ / deferred** — Monaco editor pane, file tree, SCM, search. Uncommitted; evaluate post-L3.

**Reference design:** sketch 001 Variant B (Minimal Tile) — `.planning/sketches/001-voss-grid-shell/`. 22px headers, thin 1px borders, mono everywhere, glyph-prefix lines, inset-shadow focus.

**Cross-A constraints:**
- v0 must be usable as a daily terminal without the word "Voss" appearing in the UI beyond the app name.
- `.voss/` directory is forward-compat only in L1 (empty unless user customizes settings) — schema versioned `{"version": 1}`.
- Cost meter in status bar is stubbed `$0.00` in L1; comes alive in L2.
- All A phases share the Variant B aesthetic tokens (default) — A8 adds a full theme engine with VSCode theme import, but Variant B remains the canonical default.
- **Workspaces (A8) are the top-level container** — each workspace owns an isolated pane tree, project cwd, layout, and session state. A5 (Project Open) handles folder-picker mechanics; A6 (Session Persist) extends to multi-workspace persistence; A10 (Status Bar) scopes to active workspace.
- Project-wide spec-blocking questions **closed 2026-05-16** — full decisions in `apps/voss-app/CONCEPT.md` §10. Highlights: ship name = **Voss ADE** (Q1); auto-`$SHELL` on pane open (Q2); banner + restart on exit (Q3); pure-visual presets in L1 (Q4); first-class project-less mode (Q5); no cost meter in L1 (Q6); lazy `.voss/` creation (Q7); three distribution channels — Direct + Homebrew + npm subcommand (Q8); telemetry OFF default, opt-in (Q9).

---

### Phase A1: voss-app Tauri Shell

**Goal:** Tauri + Solid empty window builds and runs locally on the dev's platform with custom titlebar and theme tokens applied. **No release pipeline, no signing, no distribution channels** — that work is consolidated into A11 (release is a final gate; the app does not ship until A1–A10 are built).

**Requirements (locked at SPEC):** SHL-01..06
- SHL-01 Tauri version pinned (2.x recommended; SPEC confirms).
- SHL-02 Solid + Tailwind UI scaffolded with Variant B theme tokens.
- SHL-03 Custom titlebar with project-name placeholder, layout-preset switcher (visual only, no behavior yet). No cost-meter slot (Q6).
- SHL-04 Window: traffic lights (mac) · standard close/min/max (linux/win) · zoom · fullscreen · multi-monitor.
- SHL-05 `pnpm tauri dev` runs the app locally; `pnpm tauri build` produces an **unsigned local artifact** for the dev's own platform (smoke-test only — not a release artifact).
- SHL-06 Window title + About dialog use the **Voss ADE** ship name (Q1); `voss-app` retained only as repo / npm-package slug.

**Success Criteria (proposed):**
1. `voss-app` launches as an empty Tauri window on the dev's platform.
2. Titlebar renders Variant B tokens; theme swappable via config file.
3. `pnpm tauri build` produces a runnable unsigned local artifact.


**Plans:** 4 plans across 4 waves (sequential — each layer compiles on the prior; VALIDATION.md sampling rule favors a compile/smoke check between layers)
- [ ] A1-01-PLAN.md — Monorepo wiring + Tauri/Solid/Tailwind scaffold + pinned versions; empty 'Voss ADE' window (SHL-01, SHL-06)
- [ ] A1-02-PLAN.md — Full Variant B token system + Tailwind @theme inline + Rust get_theme_overrides settings seam (SHL-02)
- [ ] A1-03-PLAN.md — Custom 22px titlebar + macOS traffic-light controls + visual-only preset switcher (SHL-03, SHL-04)
- [ ] A1-04-PLAN.md — Hardened CSP + unsigned `pnpm tauri build` smoke + About-panel ship name + A11 cert-procurement clock (SHL-05, SHL-06)

**Cross-cutting constraints:**
- No xterm, no PTY, no grid in A1 — pure window scaffolding.
- **No release/CI/signing/Homebrew/npm work in A1** — moved to A11.
- Settings load from `~/.config/voss-app/settings.json` if present; else baked defaults.
- `apps/voss-app/src-tauri/` is a new Rust crate consuming `crates/voss-app-core/` (created empty here, populated by later A phases).

---

### Phase A2: voss-app PTY Pane

**Goal:** A single xterm.js pane wired to a native PTY (`portable-pty`) with full TTY support, scrollback, copy/paste, and OSC sequence handling. Replaces the empty window from A1 with one working terminal.

**Requirements (locked at SPEC):** PTY-01..0N
- PTY-01 `portable-pty` spawns user's `$SHELL` with `TERM=xterm-256color`, `COLORTERM=truecolor`.
- PTY-02 xterm.js renders the PTY; bidirectional stream (stdin / stdout / stderr).
- PTY-03 10k-line scrollback default, configurable. `⌘F` search in scrollback. `⌘⇧K` clear.
- PTY-04 Copy/paste: `⌘C` selection or interrupt (configurable), `⌘V` w/ bracketed-paste safety, `⌘⇧V` literal.
- PTY-05 OSC 8 hyperlinks (`⌘+click` opens URL). File-path auto-detection in output → `⌘+click` opens in OS.
- PTY-06 Process indicator in pane header (foreground command parsed from OSC 0).
- PTY-07 Shell exit behavior — pane shows `[exited N]` banner with "restart" button (assumes Q3 closes this way; SPEC reconfirms).
- PTY-08 Alt-screen apps (`vim`, `htop`, `less`, `tmux`) render correctly inside the pane.

**Success Criteria (proposed):**
1. Run `vim`, `htop`, `tmux`, `less` inside the pane — alt-screen + TTY signals work.
2. Scrollback persists across pane resize.
3. Copy from one OS app, paste into pane (bracketed-paste warns on multi-line).
4. Hyperlink click opens browser.

**Cross-cutting constraints:**
- Single pane only in A2 — multi-pane is A3.
- Pane occupies the whole window minus titlebar + status bar (status bar stubbed; A9 finishes it).

**Plans:** 5 plans across 4 waves
- [ ] A2-01-PLAN.md — Wave 0 scaffold: red test suite, xterm v5.5.0 pin, voss-app-core crate, D-01/legitimacy gate (W1)
- [ ] A2-02-PLAN.md — Rust PTY core: spawn/stream/resize/exit/backpressure/SIGINT + pgid fallback (W2)
- [ ] A2-03-PLAN.md — Solid pane + Tauri Channel IPC + D-02 rAF coalescing & watermark (W2)
- [ ] A2-04-PLAN.md — Paste-guard, ⌘C/SIGINT, find/clear, OSC8 links, fg-header, exit/restart (W3)
- [ ] A2-05-PLAN.md — D-02 flood-perf build-failing gate + PTY-08 alt-screen manual matrix (W4)

---

### Phase A3: voss-app Grid Engine

**Goal:** Multi-pane grid layout — binary-split tree, splits/focus/resize/close, `⌘1-9` numeric nav, an **in-memory Solid→Rust layout mirror (no disk persistence in A3 — A4/A6 own file I/O)**. Each pane is an independent PTY from A2.

**Requirements (locked at SPEC):** GRD-01..0N
- GRD-01 Pane tree model: binary splits (horizontal/vertical), tmux-style.
- GRD-02 `⌘\` split horizontal, `⌘⇧\` split vertical, `⌘D` fork (duplicate cwd + shell), `⌘W` close (confirm if running).
- GRD-03 Focus: `⌘1`-`⌘9` numeric, `⌘⌥` arrow directional, click-to-focus, `⌘[`/`⌘]` cycle.
- GRD-04 Resize: drag border, `⌘⌥⇧` arrow 5% increments, `⌘=` equalize.
- GRD-05 Per-pane min size (cols × rows) enforced.
- GRD-06 22px Variant B pane header: `●` dot · index · cwd basename · shell · process indicator · `⋯` menu.
- GRD-07 Focused pane indicated by inset shadow + bg lift (no border ring).
- GRD-08 Layout state stored in Solid signals, mirrored to Rust core for persistence.

**Success Criteria (proposed):**
1. 2×2 grid created via 3 splits; each pane runs an independent shell.
2. Focus follows click and `⌘1-4`. Directional focus works.
3. Resize via drag and keyboard.
4. Close pane: confirm if process running, no-confirm if idle.

**Cross-cutting constraints:**
- Grid model decision (binary-tree vs css-grid vs flex) closes at SPEC.
- No layout presets in A3 — that's A4.

**Plans:** 6 plans across 5 waves
- [ ] A3-01-PLAN.md — Binary-split tree model + Solid store + voss-app-core Rust mirror + sync seam (GRD-01, GRD-08)
- [ ] A3-02-PLAN.md — Split/fork/close/equalize mutations + 20×5 floor guard + D-04 close (GRD-02, GRD-05)
- [ ] A3-03-PLAN.md — Numeric/i3-directional/click/cycle focus + drag/keyboard resize w/ 20×5 clamp (GRD-03, GRD-04, GRD-05)
- [ ] A3-04-PLAN.md — Recursive renderer + drag handles + global keymap + inset-shadow focus treatment (GRD-01, GRD-03, GRD-04, GRD-07)
- [ ] A3-05-PLAN.md — 22px Variant B header (index + ⋯) + 5-item menu + foreground-gated close-confirm (GRD-02, GRD-06, GRD-07)
- [ ] A3-06-PLAN.md — App integration + e2e acceptance + 9-pane Canvas perf/flood benchmark + mirror parity (GRD-01..08)

---

### Phase A4: voss-app Layout Presets

**Goal:** Visual layout templates — `fanout · pipeline · swarm · watchers`. `⌘G` cycles. Switching reorders existing panes, never kills them. Save/load named layouts.

**Requirements (locked at SPEC):** LAY-01..0N
- LAY-01 Four presets: fanout (1 source left, N receivers right column) · pipeline (left-to-right equal row) · swarm (N×N equal grid, default 2×2 up to 4×4) · watchers (main top, 2-3 thin watchers bottom).
- LAY-02 Titlebar switcher widget (sketch 001 Variant B styling).
- LAY-03 `⌘G` cycles presets in order.
- LAY-04 Switching preset reorders existing pane tree; never destroys panes.
- LAY-05 If pane count doesn't match preset capacity, panes added/preserved gracefully (no panes destroyed).
- LAY-06 "Save layout as…" + "Load layout…" in command palette (palette delivered in A7; stub command exists earlier).
- LAY-07 Layout file format: `.voss/layouts/<name>.json` with versioned schema.
- LAY-08 L1 semantics: pure visual templates. Layer 2 will overlay behavior — L1 must not couple.

**Success Criteria (proposed):**
1. Switch between all 4 presets with `⌘G`; layout reorders predictably.
2. Save a named layout, modify, reload — geometry restored.
3. Open a project with a saved default layout in `.voss/layouts/default.json`.

**Cross-cutting constraints:**
- Preset semantics question (CONCEPT §10 Q4) must close before SPEC — L1 visual-only is the recommendation.

**Plans:** 6 plans across 5 waves (planned 2026-05-19; A4-00 blocks on A3-06 substrate).

Plans:
- [ ] `A4-00-PLAN.md` — Blocking A3-06 substrate preflight; verify GridRoot is live in App, Rust grid sync commands are registered, and A3 integration/perf summary exists before A4 changes begin.
- [ ] `A4-01-PLAN.md` — Pure preset transform model for fanout/pipeline/swarm/watchers, fixed cycle order, count-weighted ratios, and id-preserving capacity handling.
- [ ] `A4-02-PLAN.md` — Controlled titlebar switcher, `custom` state, `Cmd+G` cycle injection, and GridRoot/App ownership wiring.
- [ ] `A4-03-PLAN.md` — Rust versioned layout schema plus safe `.voss/layouts/<name>.json` save/load/list/default commands.
- [ ] `A4-04-PLAN.md` — Frontend save/load command wrappers, exact command copy, loaded-layout remap semantics, and default-layout apply path.
- [ ] `A4-05-PLAN.md` — Requirement-level acceptance, e2e smoke, full verification, and manual Variant B visual sign-off.

---

### Phase A5: voss-app Project Open

**Goal:** Folder picker, recent workspaces list, `.voss/` directory lazy creation, git branch detection, optional project-less mode.

**Requirements (locked at SPEC):** WS-01..0N
- WS-01 `⌘O` folder picker; drag-drop folder onto app icon to open.
- WS-02 Recent workspaces list (last 10, pinned favorites). Stored at `~/.config/voss-app/recents.json`.
- WS-03 `.voss/` dir lazily created on first action that needs it (settings write, layout save) — never auto on project open in L1.
- WS-04 Git branch read via `git2` Rust crate (no shelling out). Surfaced in status bar (A9).
- WS-05 Project-less mode supported — app launches and runs without any folder open.
- WS-06 New panes inherit project cwd; project-less panes inherit `$HOME`.
- WS-07 Switch project via palette ("Open recent", "Close project").

**Success Criteria (proposed):**
1. Open folder picker → select folder → panes inherit cwd.
2. Quit + reopen most-recent project from start screen.
3. Launch without a project → fully functional empty-pane workflow.
4. `.voss/` doesn't appear until a setting changes or layout is saved.

**Cross-cutting constraints:**
- CONCEPT §10 Q5 (project-less) and Q7 (`.voss/` timing) must close before SPEC.

---

### Phase A6: voss-app Session Persist

**Goal:** Pane tree, per-pane cwd + shell choice, and truncated scrollback restore across app restart. Live processes are NOT auto-relaunched in L1.

**Requirements (locked at SPEC):** PER-01..0N
- PER-01 On quit: pane tree (geometry + cwds + shells), focused pane, active layout preset, last 2k scrollback lines per pane → `.voss/session.json`.
- PER-02 On launch with project: read `session.json`, reconstruct panes with stored geometry. Each pane shows `[restored]` banner with scrollback truncated to 2k lines; user re-runs commands manually.
- PER-03 Project-less mode persists at `~/.config/voss-app/global-session.json`.
- PER-04 Schema versioned `{"version": 1}` with forward-migration policy (unknown future versions decline gracefully).
- PER-05 Storage format: JSON in L1 (SQLite reserved for L2 cells.sqlite).
- PER-06 Concurrent-app safety: portalocker or equivalent flock on session file write.

**Success Criteria (proposed):**
1. Quit app with 4 panes open across 2 splits → reopen → exact layout restored.
2. Project-less session restores last-used pane on launch.
3. Corrupted `session.json` falls back to default layout with non-fatal toast.

**Cross-cutting constraints:**
- Scrollback cap (2k lines) configurable in settings but locked default.
- No live-process restart in L1 — that's an explicit non-feature.

---

### Phase A7: voss-app Command Palette + Keymap

**Goal:** Command palette (`⌘P` quick-open, `⌘⇧P` all commands), VSCode-default keymap profile with tmux-friendly additions, user custom-map override via `.voss/keymap.json`.

**Requirements (locked at SPEC):** CMD-01..0N
- CMD-01 `⌘P` opens fuzzy folder picker (file-open deferred to L4 editor pane). v0 stretch: jump-to-layout by name.
- CMD-02 `⌘⇧P` opens command palette with all commands, fuzzy-matched.
- CMD-03 v0 command catalog covers: Window · Pane · Layout · Project · Settings · Help.
- CMD-04 Recent commands sticky in fuzzy ranking.
- CMD-05 Keymap profiles: VSCode-default ships; tmux-friendly adds `⌘B` prefix mode; user override via `.voss/keymap.json`.
- CMD-06 Keymap JSON validated on load; invalid entries surfaced as toast.
- CMD-07 Palette renders Variant B aesthetic — mono, dim/bright, glyph affordances for command category.

**Success Criteria (proposed):**
1. Every v0 command (per FEATURES §L1.5.3 catalog) findable via palette.
2. Customize one keybinding via `.voss/keymap.json` and reload → new binding active.
3. Switch to tmux profile → `⌘B`-then-`%` splits vertically.

**Cross-cutting constraints:**
- Command implementation = web component (not Tauri-native menus) — decision locked at SPEC.
- Native OS menus (mac menubar, win/linux menu) wrap the same command registry.

---

### Phase A8: voss-app Workspaces, UX Polish, & Theming

**Goal:** Workspace tab bar (Warp-style multi-project tabs), VSCode theme import engine with bundled popular themes, appearance polish (vibrancy, animations, font management), accessibility foundations, setting profiles, and platform-native window chrome. Turns voss-app from a functional terminal into an app people *want* to use daily.

**Requirements (locked at SPEC):** UXP-01..0N

*Workspaces — UXP-01..08:*
- UXP-01 Workspace tab bar at top of window (below titlebar, above pane area). Each tab = one workspace. Warp-style: named, color-coded, `+` button to add.
- UXP-02 Each workspace owns an isolated pane tree, cwd, layout preset, session state. Switching workspaces swaps the entire pane area.
- UXP-03 `+` button opens a workspace picker: select directory, shell, layout preset. (L2 will add agent selection.)
- UXP-04 Workspace accent color: user picks per-workspace, or auto-derived from project name hash.
- UXP-05 Switch hotkeys: `⌃1`–`⌃9` for workspace tabs (`⌘1`–`⌘9` stays pane focus). `⌃Tab` / `⌃⇧Tab` cycle workspaces.
- UXP-06 Workspace persistence: all open workspaces restore on app relaunch (extends A6 session persist to multi-workspace).
- UXP-07 Drag-to-reorder workspace tabs. Double-click tab to rename. Context menu: rename, color, close.
- UXP-08 Close workspace: confirm if any pane has a running process. Last workspace can't be closed (app stays open with empty workspace).

*Theme Engine — UXP-09..14:*
- UXP-09 VSCode theme import: parse `.json` theme files from popular VSCode themes and map `tokenColors` + `colors` → voss-app CSS variable token system (`--bg-0..3`, `--fg-0..3`, `--border`, `--focus`, accent colors).
- UXP-10 Ship 8 bundled themes: One Dark Pro, Dracula, Catppuccin Mocha, Gruvbox Dark, Tokyo Night, Nord, Monokai Pro, Solarized Dark. Plus Variant B (default).
- UXP-11 Light themes: Catppuccin Latte, Solarized Light, GitHub Light. (Variant B light variant deferred — can be added later via the same engine.)
- UXP-12 Live theme preview: hover theme in settings → panes + chrome preview instantly. Click to apply. No restart.
- UXP-13 Custom theme authoring via `.voss/themes/<name>.json` with documented JSON schema.
- UXP-14 Theme hot-swap: switching theme updates all open workspaces + panes in ≤100ms.

*Appearance & Polish — UXP-15..20:*
- UXP-15 Window opacity/vibrancy: macOS `NSVisualEffectView` behind webview, Windows acrylic/mica (platform-gated). Configurable opacity slider (0.5–1.0).
- UXP-16 Font picker with live preview: family, size, line-height, letter-spacing, ligature toggle. Bundled fallback: JetBrains Mono.
- UXP-17 Cursor customization: block/bar/underline shape, blink rate (off/slow/fast), cursor color follows theme or override.
- UXP-18 Smooth transitions: pane split/close animations (150ms ease), focus transition (opacity shift), layout preset switch (200ms reflow). All respect `prefers-reduced-motion`.
- UXP-19 Pane chrome refinement: hover states on resize handles, subtle drag affordance, consistent focus indicator across themes.
- UXP-20 Window corner radius + shadow consistency across platforms.

*Accessibility — UXP-21..24:*
- UXP-21 High-contrast mode: overrides theme with WCAG AAA contrast ratios. Toggleable in settings.
- UXP-22 `prefers-reduced-motion` respected globally: disables all transitions/animations when OS preference set.
- UXP-23 Minimum font size floor (10px) enforced regardless of settings.
- UXP-24 Bell behavior: visual flash / audible / none / badge-only. Configurable per-workspace.

*Profiles — UXP-25..27:*
- UXP-25 Named setting profiles: user creates profiles (e.g., "Work", "Personal", "Presentation"). Profile = snapshot of appearance + terminal + layout settings.
- UXP-26 Quick-switch via command palette ("Switch Profile → Work") or workspace tab context menu.
- UXP-27 Profiles stored at `~/.config/voss-app/profiles/<name>.json`. Workspace can pin a profile.

*Platform-Native Feel — UXP-28..30:*
- UXP-28 macOS: proper traffic-light positioning with vibrancy, native menu bar wraps command registry, system appearance follows light/dark.
- UXP-29 Windows: proper title bar with snap layout support (Win+arrow), acrylic backdrop, taskbar integration.
- UXP-30 Linux: desktop entry + `.desktop` file, tray icon, proper window manager hints (WM_CLASS).

**Success Criteria (proposed):**
1. Open 3 workspace tabs (Wineberry, Voss, Claude Code). Each has independent pane trees. `⌃1`/`⌃2`/`⌃3` switches instantly.
2. Import a VSCode theme (Dracula) → all panes + chrome update live without restart.
3. Quit app with 3 workspaces → reopen → all 3 restore with correct layouts + cwds.
4. Switch to high-contrast mode → all text meets WCAG AAA.
5. Create "Presentation" profile with large font + light theme → quick-switch from palette.
6. macOS vibrancy visible through pane backgrounds when opacity < 1.0.

**Cross-cutting constraints:**
- Workspace tabs live between titlebar and pane area — titlebar (A1) rendered above, status bar (A10) below.
- A5 (Project Open) scopes down: "open folder" becomes "open folder in current workspace" or "new workspace for folder." Folder-picker + git-read mechanics stay in A5; workspace *container* is A8.
- A6 (Session Persist) extends: `session.json` becomes `session.json` per workspace, plus a top-level `workspaces.json` index.
- Theme engine supersedes the narrow Variant B token override from old A8 (now A9). A9 settings UI references themes delivered here.

---

### Phase A9: voss-app Settings + Theme

**Goal:** Two-pane settings UI (search + categories left, form right) backed by JSON files. Variant B token system applied as theme. Font, shell, telemetry-consent UX all live here.

**Requirements (locked at SPEC):** CFG-01..0N
- CFG-01 User settings: `~/.config/voss-app/settings.json`. Workspace settings: `.voss/settings.json`. Workspace wins.
- CFG-02 Two-pane UI: search + nav left (Appearance · Terminal · Layout · Keybindings · Project · Updates · Telemetry), form right.
- CFG-03 Each form value has "Edit as JSON" link → opens raw settings file in OS default editor.
- CFG-04 Theme tokens delivered as CSS variables (sketch 001 Variant B canonical set). Token override via `.voss/theme.css` or settings. **Theme engine from A8 provides the full theme catalog; A9 provides the settings surface to select/configure them.**
- CFG-05 Font (family + size + line-height), cursor shape, scrollback size, default shell all configurable.
- CFG-06 Telemetry section: all toggles OFF default. Crash reports + usage analytics opt-in, both clearly labelled.
- CFG-07 Settings hot-reload: change → next pane open uses new defaults; live panes ask before retroactive changes.

**Success Criteria (proposed):**
1. Change theme tokens via UI → all panes + chrome update without restart.
2. Change default shell via UI → next new pane uses it.
3. Telemetry toggles persist; off-state prevents any network call.

**Cross-cutting constraints:**
- CONCEPT §10 Q9 (telemetry policy) must close before SPEC.
- Settings schema validated by JSONSchema or similar (decision at SPEC).
- A9 settings UI surfaces themes, profiles, and accessibility controls delivered by A8.

**Plans (4 plans, 3 waves):**

**Wave 1** *(parallel, file-disjoint)*
- [x] A9-01 — Rust settings.rs: typed structs, load/save/merge, Tauri commands
- [x] A9-02 — Frontend form controls: Toggle, Dropdown, Slider, NumberStepper, RadioGroup, WorkspaceBadge, SettingRow

**Wave 2** *(depends on Wave 1)*
- [x] A9-03 — SettingsPanel overlay + sidebar + search + 7 category sections (wires controls to Tauri backend)

**Wave 3** *(depends on Wave 2)*
- [x] A9-04 — App.tsx integration: ⌘, shortcut, overlay mount, hot-reload dispatch, CFG-01..07 acceptance

Cross-cutting constraints: All 16 CONTEXT decisions (D-01..D-16) covered. Plan-checker 12/12 PASS.

---

### Phase A10: voss-app Status Bar

**Goal:** Bottom status bar: project · branch · active pane info · pane count · cost-meter stub · notifications bell. Click any cluster for popover detail. **With A8 workspaces, status bar is per-workspace** — shows info for the active workspace's focused pane.

**Requirements (locked at SPEC):** BAR-01..0N
- BAR-01 Left cluster: project name (click → recents), git branch (read-only display). **Workspace-aware: shows active workspace's project.**
- BAR-02 Center cluster: focused pane cwd · shell · pid.
- BAR-03 Right cluster: pane count `▢ N` (for active workspace), notifications bell with badge, settings cog. **No cost meter slot in L1** (Q6 decision — added in L2 with cell promotion).
- BAR-04 Click clusters → popovers with full detail (focus history, branch switcher placeholder, notification log).
- BAR-05 Status bar height fixed (22px Variant B), single dense line, mono font.
- BAR-06 Updates on every focus change + every git ref change (file watcher).
- BAR-07 Notifications bell shows last 100 events, clearable.
- BAR-08 Project-less mode: left cluster shows "no project · ⌘O to open" instead of name/branch.

**Success Criteria (proposed):**
1. Branch updates within 500ms of `git checkout` in any pane.
2. Pane count updates instantly on split/close.
3. Project-less status bar renders without branch/project clusters.
4. Notification log persists across restart (last 50).
5. Switching workspace tabs → status bar updates to reflect new workspace's state.

**Cross-cutting constraints:**
- Q6 closed: no cost meter in L1. L2 status bar work will add the slot (planned minor reflow accepted).
- Status bar scoped to active workspace (A8). Pane count, branch, cwd all reflect active workspace only.

**Plans (4 plans, 3 waves):**

**Wave 1** *(parallel, file-disjoint)*
- [ ] A10-01 — Rust backend: git.rs HEAD helpers + lib.rs watcher/notifications commands
- [ ] A10-02 — Frontend stores: notificationStore.ts + gitWatcher.ts + Popover.tsx

**Wave 2** *(depends on Wave 1)*
- [ ] A10-03 — StatusBar component tree: 3 clusters + 3 popover content panels

**Wave 3** *(depends on Wave 2)*
- [ ] A10-04 — App.tsx integration: GridController extension + signal wiring + BAR-01..08 acceptance + human verify

---

### Phase A11: voss-app Onboarding + Release Pipeline (v0 SHIP GATE)

**Goal:** First-run wizard, empty-state UI, soak-test hardening, AND the entire release pipeline (signing + 3 distribution channels + auto-update + version-sync). This is the final gate — the app does not release until A1–A10 are built and stable. All distribution work deferred from A1 lands here.

**Requirements (locked at SPEC):**

*Onboarding + polish — OBD-01..0N:*
- OBD-01 First-run wizard: welcome → pick workspace name → pick theme → pick shell → done. No API keys requested (L1 has no Voss).
- OBD-02 Empty-state UI for project-less new window: prompt "Open folder" or "Start without a project".
- OBD-03 Empty pane area shows keyboard hint `⌘\` split / `⌘O` open project.
- OBD-04 Keybind cheatsheet modal via Help menu, scrollable, categorized.
- OBD-05 In-app docs link to website docs; changelog modal.
- OBD-06 Crash reporter pipeline (off by default; opt-in CFG-06): captures stderr + last 500 log lines + system info on panic, queues for upload.
- OBD-07 24-hour soak test: 8 panes across 3 workspaces, mixed alt-screen + scrolling output, no PTY leaks, no memory growth > 100MB.
- OBD-08 Bug-report flow: Help → "Report Issue" opens prefilled GitHub issue with app version + platform.

*Release pipeline — REL-01..0N (deferred from A1 per 2026-05-16 decision):*
- REL-01 CI matrix builds on tag: mac-13 (arm64 + x64), ubuntu-22 (x64 + arm64), windows-2022 (x64).
- REL-02 Code-signing: mac Developer ID + notarization, win Authenticode. Certs procured (procurement is a blocking sub-task — start early).
- REL-03 Direct-download channel: signed DMG / AppImage / MSI on GitHub Releases.
- REL-04 Tauri auto-updater wired against GitHub Releases for the direct channel.
- REL-05 Homebrew cask channel: `brew install --cask voss-ade`, auto-bumped on release via separate tap repo.
- REL-06 npm channel: `@vosslang/cli voss app` subcommand launches the GUI; wrapper downloads/bundles the platform binary on first invoke; version-pinned against the M6 npm wrapper.
- REL-07 Single GitHub release tag fans out to all three channels, version-synced; channel-specific release notes generated.
- REL-08 All artifacts + store metadata use **Voss ADE** ship name (Q1).

**Success Criteria (proposed):** **THE v0 SHIP GATE** (mirrors FEATURES §L1 acceptance checklist):
1. Install on mac/linux/win from a **signed** artifact (direct channel).
2. `brew install --cask voss-ade` works on mac.
3. `npm i -g @vosslang/cli && voss app` launches the GUI.
4. Auto-updater pulls a newer release and prompts user.
5. All three channels resolve to the same version from one release tag.
6. Open app → empty state works.
7. Open folder → status bar populates.
8. 2×2 grid via 3 splits, all independent shells.
9. `⌘1-4` focus + click focus works.
10. Switch layout preset → reorder, no kill.
11. Resize via mouse + keyboard.
12. Save + reload layout via palette.
13. `vim`/`htop`/`tmux` work inside a pane.
14. Copy/paste across panes.
15. Quit + reopen restores layout + all workspaces.
16. Settings persist (theme + font + shell + keybind).
17. 3 workspace tabs with independent pane trees — switch instantly.
18. 24hr soak with 8 panes across 3 workspaces — no crashes, no PTY leaks.
19. Crash reporter activates if app panics (opt-in pipeline tested).
20. Bug-report flow opens prefilled GH issue.

**Cross-cutting constraints:**
- A11 is the integration + release phase — assumes A1–A10 complete and stable.
- Cert procurement (REL-02) is the long-pole — kick off procurement during A1, even though the wiring lands in A11.
- Failing any acceptance criterion = v0 doesn't ship.

---

### Phase A12: voss-app ADE Visual Redesign

**Goal:** Transform voss-app from "terminal multiplexer" to SOTA agent development environment. Left sidebar with agent list, quick launch, file tree, and history. Warm site palette (#0b0a09 bg, #ff5b1f burnt orange accent, Poppins/Inter/JetBrains Mono). Pane chrome with role-color accent bars. Branded titlebar with Voss logo. Terminals remain the hero — this is for vibe coders.

**Source:** `.planning/ADE-REDESIGN.md` (sketch 002 Variant A winner). Site design tokens from `site/app/globals.css`.

**Requirements (locked at SPEC):** ADE-01..08

- ADE-01 Theme migration: replace cool blue-gray token palette (variant-b.css) with warm site-aligned palette. All CSS vars, no raw hex. Font loading for Poppins.
- ADE-02 AgentSidebar component: collapsible left panel (280px), 2px orange left accent, sections for Agents/Quick Launch/Files/History. Animates open/close (250ms).
- ADE-03 Layout integration: sidebar sits outside grid tree in flex row. Grid resizes via ResizeObserver. `⌘⇧B` toggle. Sidebar state persists in localStorage.
- ADE-04 Agent launch flow: Quick Launch buttons (Claude/Codex/Gemini) spawn agents in new panes. Agent detection updates sidebar reactively.
- ADE-05 Titlebar + branding: Voss logo mark (20px SVG), Poppins display font for app name. Status bar orange agent count badge.
- ADE-06 Pane chrome warmth: 3px left accent bars in role color on agent pane headers. Focused agent pane gets orange edge + focus-soft bg. Streaming pulse animation.
- ADE-07 File tree: basic recursive directory listing from project root via Tauri FS. Expand/collapse, scroll within section.
- ADE-08 History/sessions: git log entries with relative timestamps in sidebar History section. Updates on focus.

**Depends on:** A3 (grid engine), A8 (workspaces/theming baseline)

**Plans:** 8 plans, 3 waves

Plans:
- [ ] A12-01-PLAN.md — ADE-01: Voss Ignite theme (token swap + xterm palette + Poppins bundled)
- [ ] A12-02-PLAN.md — ADE-02: AgentSidebar component (4 sections shell + budgetRegistry)
- [ ] A12-03-PLAN.md — ADE-03: Layout integration (wire sidebar into App.tsx + Cmd+Shift+B + focus sync)
- [ ] A12-04-PLAN.md — ADE-04: Agent launch modal (6 CLI presets, context-sensitive config)
- [ ] A12-05-PLAN.md — ADE-05: Titlebar branding + status bar agent badge
- [ ] A12-06-PLAN.md — ADE-06: Pane chrome warmth (accent bars, streaming pulse, focused state)
- [ ] A12-07-PLAN.md — ADE-07: File tree (read-only, Tauri list_dir command)
- [ ] A12-08-PLAN.md — ADE-08: Git log + Sessions (two sidebar sections, Tauri git_log)

| Wave | Plans | Parallel |
|------|-------|----------|
| 1 | A12-01 (theme), A12-02 (sidebar shell) | yes |
| 2 | A12-03 (layout wiring), A12-05 (titlebar/badge), A12-06 (pane chrome) | A12-05/A12-06 parallel; A12-03 sequential after W1 |
| 3 | A12-04 (launch modal), A12-07 (file tree), A12-08 (git/sessions) | yes, all after A12-03 |

**Critical path:** A12-01 → A12-03 → A12-04. A12-02 parallel with A12-01 in W1.

**Success Criteria (proposed):**
1. App renders with warm site palette — no cool blue-grays remain.
2. Sidebar shows running agents with role badges, status dots, model, cost.
3. Sidebar collapses/expands smoothly via `⌘⇧B`.
4. Quick Launch spawns an agent in a new pane.
5. Logo mark visible in titlebar.
6. Agent panes have role-colored accent bars in headers.
7. File tree shows project directory structure.
8. History shows recent git commits.
9. All existing tests pass (no regression).

**Cross-cutting constraints:**
- Terminals remain the hero element — sidebar is supplementary, not dominant.
- Grid resize must work correctly with sidebar open/closed (ResizeObserver, not manual width math).
- Agent list derives from existing `agentConfigByPaneId` — no new backend required for P1-P3.
- Design tokens reference: `.planning/ADE-REDESIGN.md` § Design Tokens Reference.

---

### Phase A13: voss-app Agent Swarm Orchestration

> **⊘ TRANSPORT SUPERSEDED by V25 (2026-06-17).** A13 chose filesystem-as-IPC because, at the time, no daemon mediated agents. Voss now has the harness server + sidecar + SSE bus, so V25 re-bases swarm coordination on server+SSE. **A13-01 (shipped) file schema is retained as V25's git-diffable audit layer; A13-02..06 (file-bus decompose/spawn/result-watch/sidebar/persist) are superseded** by V25's `SwarmStore` + spawn-gating + PermissionGate ownership + memory-scoped recall. Keep this section as historical design context.

**Goal:** File-mediated multi-agent swarm where a coordinator decomposes user goals into subtasks, spawns parallel agent panes, and synthesizes results. Agents communicate via `.voss/swarm/` filesystem convention — works with any CLI agent without modification.

**Source:** `.planning/phases/A13-agent-swarm-orchestration/A13-CONTEXT.md`, `A13-SPEC.md`

**Requirements:** SWM-01..SWM-12

- SWM-01: User launches swarm from sidebar with natural language goal
- SWM-02: Coordinator decomposes goal into 2-6 subtasks automatically
- SWM-03: Each subtask spawns a dedicated agent pane with task context
- SWM-04: Agents read task assignments from `.voss/swarm/tasks/` files
- SWM-05: Agents write results to `.voss/swarm/results/` files
- SWM-06: Host detects completion via result file creation + PTY idle
- SWM-07: Coordinator synthesizes all results into summary
- SWM-08: Sidebar shows per-agent swarm status (pending/running/complete)
- SWM-09: User can stop individual agents or entire swarm
- SWM-10: Swarm layout preset auto-applied on launch
- SWM-11: Swarm state persisted in `.voss/swarm/manifest.json`
- SWM-12: Swarm resumable after app restart

**Depends on:** A12 (ADE sidebar + agent detection + launch modal), A4 (layout presets)

**Plans:** 5 plans, 3 waves

Plans:
- [x] A13-01-PLAN.md — Swarm type contracts + Rust file I/O commands + CSP update (SWM-04, SWM-05, SWM-06, SWM-11)
- [ ] A13-02-PLAN.md — Coordinator LLM decomposition + result parser + npm deps (SWM-02, SWM-07)
- [ ] A13-03-PLAN.md — SwarmController lifecycle + swarmRegistry signal store (SWM-03..06, SWM-10..12)
- [ ] A13-04-PLAN.md — Sidebar swarm UI + launch modal Swarm tab (SWM-01, SWM-08, SWM-09)
- [ ] A13-05-PLAN.md — App.tsx wiring + visual verification (SWM-01, SWM-03, SWM-08..10, SWM-12)

| Wave | Plans | Parallel |
|------|-------|----------|
| 1 | A13-01 (types + Rust commands), A13-02 (coordinator + parser) | yes |
| 2 | A13-03 (SwarmController), A13-04 (sidebar + modal UI) | yes, after W1 |
| 3 | A13-05 (App.tsx wiring + visual verify) | after W2 |

**Critical path:** A13-01 -> A13-03 -> A13-05

**Success Criteria:**
1. User types a goal, coordinator splits into 2-6 subtasks
2. Each subtask spawns a pane with the right agent CLI + task file
3. Agents read `.voss/swarm/tasks/` and write `.voss/swarm/results/`
4. Sidebar shows per-agent swarm status (pending/running/complete)
5. Coordinator synthesizes results when all agents finish
6. User can stop individual agents or full swarm
7. Swarm state survives app restart

---

## O-prefixed phases: Caged Autonomous Eng Team (ADE Orchestration)

**Track:** Multi-agent orchestration layer on the Python harness. Full design, decision log (21 decisions), `.voss` strawman, and residual-risk register in **`.planning/ORCHESTRATION-PLAN.md`**.

**Thesis:** Every autonomous agent-team product today is an unbounded blackbox. Voss already ships per-call budgets, confidence gates, write-scope locks, and replayable audit. The ADE orchestrator is the showcase: **a fully autonomous AI engineering team inside a *provable* cage — hard budget, global scope ceiling, an independent judge gating every state transition, fully replayable.** "Audit the cage," not "trust the swarm."

**Not a pivot.** Showcase skin on the harness, not a parallel build. Single-agent harness must be boring-solid first. The orchestrator + board + rituals are expressed in `.voss`; the harness owns execution. Builds on M13 (raw `spawn`/`gather`) — O-phases add the cage.

**Roles:** Human (idea + final sign-off) · **Engineering Manager** (LLM lead: idea→tickets/AC/DoD, runs board, dispatches specialists) · **Engineer roster** (backend/frontend/ui/ai, per-role scope+tools) · **Reviewer-A** (re-derives bar + authors tests/eval from the *original idea*) · **Reviewer-B** (independent tiered judge: slop/errors/correctness, EM-narrative-blind).

**Cross-O cage invariants (the product is these or it is theater):**
- Budget = security boundary: hard, pre-committed, non-extendable by EM; fans out parent→card.
- Scope: per-card `edit_scope` + global ceiling; union of card scopes ≤ ceiling.
- Confidence is independent (Reviewer-B); threshold `p` is per-card-risk, human-declared, EM-immutable.
- Audit bar = the **original human idea** (Reviewer-A re-derives), never EM-authored AC.
- Engineers cannot author the verification that gates them (Reviewer-A owns tests/eval).
- Liveness guaranteed: reserved non-spendable drain budget + timeout→Blocked.
- The session-tree recorder **is** the human review product, not telemetry.

**Open residual risks (carried, none fatal — full register in ORCHESTRATION-PLAN.md §7):**
- Standup→`semantic.memory` poisoning (Leak 6) — **unaddressed**, O6 mitigation candidate.
- Reviewer-A misread propagates — requires a written invariant: Reviewer-B may fail idea-divergent A-verification.
- Human sign-off is overloaded (correctness + misroute + killed-card review) — O6 forcing-function candidate.
- "~80% reuse" is false — real build is substantial across O1–O6; do not plan against the reuse number.

**Dependency chain:** O1 (keystone) → O2 → O3 → O4 → O5 → O6.

---

### Phase O1: Session-Tree Substrate + Budget Fan-out

**Goal:** Parent→child session tree in `recorder.py`/`session.py` so every spawned agent is a first-class recorded node with its own budget, scope, and audit. The keystone — every other O-phase renders off this.

**Scope:** Parent→card budget fan-out (`(envelope − reserve) / total WIP` floor); reserved non-spendable drain budget guaranteeing every in-flight card reaches a verdict; hard non-extendable caps (no "ask for more tokens" path); session-tree recorder schema. Reuses/extends `RunRecorder`, `SessionRecord`.

**Requirements (locked at SPEC):** SPEC-1 (harness session tree + parent linkage), SPEC-2 (per-card budget allocation + fan-out invariant), SPEC-3 (reserved drain → terminal finalize), SPEC-4 (non-extendable cap + recorded attempts), SPEC-5 (strict harness-additive blast radius) — 5 locked in `O1-SPEC.md`.

**Plans:** 2 plans, 2 waves

Plans:
- [ ] O1-01-PLAN.md — Session-tree substrate: SessionTreeNode + SessionTreeManager allocator (fan-out invariant) + D-04 guarded mutator + per-node file persistence (D-01/D-02/D-04)
- [ ] O1-02-PLAN.md — D-03 always-finalize boundary in run_subagent: finalize_node guard + reserved-drain terminal finalize + parent linkage at spawn (D-03)

**Cross-cutting:** No board, no reviewers, no EM in O1 — pure substrate. `subagents.py` gains budget/scope/recorder plumbing it lacks today.

---

### Phase O2: `.voss team{}` Spec + Specialist Roster

**Goal:** A `.voss team{}` block parser that compiles to an enriched `SubagentRegistry` + specialist roster, with `ceiling`/`p` declared above the EM and immutable to it (the cage is syntax).

**Scope:** `SubagentSpec` extended with model/mode/scope/budget/tools per role; backend/frontend/ui/ai roster; EM-immutable `ceiling`/`p` blocks; per-role permission/tool profile (AI role gets `net`). Depends O1 (specs carry budget/scope that need the tree).

**Requirements:** OTEAM-01, OTEAM-02, OTEAM-03, OTEAM-04, OTEAM-05, OTEAM-06, OTEAM-07, OTEAM-08 (derived in `O2-RESEARCH.md`; no O2-SPEC.md — requirements ratified inline at planning).

**Plans:** 3 plans

Plans:
- [ ] O2-01-PLAN.md — Grammar + AST nodes + transformer for `team{}` block; frozen value-object shells (OTEAM-01, OTEAM-04, OTEAM-08)
- [ ] O2-02-PLAN.md — `SubagentSpec` extension + `compile_team` + scope-containment validator (OTEAM-02, OTEAM-03, OTEAM-05, OTEAM-06)
- [ ] O2-03-PLAN.md — Per-role `gate_for_role` + tool filter + per-gate `allow_net` override; AI-vs-engineer net cage (OTEAM-03, OTEAM-07)


---

### Phase O3: Board State Machine + Gated Transitions

**Goal:** The Kanban board as the orchestrator state machine — columns, per-column WIP, gated transitions.

**Scope:** `Backlog→Planned→InProgress→InReview→Blocked→Done`; per-column WIP (backpressures reviewer cost); confidence gate only on artifact transitions; →Done double gate (code: tests; AI: eval); critic loop ceiling(≈3)+budget→Blocked; column/card timeout→Blocked liveness. Depends O1, O2.

**Requirements:** OBRD-01..OBRD-09 — locked in `O3-SPEC.md` (14 acceptance checkboxes).

**Plans:** 4 plans

Plans:
- [ ] O3-01-PLAN.md — Substrate edits (SessionTreeNode fields, get_node, EXIT_REASONS+"timeout"); board package scaffold (verdict.py zero-deps, errors.py) — addresses OBRD-01 (substrate), OBRD-07
- [ ] O3-02-PLAN.md — State machine: Card frozen value-object, Board.from_team_config, Board.move with WIP enforcement, BoardSpec adapter, transition-delta emission — addresses OBRD-01, OBRD-02, OBRD-03, OBRD-06 (single-source threshold)
- [ ] O3-03-PLAN.md — Gate-predicate registry (8 predicates / 7 stable names), Board.dry_run_gate, artifact-only confidence, DeterministicReviewerStub — addresses OBRD-04, OBRD-05, OBRD-06 (acceptance), OBRD-07 (stub end-to-end)
- [ ] O3-04-PLAN.md — Tick driver (Clock + FakeClock + _tick_loop), Board.start/stop, critic loop (retry_notes + ceiling), finalize_node integration, 100-card stress — addresses OBRD-08, OBRD-09, OBRD-01 (full audit invariant)

---

### Phase O4: Reviewer A/B Split

> ⊘ **SUPERSEDED by V6** (2026-06-06). Shipped via V6-01..05. O4 artifacts (`voss/harness/board/reviewer_a.py`, `reviewer_b.py`, `verdict.py`) are RETAINED as the production reviewer surface — V6 extended them additively (7-field verdict, two-source Done gate, sidecar, `voss review`). The O4 plan list below is kept for lineage; do not re-execute.

**Goal:** Independent bar/verification authoring (A) cleanly split from independent judgment (B), restoring two independent sources at →Done.

**Scope:** Reviewer-A re-derives the bar from the original idea + authors verification (deterministic tests for code; eval harness for AI via `voss/eval/` reuse). Reviewer-B: independent session/model, no shared memory with A or EM, tiered (fast intermediate / strong at →Done), checks slop/errors/correctness, sees `[artifact, acceptance, repo, original_idea]`, **explicit authority to fail a card whose A-verification diverges from the idea** (residual-2 invariant). Depends O2, O3.

**Requirements:** ORVW-01 (A bar from idea), ORVW-02 (A test authoring for code), ORVW-03 (A judge_run for AI), ORVW-04 (B message isolation), ORVW-05 (B fast tier), ORVW-06 (B strong tier), ORVW-07 (Residual-2 block), ORVW-08 (fresh memory per A review), ORVW-09 (Protocol conformance), ORVW-10 (board lifecycle integration).

**Plans:** 4 plans

Plans:
- [ ] O4-01-PLAN.md — O3 preflight gate + RED test scaffolds for all 10 ORVW requirements (ORVW-01..10)
- [ ] O4-02-PLAN.md — Reviewer-B: independent tiered judgment via single provider.complete() call (ORVW-04..07, ORVW-09)
- [ ] O4-03-PLAN.md — Reviewer-A: bar authoring via run_turn + judge_run AI-card path (ORVW-01..03, ORVW-08, ORVW-09)
- [ ] O4-04-PLAN.md — Integration test + final acceptance gate (ORVW-09, ORVW-10)

---

### Phase O5: Engineering Manager Loop

> ⊘ **SUPERSEDED by V7** (2026-06-06). Shipped via V7-01..03. O5 artifacts (`voss/harness/em/loop.py`, `handle.py`, `tickets.py`, `schema.py`, `stub.py`) are RETAINED as reference — V7 composed them unchanged behind `voss team run` (no reimplementation of `em_loop`, the cage, the board, or the reviewers; zero frozen-schema drift). The O5 plan list below is kept for lineage; do not re-execute.

**Goal:** The EM autonomous lead loop — idea in, board run to Done, human sign-off only.

**Scope:** Full-authority autonomous loop; idea→tickets/AC/DoD (worker scaffolding, not the audit bar); specialist dispatch from roster + `routing_rationale` per card; kill/re-scope with preserved lineage; board mutation bounded by the cage (cannot rewrite `ceiling`/`p`, cannot invent agents). Depends O1–O4.

**Requirements:** OEM-01..OEM-10 (locked direct from CONTEXT + RESEARCH; no SPEC).

**Plans:** 6 plans
- [ ] O5-00-PLAN.md — Substrate gate (O1/O2 live probes + O3/O4 paper audit; no code)
- [ ] O5-01-PLAN.md — Data model: Ticket/KillRecord/RescopeRecord/RoutingRationale/RunFinal + EXIT_REASONS "killed" additive (OEM-01, OEM-07, OEM-10)
- [ ] O5-02-PLAN.md — EMBoardHandle cage facade + BoardProtocol mocks for O3 (OEM-02, OEM-06, OEM-07, OEM-08)
- [ ] O5-03-PLAN.md — EM LLM wrapper + EMPlanResponse pydantic LENIENT schema + DeterministicEMStub (OEM-03, OEM-04)
- [ ] O5-04-PLAN.md — em_loop driver: idea → plan → dispatch → tick → terminate (OEM-05, OEM-06)
- [ ] O5-05-PLAN.md — Integration tests + cross-phase coordination doc + VALIDATION matrix (OEM-08, OEM-09, OEM-10)

---

### Phase O6: Audit Product + Calibration + Liveness Hardening

**Goal:** The human review product + the monitoring that keeps the cage honest.

**Scope:** Session-tree as primary review surface; killed/re-scoped cards + routing rationale foregrounded first-class; reviewer calibration telemetry (B-verdict vs. A-verification, now independent) + sampled human slop-rejection spot-audit; reserve/timeout liveness wiring surfaced; **sign-off forcing function** (mandatory killed-card + misroute diff before approve is available); Leak-6 (`semantic.memory` poisoning) mitigation candidate. Depends O5.

**Requirements:** OAUD-01..08 — derived in `O6-RESEARCH.md` / `O6-VALIDATION.md` because `O6-SPEC.md` is not present; reconcile if a formal SPEC is later authored.

**Cross-cutting:** O6 closes (or explicitly defers) the residual-risk register from `ORCHESTRATION-PLAN.md §7`. Leak 6 may remain a documented accepted gap if mitigation proves out-of-scope.

---

## V-track phase detail (Agent Engineering Organization Layer)

> Design source: `docs/ORCHESTRATION_LAYERS.md` (PRD §P0–P12). The V-track **supersedes O1–O6 and absorbs M13** (see Phase Order). Requirement IDs below are the roadmap-namespaced `V*` form; each `V{n}-SPEC.md` locks them and maps PRD-ID → roadmap-ID. Build order: V1→V3→V4(keystone)→V5→V6→V7→V9, then V2/V10/V11/V12. Keep `voss do`/`voss chat` working every phase (PRD §9 top risk).

### Phase V0: Reframe & Consolidate

**Goal:** Reframe the canonical + planning identity docs around "Voss is an **agent engineering organization layer**, with the `.voss` language + harness as its substrate" — promoting `.planning/docs/ORCHESTRATION_LAYERS.md` to the canonical PRD + architecture doc, naming the six primitives, mapping every roadmap track to them, and adding a glossary, so a contributor can trace identity → primitives → phases from one source. Docs-only.

**Scope:** Add a canonical-PRD status declaration + a net-new phase→primitive map (M/T/A/O/F/V) + a net-new glossary to `.planning/docs/ORCHESTRATION_LAYERS.md`, and normalize its existing six-primitive table in place; prepend a `⊘ SUPERSEDED` banner to root `PRD.md` linking to the canonical doc; reframe the `.planning/PROJECT.md` lead to org-layer-atop-substrate. No new architecture doc — `.planning/docs/ORCHESTRATION_LAYERS.md` IS the architecture doc. README/npm `@vosslang` copy untouched (deferred). Docs-only — no runtime/CLI/grammar change. (Supersedes the earlier stale scope prose that referenced `docs/agent-org-architecture.md` and a 15-minute metric — governed by V0-SPEC.md acceptance checks.)

**Requirements:** VRFM-01, VRFM-02, VRFM-03, VRFM-04, VRFM-05 (PRD P0-01..05).

**Cross-cutting:** Pure documentation/identity phase. Acceptance is grep-checkable doc-presence; scope guard requires `README.md` byte-unchanged and zero non-`.md` files in the phase diff. Source: `.planning/docs/ORCHESTRATION_LAYERS.md` §"Phase 0".

**Plans:** 2 plans (1 wave)

Plans:
- [ ] V0-01-PLAN.md — Canonical PRD: status declaration + six-primitive normalize + phase→primitive map + glossary + §1 thesis confirm
- [ ] V0-02-PLAN.md — Satellite docs: PRD.md ⊘ SUPERSEDED banner + PROJECT.md org-layer lead reframe + scope guard

---
### Phase V1: Capability Surface Hardening

**Goal:** Make the agent toolbelt a clean, composable, typed, permissioned, auditable capability registry — extending `ToolEntry`, not replacing it.

**Scope:** Normalized `Capability` schema (name, description, input/output schema, mutability, network usage, scope requirements, audit behavior); `voss capabilities list` + `voss capabilities inspect <name>`; capability groups (`fs git test shell net code memory review mcp`); unify MCP tools into the same registry; capability invocations emit recorder events; mutating capabilities require gate approval unless role/mode allows; stub-testable with deterministic fixtures. Hardens M10–M15 tool surfaces.

**Requirements (lock at SPEC):** VCAP-01..10 (PRD CAP-01..10).

**Cross-cutting:** Extends existing `tools.py`/`permissions.py`/`sandbox.py`; preserve current call sites; metadata added incrementally; JSON-first output.

**Plans:** 4 plans, 3 waves

Plans:
- [ ] V1-01-PLAN.md — Extend ToolEntry schema + hand-tag native registry (CAP-01/02/03/06)
- [ ] V1-02-PLAN.md — `voss capabilities list` + `inspect` CLI, JSON-first (CAP-04/05)
- [ ] V1-03-PLAN.md — Unify MCP into registry, default-deny gate-on-mutation, net-bucket close (CAP-07/09)
- [ ] V1-04-PLAN.md — Recorder capability-invocation audit events + CAP-10 stub fixtures (CAP-08/10)

---

### Phase V2: Principles Layer

**Goal:** Make engineering principles first-class and inject them into every agent context without hardcoding workflow steps.

**Scope:** `.voss/principles.yml` + optional `principles { ... }` syntax → immutable `PrinciplesConfig`; injected into EM/worker/reviewer/tester contexts; ship default principles (diff/evidence/tests/scope/review/reversibility); project-local override additively unless disabled; `voss principles show`; audit records active principles. No control flow may depend on individual principle strings.

**Requirements (lock at SPEC):** VPRIN-01..08 (PRD PRIN-01..08).

**Cross-cutting:** Genuinely new surface. Changing principles changes subsequent runs, never historical audits.

**Plans:** 3 plans (2 waves) — covers VPRIN-01/03/04/05/06/07. VPRIN-02 (grammar block) → V10; VPRIN-08 (audit recording) → V9.

Plans:
- [ ] V2-01-PLAN.md — principles.py: frozen PrinciplesConfig + .voss/principles.yml loader + six defaults + additive/disable merge (Wave 1)
- [ ] V2-02-PLAN.md — inject distinct `## Principles` block into _compose_system_blocks; ~1k cap + principles_overflow event (Wave 2)
- [ ] V2-03-PLAN.md — `voss principles show` (+--json); no-branching guard test + RunRecord/SessionRecord/BudgetScope schema-freeze assertion (Wave 2)

---

### Phase V3: Team Spec + Role Cage (supersedes O2)

**Goal:** Make `.voss team{}` the declarative source of truth for role roster, budget, scope, tools, and model tiering — the cage as syntax.

**Scope:** Finalize `team{}` grammar/AST → frozen `TeamConfig` + `SubagentRegistry`; `SubagentSpec` carries role id/prompt/model/mode/scope/budget/tools/net; EM cannot invent agents outside the registry; role scope + budget compile-time contained in global ceiling; role tools filtered through the capability registry (V1); explicit per-role model tiering; default roster (`architect backend frontend tester reviewer skeptic docs`); `voss team check` validates syntax/scope/tools/model/budget. Supersedes O2; reuses `TeamDecl`/`compile_team`/`gate_for_role`/`filter_toolset_for_role`.

**Requirements (lock at SPEC):** VTEAM-01..10 (PRD TEAM-01..10).

**Status:** Plans ready to execute (3 plans, 2 waves; build delta VTEAM-07/08/09/10, regression VTEAM-04/05/06; O2 superseded).

**Plans:**
- [ ] V3-01-PLAN.md — Seven-role roster + tier-based per-role defaults [VTEAM-09] and config-backed model-tier resolution in _parse_model_value [VTEAM-08].
- [ ] V3-02-PLAN.md — `voss team check [path]` CLI wrapping compile_team with roster/ceiling summary + exit codes [VTEAM-10].
- [ ] V3-03-PLAN.md — V1 capability-registry binding seam [VTEAM-07] + back-compat & shipped-surface regression (legacy roles, scope/budget containment, EM-invent guard, schema freeze) [VTEAM-04/05/06].

**Cross-cutting:** Legacy `explorer`/`worker`/`reviewer` path stays backward-compatible. Invalid scope widening / unknown capability / unknown model fail at compile time.

---

### Phase V4: Session Tree + Budget Fan-out (supersedes O1 — KEYSTONE)

**Goal:** Make every agent/subagent a first-class recorded node with its own budget, scope, status, artifacts, and audit trail — the substrate every later V-phase renders off.

**Scope:** `SessionTreeNode` schema + `SessionTreeManager`; persist each node to `.voss/sessions/<root_id>/<node_id>.json`; enforce `sum(child budgets) + reserve ≤ parent budget`; prevent upward budget mutation after allocation; record rejected raise attempts; always finalize children (error/timeout/budget/killed/blocked); attach scope+role metadata per node; `voss session tree <root_id>`; machine-readable tree export for ADE. **Budget enforcement must be pre-emptive — a node cannot make the call that breaches its envelope** (post-hoc detection = cage leaked). Supersedes O1; reuses `SessionRecord`/`RunRecorder`/`BudgetScope`/`run_subagent`/M13 allocator.

**Requirements (lock at SPEC):** VTREE-01..10 (PRD TREE-01..10).

**Plans:** 3 plans (3 waves)

Plans:
- [ ] V4-01-PLAN.md — Additive scope/role schema + EXIT_REASONS "error" + schema-lock test update (VTREE-01, VTREE-08, VTREE-05, VTREE-06)
- [ ] V4-02-PLAN.md — Keystone: pre-emptive spend guard + mutate_envelope wiring + all-reason finalize (VTREE-04, VTREE-07, VTREE-02)
- [ ] V4-03-PLAN.md — export_tree + `voss session tree` CLI + disk-reconstruct verify (VTREE-10, VTREE-09, VTREE-03)

**Cross-cutting:** No board/reviewers/EM here — pure substrate. `subagents.py` gains budget/scope/recorder plumbing it lacks today. No child overspend; no orphan sessions; tree reconstructs a full run without the chat transcript.

---

### Phase V5: Board State Machine (supersedes O3)

**Goal:** Represent orchestration as a board, not an invisible prompt loop.

**Scope:** Columns `Backlog→Planned→InProgress→InReview→Blocked→Done`; `Card` backed by a session-tree node (carries original idea/role/scope/risk/artifact target/AC/verification requirement/budget/status); per-column WIP limits (backpressure reviewer cost); transition gates (artifact required InProgress→InReview; tests/evals + independent review required InReview→Done; timeout/critic-exhaustion → Blocked); transitions persist to the session tree; `voss board`. Agents cannot mark their own work Done. Supersedes O3; depends V3, V4.

**Requirements (lock at SPEC):** VBOARD-01..10 (PRD BOARD-01..10).

**Cross-cutting:** Board state deterministic and replayable; every blocked card has a reason; renderable in CLI and ADE.

**Status:** ✅ COMPLETE — 4 plans, 3 waves (completed 2026-06-06; supersedes O3, depends V4). Full board suite 121 green; frozen schemas (RunRecord/SessionRecord/BudgetScope/SessionTreeNode) field-unchanged.

**Plans:**
- [x] V5-01-PLAN.md — Wave 0 RED scaffolds (test_card_fields_v5 / test_self_done_guard / test_board_cli) driving the real planned API (VBOARD-03/07/10)
- [x] V5-02-PLAN.md — machine.py: four additive Card fields + card_status/card_budget helpers + self-Done `no-reviewer` guard in Board.move (VBOARD-03/07)
- [x] V5-03-PLAN.md — cli_view.py read-only renderer + `voss board [root_id]` board_cmd (mtime-latest, path-traversal-safe) (VBOARD-10)
- [x] V5-04-PLAN.md — shipped-surface regression (BOARD-01/02/04/05/06/08/09) + stale-test fix + frozen-schema diff gate + O3-superseded bookkeeping (VBOARD-01/02/04/05/06/08/09)

---

### Phase V6: Reviewer A/B Split (supersedes O4)

**Goal:** Make verification independent, cheap, and continuous — bar/test authoring (A) split from judgment (B).

**Scope:** Reviewer-A derives the bar from the **original human idea** (not EM-authored AC) and authors tests/evals/checklist; worker agents cannot author their own final gate; Reviewer-B independently judges artifact/diff/tests/idea-alignment, EM-narrative-blind, tiered (fast intermediate / strong at →Done), **with authority to fail when A's verification diverges from the idea**; verdict carries confidence/pass-fail-block/evidence-refs/notes/inferred-domain; review artifacts persisted; `voss review <run_id>`. Supersedes O4; reuses `voss/eval/`. Depends V4, V5.

**Requirements (lock at SPEC):** VREV-01..10 (PRD REV-01..10).

**Cross-cutting:** A and B see different context packets; B does not depend on EM summary; failed verification blocks Done; audit can explain why something passed.

**Status:** Executed — 5 plans, 5 waves (completed 2026-06-06; supersedes O4). Full board suite green; frozen records (RunRecord/SessionRecord/BudgetScope) field-unchanged.

**Plans:**
- [x] V6-01-PLAN.md — Wave 0: pre-existing red-baseline fix + RED scaffolds (two-source gate, domain_inferred, sidecar, CLI) + 6→7-field verdict edit
- [x] V6-02-PLAN.md — verdict.domain_inferred (7th defaulted field); B populates+clamps, A defaults (VREV-06)
- [x] V6-03-PLAN.md — two-source Done gate: GateContext A/B slots + predicates, Board reviewer_a/reviewer_b + back-compat alias, B-block→Blocked seam, .review.json sidecar (VREV-03/04/07/09)
- [x] V6-04-PLAN.md — `voss review <run_id>` read-only CLI over .review.json sidecars (VREV-10)
- [x] V6-05-PLAN.md — regression verify (REV-01..05,07,08) + frozen-schema diff gate + O4-superseded bookkeeping + human-verify review output (VREV-05)

---

### Phase V7: Engineering Manager Loop (supersedes O5)

**Goal:** Implement the autonomous orchestrator as a constrained tech lead — idea in, board run to Done, human sign-off only.

**Scope:** Convert human idea → tickets/cards; assign roles from the declared roster only; emit `routing_rationale` per assignment; split work to maximize parallelism within budget + WIP; integrate completed artifacts; kill/rescope blocked cards with preserved lineage; produce a final run summary with evidence + residual risk. **EM may never mutate ceiling, confidence threshold, or role registry, nor construct permission gates outside team config.** Supersedes O5; depends V3–V6.

**Requirements (lock at SPEC):** VEM-01..10 (PRD EM-01..10).

**Cross-cutting:** EM decisions logged; misroutes auditable; killed cards inspectable; human reviews final rationale.

**Status:** ✅ COMPLETE — 3 plans, 3 waves (completed 2026-06-06; supersedes O5, depends V3–V6). V7 ships the runnable delta on the shipped O5 pieces: `voss team run "<goal>"` composes the V3 team config + V4 session tree + V5 board + the V6 Reviewer-A/B two-source slots + the O5 `em_loop`, runs autonomously to all-cards-terminal on the stub provider, persists `RunFinal` to a `.voss/sessions/<root_id>/run-final.json` sidecar, and records a human approve/reject sign-off (record-only — reject reverts nothing). O5 artifacts retained as reference; cage re-verified (no `set_ceiling`/`set_p`/`extend_budget`; undeclared-role dispatch denied; kill/rescope lineage + routing_rationale intact); frozen records (RunRecord/SessionRecord/BudgetScope) field-unchanged; no new deps.

Plans:
- [x] V7-01-PLAN.md — RED scaffold `tests/harness/test_team_run_cli.py` (10 tests, real planned surface, no fictional API / no xfail mask) (VEM-CLI/PERSIST/SIGNOFF)
- [x] V7-02-PLAN.md — `@team_group.command("run")` + `_default_team_config()` (DEFAULT_ROSTER) + `_persist_run_final()` (10-field `asdict` + `sign_off`, 0o600, root_id-derived path); pre-spawn `board.spawn_card("med")`; real V6 `reviewer_a`+`reviewer_b` injection; `asyncio.run(em_loop(...))`; `click.prompt(Choice[approve,reject])` (VEM-CLI/PERSIST/SIGNOFF)
- [x] V7-03-PLAN.md — verify EM cage + lineage regress green; frozen-schema zero-drift + no-new-deps gate; O5-superseded bookkeeping (VEM-CLI/PERSIST/SIGNOFF)

---

### Phase V8: Multi-agent Chat + Live Steering (absorbs M13)

**Goal:** Expose team-style delegation inside `voss chat` and the ADE.

**Scope:** Parent chat agent spawns child agents non-blockingly; child handles return immediately; parent can check status / gather outputs / steer between iterations; child budget allocated from parent budget; recursive child spawning preserves the budget invariant; TUI/ADE shows live child state quietly by default with explicit reveal; all child events persist into recorder/session tree once V4 is live. **Absorbs M13** (scope + its 6 ready plans fold in); reuses `multiagent.py`, `SubAgentPanel`, `run_subagent`, TUI renderer hooks.

**Requirements (lock at SPEC):** VMAG-01..10 (PRD MAG-01..10; reconcile with M13's MAG-01..08).

**Cross-cutting:** Works with stub provider; child oversell impossible; Ctrl+C remains interrupt.

---

### Phase V9: Audit Product (supersedes O6 — reuse O6 plans)

**Goal:** Make the audit trail the primary trust product.

**Scope:** `voss audit <run_id>` (read-only, deterministic) showing original idea, active principles, team config, budget, scope, board, cards, agent actions, diffs, tests, reviews, blocked items, final status; distinguishes EM claims from verified evidence; per-node budget allocation/consumption; scope violations + denied attempts; Reviewer-A and Reviewer-B separately; killed/rescoped lineage; Markdown + JSON export; residual-risk + Leak-6; sign-off forcing function; reviewer calibration telemetry. **Re-planned fresh against the V4–V7 persistence contracts — O6 plans are reference only, not reused.** AUD-09 ADE navigable session-tree render is OUT OF SCOPE → V11. Depends V7.

**Requirements (lock at SPEC):** VAUD-01..10 (PRD AUD-01..10; supersedes OAUD-01..08).

**Cross-cutting:** Audit deterministic from persisted run data; usable for PR review; can detect unsupported claims. Closes/defers the `ORCHESTRATION-PLAN.md §7` residual register (incl. Leak-6).

**Plans:** 7 plans, 6 waves (re-planned fresh 2026-06-06; O6 superseded).

- [x] V9-01-PLAN.md — Wave 0 RED scaffolds: 5 new test files + fixture/loader extension (.review.json + run-final.json) + glob-landmine fix expressed as a test
- [x] V9-02-PLAN.md — load.py (run_id param, glob-landmine filter, sidecar + run-final readers) + model.py (AuditReport + CalibrationReport dataclasses)
- [x] V9-03-PLAN.md — report.py AuditReport assembly + claims-vs-evidence tagging + residual-risk/Leak-6 synthesis + scope denials
- [x] V9-04-PLAN.md — render.py (deterministic MD/JSON/text) + __init__.py exports + voss audit CLI registered in AGENT_COMMANDS
- [x] V9-05-PLAN.md — calibration.py false-pass / slop-rejection rates + deterministic spot-audit hook
- [x] V9-06-PLAN.md — sign-off forcing function: ack gate in voss team run + .signoff-ack.json sidecar + audit approve readback
- [~] V9-07-PLAN.md — closeout: calibration wired into audit_cmd, full regression + frozen-schema diff guard GREEN, ROADMAP bookkeeping done; human verify checkpoint PENDING

---

### Phase V10: Voss Language as Coordination Spec

**Goal:** Make `.voss` the durable control language for agent engineering work.

**Scope:** Stabilize grammar for `principles`/`team`/`role`/`gate`/`board`/`review`/`memory`; compiler diagnostics for scope/budget/tools/role errors; `voss ast` inspection; `voss check` static validation; `voss compile` to runtime config objects; `voss run <file.voss>` for declared workflows; keep raw-Python runtime examples as canonical parity tests; examples for team orchestration / reviewer split / audit gates. Extends the M3 language (different concern: coordination, not general programming).

**Requirements (lock at SPEC):** VLANG-01..08 (PRD LANG-01..08; namespaced to avoid clash with M3 LANG-01..10).

**Cross-cutting:** Static errors clear enough for non-CS users; runtime behavior matches compiled config; `.voss` shorter/clearer than equivalent Python.

**Plans:** 5 plans across 5 serial waves (RED scaffold -> grammar/AST/parser -> compile-to-config -> diagnostics -> examples/e2e/guards). V10-03 and V10-04 both edit `voss/harness/team.py`, so they are sequenced (compile before diagnostics) to avoid file-ownership conflict.

Plans:
- [x] V10-01-PLAN.md — Wave-0 RED scaffold: 7 failing test files (principles/gate/memory parse + compile, diagnostics shape, org-loop examples, e2e team run) against the real planned surface (Wave 1)
- [x] V10-02-PLAN.md — grammar + AST nodes + parser transformers for `principles{}`/`gate{}`/`memory{}` (+ team_item/top_decl wiring); parse scaffolds GREEN (Wave 2)
- [x] V10-03-PLAN.md — compile-to-config: `GateConfig`/`MemoryConfig` + `compile_team(cwd=)` principles merge (V2 path) + 3 `TeamConfig` fields; compile scaffolds GREEN (Wave 3)
- [x] V10-04-PLAN.md — diagnostics bar: `VossTeamConfigError.construct`/`fix_hint`/`format_diagnostic()` + retrofit ~14 raise sites; diagnostic-shape scaffold GREEN (Wave 4)
- [x] V10-05-PLAN.md — three org-loop samples + end-to-end `team{}` on stub + verify/parity + frozen-schema git-diff guard + coordination-focus guard (Wave 5)

---

### Phase V11: ADE Org Integration

**Goal:** Turn the desktop app into a visual Agentic Development Environment centered on the org loop.

**Scope:** Add ADE panels — team roster, board, session tree, audit, reviewer verdict; budget visualization per root/card/agent; scope visualization per role/card; diff + verification drilldown; blocked-card human decision flow; run replay mode. Builds on the A-track shell (panes/grid/palette/themes/status bar/sidebar/SubAgentPanel/CodeIntelPanel) and the A12/A13 redesign+swarm work.

**Requirements (lock at SPEC):** VADE-01..10 (PRD ADE-01..10; namespaced to avoid clash with A12 ADE-01..08).

**Cross-cutting:** User can watch many agents without terminal spam; inspect why a card is blocked; compare reviewer outputs; replay a run; sign off from the audit view.

**Plans:** 8 plans across 5 waves (W0 contracts/reducer/fixtures -> W1 Rust data layer -> W2 view shell + panel stubs -> W3 structural/audit/budget/scope panels [parallel] -> W4 diff+blocked-decision + replay [parallel]).

Plans:
- [ ] V11-01-PLAN.md — Wave 0: hand-authored TS types (D-02 + V13.1 marker) + runtime guards + pure replay reducer (D-05/D-06) + golden JSON fixtures
- [ ] V11-02-PLAN.md — Wave 1: aggregate `load_run` + `enumerate_runs` (dual-layout filter) + `run_decision` Tauri commands (D-01/D-03/D-08) + orgStore/decisionActions wrappers
- [ ] V11-03-PLAN.md — Wave 2: `⌘⇧O` Org/Run view toggle (display:none, no PTY regression) + OrgViewShell (header/run-picker/10-tab) + StatusBar button + tokens + 10 panel stubs
- [ ] V11-04-PLAN.md — Wave 3: Roster + Board panels (VADE-01/02) + tested board column/risk derivation
- [ ] V11-05-PLAN.md — Wave 3: Session-tree (navigable) + Reviewer A/B verdict panels (VADE-03/05)
- [ ] V11-06-PLAN.md — Wave 3: Audit (sections + unsupported-claim flag + residual-risk) + Budget + Scope panels (VADE-04/06/07)
- [ ] V11-07-PLAN.md — Wave 4: Diff drilldown (a_verification surface + explicit no-diff state) + Blocked-card decision flow shelling the CLI (VADE-08/09, D-07/D-08, one-write-path)
- [ ] V11-08-PLAN.md — Wave 4: Run replay panel — step scrubber + reducer-driven board snapshot (VADE-10)

---

### Phase V12: Safety & Factory Fallbacks

**Goal:** Keep strict procedural rails only where autonomy is unsafe or inefficient — the deliberate "factory tier."

**Scope:** Irreversible actions require explicit confirmation; deploy/delete/migration/money/prod operations use fixed runbooks; latency-critical operations can opt into fixed pipelines; weak-model roles can use scaffolded procedures; every factory fallback is marked as such in audit; user can configure "factory-only" for certain directories/operations; human confirmation includes risk summary + the exact command/action.

**Requirements (lock at SPEC):** VSAFE-01..07 (PRD SAFE-01..07).

**Cross-cutting:** Dangerous actions cannot be executed by the autonomous EM alone; factory fallback does not contaminate the normal autonomous path; audit clearly shows when strict runbook mode was used.

**Plans:** 4 plans across 4 serial waves (policy foundation -> runtime gate -> audit persistence -> EM parity).

Plans:
- [ ] V12-01-PLAN.md — `.voss/safety.yml` schema/load + pure classifier for factory-only paths/operations, runbooks, pipelines, weak-model scaffolds (Wave 1)
- [ ] V12-02-PLAN.md — PermissionGate/tool invocation safety overlay: irreversible confirmation, runbook/fixed-pipeline route-or-deny, normal-path preservation (Wave 2)
- [ ] V12-03-PLAN.md — factory fallback audit persistence: additive RunRecorder/RunRecord evidence, audit marker, old-record hydration (Wave 3)
- [ ] V12-04-PLAN.md — EM role-gate parity + weak-model scaffold context + full V12 regression selection (Wave 4)

---

### Phase V13: External Developer SDK Surfaces (foundation)

**Goal:** Lock the external-developer SDK strategy across languages and surfaces. **Docs-only.** The shared contract snapshot + codegen substrate + CI drift gate moved to V13.1 (the first client owns the artifact). Per-language client builds are sub-phases **V13.1–V13.4**. No hosted/cloud SDK; data-model-coupled reader surfaces defer until their upstream phases freeze.

**Scope (V13 foundation, docs-only):** (1) **SDK Surface Matrix** (language × surface × tier) in `docs/ORCHESTRATION_LAYERS.md`; (2) **five stability tiers** (stable-now / experimental / generated-from-protocol / private-internal / deferred), every public surface assigned; (3) **language priority** locked (Python in-process → TS → Rust → Go → C-ABI-only); (4) **non-goals**; (5) **reconcile** `docs/sdk.md` with `PROTOCOL.md` (local loopback client ≠ hosted/remote — remove the stale "no service, no client" claim, cross-link); (6) **Python SDK** = link gaps to M7 (SDK-01..05) + enumerate org-layer read views to promote as V1/V3/V4/V9 harden, no dup spec.

**Requirements (lock at SPEC):** VSDK-01..06 (no PRD §P — V13 is post-P12; design source is `V13-SPEC.md` + the new SDK Surface Matrix in `docs/ORCHESTRATION_LAYERS.md`).

**Cross-cutting:** Pure documentation/strategy phase — no code, no CI, no dependency on any other phase; doable anytime. The contract snapshot + drift gate that clients generate from live in **V13.1**, not here. **Deep reader SDKs** (full audit/replay, team-compile helpers, capability introspection beyond protocol-exposed data) are GATED on V1 (capability schema) / V3 (team compile) / V4 (session tree — keystone) / V9 (audit product) freezing — each V13.x ships protocol-exposed readers now and deep readers when its upstream freezes. No Rust/Go reimplementation of EM/board/runtime semantics. No marketplace/plugin sandbox unless separately scoped.

**Acceptance (lock at SPEC):** a developer can tell which SDK to use per integration style; `docs/sdk.md` no longer contradicts `PROTOCOL.md`; public/private boundaries are explicit; Python SDK gaps are linked to M7 or superseded by V13.

**Plans:** TBD by V13-SPEC.md.

Plans:
- [ ] TBD (run `/gsd:spec-phase` to lock VSDK-01..06)

---
### Phase V13.1: TypeScript Local Client SDK

**Goal:** Highest-leverage non-Python SDK — VS Code extension, web UI, Electron/Tauri frontends, external dashboards, devtools. **First sub-phase** (per language priority), and the **owner of the shared contract snapshot**: it produces the committed `openapi.json` + event-union schema + CI drift gate that V13.2–.4 reuse.

**Scope:** **Contract snapshot** (static export of `openapi.json` + event-union schema from the app object, committed, deterministic exporter + CI drift gate, REST+SSE any-diff-fails); `voss serve` launcher wrapper; REST client; SSE typed-event client; permission-reply helpers; typed event union (from `EventEnvelope`); audit/session-tree readers limited to protocol-exposed data (deep readers when V9 freezes). NOT a general in-process runtime SDK.

**Requirements (lock at SPEC):** VSDK-TS-01..0N (`V13.1-SPEC.md`).

**Cross-cutting:** Self-contained — produces its own contract snapshot from the LOCKED PROTOCOL v1 (no dependency on V13; V13 is docs-only). Types generate from that snapshot. Downstream V13.2–.4 consume the same committed snapshot. No orchestration semantics reimplemented in TS.

**Plans:** 6 plans, 5 waves (Wave 0 contract snapshot substrate → Wave 1 TS scaffold+types → Wave 2 REST+SSE → Wave 3 launcher+boundary → Wave 4 integration suite).

Plans:
- [ ] V13.1-01-PLAN.md — Contract snapshot exporter + committed openapi.json/events.schema.json + Python drift gate (VSDK-TS-08)
- [ ] V13.1-02-PLAN.md — @vosslang/sdk scaffold + generated TS types + TS drift gate + exhaustive-union check (VSDK-TS-01)
- [ ] V13.1-03-PLAN.md — Typed REST client (Bearer + typed errors) + permission-reply helper (VSDK-TS-02, VSDK-TS-04)
- [ ] V13.1-04-PLAN.md — SSE typed-event async-iterable client with abort teardown (VSDK-TS-03)
- [ ] V13.1-05-PLAN.md — Node launcher/supervisor + build + zero-node:* core boundary enforcement (VSDK-TS-05, VSDK-TS-06)
- [ ] V13.1-06-PLAN.md — Integration suite vs real voss serve (REST/SSE/permission/launcher) (VSDK-TS-07 + behavioral 02–05)

---
### Phase V13.2: Rust Local / Native Client SDK

**Goal:** Native/local client for `voss-tui`, Tauri core, native IDE surfaces, performance-sensitive local tooling.

**Scope:** Protocol/event types (codegen tagged enum off `EventEnvelope`); local server supervisor (reuse `voss-tui` child-supervision); auth helpers (handshake + bearer); session/audit readers (protocol-exposed; deep readers when V4/V9 freeze). Avoid duplicating Python orchestration semantics.

**Requirements (locked at SPEC):** VSDK-RS-01..07 (`V13.2-SPEC.md`).

**Cross-cutting:** Generates off the **V13.1 contract snapshot** (reuses the committed `openapi.json` + event-union schema; does not re-export). Reuses existing `crates/voss-tui` / `voss-bridge` / `voss-auth` supervision + auth surfaces where present.

**Plans:** 6 plans, 5 waves. Most of the crate is built against a structurally-identical stub `AgentEvent` (Wave 0) so client/stream/supervisor/projection/tests proceed without the V13.1 snapshot; Wave 5 replaces the stub with real `cargo typify` output + the cargo drift gate, hard-blocking on V13.1 shipping `contracts/`.

Plans:
- [ ] V13.2-01-PLAN.md — Crate scaffold + workspace member + VossError + stub 21-member AgentEvent tagged enum + REST structs + cargo-typify/typify-tag coordination gate (Wave 1) [VSDK-RS-01, VSDK-RS-07]
- [ ] V13.2-02-PLAN.md — VossClient typed REST surface (token-redacting Debug) + Handshake bearer auth helper (Wave 2) [VSDK-RS-02, VSDK-RS-05]
- [ ] V13.2-03-PLAN.md — event_stream() typed SSE Stream + UiProjection lossy parity (21-member TryFrom) (Wave 3) [VSDK-RS-03, VSDK-RS-04]
- [ ] V13.2-04-PLAN.md — Supervisor (spawn/handshake/kill-on-drop, no orphan) lifted from server.rs (Wave 3) [VSDK-RS-06]
- [ ] V13.2-05-PLAN.md — FAKE_TURN integration suite: REST/401/409, SSE sequence + mid-stream drop, supervisor no-orphan (Wave 4) [VSDK-RS-02, VSDK-RS-03, VSDK-RS-05, VSDK-RS-06, VSDK-RS-07]
- [ ] V13.2-06-PLAN.md — Replace stub with cargo typify output + cargo drift gate (D-08); HARD-BLOCKS on V13.1 contracts/ (Wave 5) [VSDK-RS-01, VSDK-RS-07]

---
### Phase V13.3: Go Local / Headless Client SDK — ✅ COMPLETE (2026-06-08)

> ✅ **COMPLETE (6/6 plans, full suite green).** Greenfield Go SDK at `sdk/go/`: generated+drift-gated types, 21-member `Decode()` event model, typed REST (10 methods), typed SSE (`<-chan TypedEvent`, leak-free cancel), spawn/attach supervisor (no-orphan), permission helper, no-FFI guard. `go test ./...` + real-server `TestMain`/`VOSS_SERVE_FAKE_TURN` integration all green; drift gate live. Deviations: go floor→1.24 (audited deps), in-SDK 3.1→3.0 codegen normalizer (`internal/specgen`, oapi-codegen can't read 3.1), 60s spawn handshake + `LITELLM_LOCAL_MODEL_COST_MAP=true`. VSDK-GO-01..08 met. Summaries: `V13.3-0{1..6}-SUMMARY.md`.

**Goal:** Infra/headless automation — CI bots, devops tools, lightweight local runners, repo-automation daemons.

**Scope:** Start/attach to `voss serve`; create session; send message; stream events; approve/deny permission gates; export audit/session data. Local REST/SSE only — no Python FFI, no runtime-semantics reimplementation.

**Requirements (lock at SPEC):** VSDK-GO-01..08 (`V13.3-SPEC.md`).

**Cross-cutting:** Generates off the **V13.1 contract snapshot**. Go's value here is infra glue, not orchestration.

**Plans:** 6 plans, 5 waves. Greenfield Go module at `sdk/go/` (stdlib net/http + oapi-codegen types-only). Wave 0 (Plan 01) captures a live-server OpenAPI fixture so codegen + all downstream work proceed NOW without V13.1; the drift gate `t.Skip`s until V13.1 ships `contracts/openapi.json` (D-08). DAG: W0 01 (module skeleton + fixture + codegen + Discriminator probe + RED scaffolds) -> W1 02 (event model: 21-member Decode dispatcher + VossError) -> W2 03 (handshake + AttachClient + 9 typed REST methods) ∥ 04 (channel SSE consumer, leak-free cancel) -> W3 05 (spawn supervisor, no-orphan PID) -> W4 06 (permission helper + no-FFI guard + real-server TestMain integration suite + drift finalize).

Plans:
- [x] V13.3-01-PLAN.md — Module skeleton + openapi.fixture.json + oapi-codegen types.gen.go + Discriminator probe + drift gate + RED scaffolds (Wave 0) [VSDK-GO-01, VSDK-GO-08]
- [x] V13.3-02-PLAN.md — Full-fidelity event model: TypedEvent + 21 structs + exhaustive Decode() (incl. principles_overflow) + ErrUnknownEventType + VossError (Wave 1) [VSDK-GO-02]
- [x] V13.3-03-PLAN.md — Handshake parse + AttachClient + bearer chokepoint + 9 typed REST methods (round-trip/401/409) (Wave 2) [VSDK-GO-03, VSDK-GO-06]
- [x] V13.3-04-PLAN.md — Typed SSE consumer over <-chan TypedEvent (hand-parsed framing, context-cancel teardown, no leak) (Wave 2) [VSDK-GO-04]
- [x] V13.3-05-PLAN.md — Spawn supervisor (voss serve --port 0, stdin heartbeat, interpreter resolution, SpawnError, no-orphan Close) (Wave 3) [VSDK-GO-05]
- [x] V13.3-06-PLAN.md — PermissionReply + no-FFI/no-orchestration guard + shared TestMain real-server integration suite + drift gate finalize (Wave 4) [VSDK-GO-07, VSDK-GO-08, VSDK-GO-01]

---
### Phase V13.4: C ABI / Schema Documentation — ✅ COMPLETE (2026-06-08)

> ✅ **COMPLETE (1/1 plan, doc-only, zero code).** `docs/native-embedding.md` — native/C embedder reference (loopback REST+SSE + `{v,port,token}` Bearer handshake, PROTOCOL.md + contracts/*.json pointers w/ no schema fork, JSON→native table w/ `type` discriminator + member-set-authoritative-from `events.schema.json`, five-tier stability statement, C-headers/cbindgen/FFI deferred w/ activation trigger). `docs/check-native-embedding-refs.sh` — refs-resolve gate (hard-fail on missing always-expected; warn-skip exit 0 while `docs/ORCHESTRATION_LAYERS.md` pending V13). VSDK-C-01..06 met; PROTOCOL.md/sdk.md byte-unchanged. Summary: `V13.4-01-SUMMARY.md`. Open: VSDK-C-01 prose-readability human-check (manual-only).

**Goal:** NOT a full SDK. Stable JSON-schema / ABI documentation for native embedders, plus an optional tiny FFI around a local client only if a concrete native embedder demands it.

**Scope:** JSON-schema/ABI doc for the protocol contract; (deferred) C headers generated from protocol structs much later. No high-level C ergonomics — Voss's value is orchestration, event streams, JSON contracts, and workflow state, all a poor C fit.

**Requirements (lock at SPEC):** VSDK-C-01..0N (`V13.4-SPEC.md`).

**Cross-cutting:** Doc-only unless a concrete native embedder appears. Lowest priority; may stay deferred indefinitely.

**Plans:** 1 plan.

Plans:
- [x] V13.4-01-PLAN.md — author docs/native-embedding.md (native/C embedder contract reference: loopback+Bearer model, PROTOCOL/contracts pointers, JSON->native table, stability tiers, FFI deferral) + docs/check-native-embedding-refs.sh (references-resolve gate)

---
### Phase V14: ADE Run Cockpit (Integrated Redesign + Live Data Unification)

**Goal:** Recompose V11's 10 built org panels into one integrated run cockpit and unify the live PTY/SSE agent registry with the static CLI-JSON `RunData` into a single UI model, closing the design-contract gaps in `research/ade-ui-design-contract-research.md`.

**Scope:** Normalized UI data model (Run/Card/Agent/SessionNode/Evidence/Decision) merging live registry + snapshot; card↔session/pane binding; integrated cockpit layout (Board spine + Card detail drawer + Timeline/replay rail + gate bar, tabs demoted); RunCommandBar intake (mode/team/scope/budget/native-vs-terminal); global AttentionQueue; live SSE wiring gated on V13.1 (snapshot fallback); A13 swarm-manifest reconciliation; Live↔Review mode toggle; best-effort feedback write-path; dense/a11y pass on A12 Ignite tokens; **refreshed sparse quick-launch modal (VCKP-11)**; **"Manage with Voss" adopt flow — forward-only, best-effort for external CLIs (VCKP-12)**. Recomposes existing `org/panels/*` — not a panel rewrite.

**Requirements (LOCKED in SPEC):** VCKP-01..13 (10 core · 3 gated; ambiguity 0.141). SPEC: `…/V14-SPEC.md`; CONTEXT: `…/V14-CONTEXT.md`; design brief: `…/V14-DESIGN-BRIEF.md`. Design operator-reviewed via throwaway HTML mockups (since removed); re-mockup via `/gsd-ui-phase V14` if needed.

**Cross-cutting:** Builds on V11 (built); reuses A12 tokens; live-SSE wave gated on V13.1 contract snapshot; swarm reconciliation gated on A13. Keystone risk = the id bridge correlating live pane/agent ids with snapshot card/session-node ids (verify before the binding wave). **Locked engineering limit:** adopting an external CLI agent (VCKP-12) is PTY-only — cost/transcript-audit/budget-monitor/review/advisory-scope, NOT per-tool gate enforcement (Voss-native only). No new harness contracts — V14 is a PROTOCOL v1 client.

**Plans:** 13 plans across 8 waves (W0 scaffold/model-stubs/id-bridge fixture + A1 keystone verification → W1 normalized model + adapters → W2 card↔session binding ∥ cockpit layout shell → W3 RunCommandBar ∥ AttentionQueue → W4 live SSE wiring → W5 swarm reconciliation ∥ Live↔Review toggle → W6 quick-launch refresh ∥ adopt flow → W7 managed-launch enforcement tiers ∥ feedback write-path + a11y + human-verify).

Plans:
- [ ] V14-00-PLAN.md — Wave 0 scaffold: normalized-model stubs + selection store + fixtures + mock SSE + A1 keystone verification
- [ ] V14-01-PLAN.md — VCKP-01 normalized model adapter (snapshot spine + live overlay) + selection observed by ≥2 surfaces
- [ ] V14-02-PLAN.md — VCKP-02 keystone id-bridge (resolveCard, two mechanisms: native echo + terminal cardId↔paneId)
- [ ] V14-03-PLAN.md — VCKP-05 cockpit shell (4 regions, one selection) replacing the tab shell + CardDrawer + GateBar
- [ ] V14-04-PLAN.md — VCKP-03 RunCommandBar intake starting terminal + native runs; Auto budget/scope gate
- [ ] V14-05-PLAN.md — VCKP-04 global AttentionQueue (snapshot decisions + live events) + StatusBar pill
- [ ] V14-06-PLAN.md — VCKP-06 live SSE wiring (mock-verified) + live/snapshot label + snapshot fallback [gated]
- [ ] V14-07-PLAN.md — VCKP-07 swarm-manifest reconciliation into roster/board [gated]
- [ ] V14-08-PLAN.md — VCKP-08 Live↔Review toggle preserving the grid + completed launch stub + D-07 Open-in-grid
- [ ] V14-09-PLAN.md — VCKP-11 sparse preset quick-launch modal (drop raw-command/explainer) + tier surface
- [ ] V14-10-PLAN.md — VCKP-12 'Manage with Voss' adopt flow (forward-only, tier C, no jargon)
- [ ] V14-11-PLAN.md — VCKP-13 managed launch: OS scope-sandbox + budget-kill + honest capability tiers (Rust)
- [ ] V14-12-PLAN.md — VCKP-09 feedback write-path [gated] + VCKP-10 dense/a11y pass + phase-final human-verify

---
### Phase V15: Live Plane Integration (sidecar handshake + structured pane rendering)

**Goal:** Plug the V14 cockpit into a real `voss serve` and graduate Voss-native panes from raw PTY output to structured protocol rendering — the live plane V14 mock-gated, plus the one approved-mockup element V14 deliberately skipped.

**Scope:**
- **Sidecar + handshake (keystone, spike first):** Tauri command `start_voss_serve` — spawn/attach `voss serve` as an app-owned child, read the one-line `{v,port,token}` stdout handshake, return `{port, token}` to the webview, own lifecycle (one server per workspace, reuse-if-alive, kill on app quit). Port `crates/voss-sdk` `spawn_with` (60s cold-start timeout, `LITELLM_LOCAL_MODEL_COST_MAP=true`). Resolves V14 Pitfall 4 (webview cannot spawn the server).
- **Plug the injectable sockets:** construct the V13.1 TS client from the handshake; RunCommandBar native target → real `createSession` (delete the disabled-with-reason gate); drawer comments → live `followUpClient`; `sseClient` consumes the real stream (live/snapshot label flips for real); SSE events → AttentionQueue + normalized-model overlay on real payloads (expect fixture-vs-real drift fixes).
- **Structured pane rendering:** Voss-native sessions get a protocol-backed pane body — PROTOCOL §6 event union → DOM (EM task header w/ scope·budget·risk line, `fs_read`/`fs_edit`/`code_search` tool lines, plan prose, `stream.delta`, `final`); external CLI panes stay PTY/xterm. Visual contract: the pane-content of `.planning/sketches/V14-livework-mockup.html` (distill to UI-SPEC before planning — V14 lesson).
- **Inline permission gate:** `permission.updated` renders Allow once / Allow for scope / Deny inside the pane AND feeds the global AttentionQueue (D-06 stays the aggregator); replies via `POST /session/:id/permission`.
- Statusbar `● live · voss serve :<port>` once a session is attached.

**Out of scope:** VCKP-13b permission proxy (hook-capable CLI gating — separate phase); replay rollback/re-run; embedded browser; new harness contracts (V15 remains a PROTOCOL v1 client).

**Requirements:** VLIVE-01, VLIVE-02, VLIVE-03, VLIVE-04, VLIVE-05, VLIVE-06, VLIVE-07, VLIVE-08 (locked in `V15-SPEC.md`, ambiguity 0.123).

**Cross-cutting:** Builds on V14 (complete) + V13.1 TS SDK (shipped) + the real `voss serve` (validated by V13.2/V13.3 integration suites). Keystone risk = the sidecar handshake; everything downstream is plumbing clients V14 already left sockets for. Seed: `.planning/notes/seed-structured-pane-rendering.md`.

**Plans:** 6 plans, 5 waves (sequential keystone chain: sidecar command → client+sockets → structured pane → permission gate+lifecycle ∥ attach → hermetic AC suite + human checkpoint).

Plans:
- [x] V15-01-PLAN.md — Sidecar Tauri command + managed per-workspace lifecycle (VLIVE-01) [wave 1] — ✅ 2026-06-10
- [x] V15-02-PLAN.md — V13.1 client construction + three V14 sockets + live SSE (VLIVE-02, VLIVE-03) [wave 2] — ✅ 2026-06-10
- [x] V15-03-PLAN.md — ProtocolPane structured rendering + native-pane threading (VLIVE-04) [wave 3] — ✅ 2026-06-10
- [x] V15-04-PLAN.md — Inline permission gate + lifecycle states (VLIVE-05, VLIVE-07) [wave 4] — ✅ 2026-06-10
- [x] V15-05-PLAN.md — Attach-to-existing server sessions sidebar (VLIVE-06) [wave 4] — ✅ 2026-06-10
- [ ] V15-06-PLAN.md — Hermetic stub-provider AC suite + human real-run checkpoint (VLIVE-08) [wave 5]

---
### Phase V16: Managed Docs & Prompt Generation (Jinja2 layout-aware doc sync)

**Goal:** Extend Voss's existing Jinja2 template infrastructure (`voss/template_render.py`, `voss/templates/`) into a per-project doc/prompt generation system, so Voss feels installed-into a project rather than run-against it.

**Scope:**
- **Layout-aware workflow docs:** templates compiled with a layout-variables context (repo-root vs worktree layout, command prefixes, workspace paths) and written into the project during init and a new idempotent sync operation.
- **Managed section in agent instruction file:** marker-delimited block (`<!-- voss:managed-start/end -->`) in AGENTS.md/CLAUDE.md, regenerated from a single context struct (project name/type, enabled companion tools, review config, install/check commands, generated doc list, layout vars). Never touches content outside markers; inserts block if absent.
- **Agent/reviewer prompt templates:** synced into the project as plain `.md` (jinja suffix stripped), lightweight runtime placeholder substitution (`{{ AGENT }}`, `{{ PROJECT }}`, `{{ WORKSPACE }}`) via string replace before prompt delivery — deliberately not full Jinja at runtime so users can edit synced prompts.
- **Template rendering core:** reuse `render_package_template` (StrictUndefined, PackageLoader); extend as needed, keep single entrypoint.

**Out of scope:** templating for `.voss` language programs; multi-repo/monorepo workspace orchestration.

**Requirements:** R1–R6 (locked in `V16-SPEC.md`; V-track phase, requirements live in SPEC not REQUIREMENTS.md).

**Cross-cutting:** Builds on existing `voss init` template rendering (cli.py templates/init flow). Seed: `.planning/seeds/managed-docs-generation.md`. Verification anchor: managed-section idempotency tests (re-running sync is a no-op; user content outside markers untouched).

**Plans:** 4 plans (4 waves): input layer → templates → sync orchestrator+CLI → prompt sync (stretch R5/R6).

Plans:
- [x] V16-01-PLAN.md — Layout derivation + project: config reader + SyncContext contract (wave 1) — executed 2026-06-10
- [x] V16-02-PLAN.md — Doc + fence-body Jinja templates (wave 2) — executed 2026-06-10
- [x] V16-03-PLAN.md — voss sync orchestrator + CLI + manifest + idempotency (wave 3) — executed 2026-06-10
- [x] V16-04-PLAN.md — Prompt sync + ${} override loader + hash-guard (stretch R5/R6, wave 4) — executed 2026-06-10 — **PHASE V16 COMPLETE (4/4, R1–R6)**

---

### Phase V17: External Agent Coordination Surface (claims + bus verbs as protocol-plane clients)

**Goal:** Give external CLI agents (Claude Code, Codex, OpenCode in voss-app panes) coordination primitives by exposing the org plane Voss already has — adoption registry, board cards, server plane, SSE event union — through shell-scriptable CLI verbs. Not a parallel file-bus substrate: every primitive is a thin client of the existing plane, coherent with the V14/V15 direction (pull agents *into* the plane, not around it).

**Scope (4 slices, each on an existing asset):**
- **Advisory claims** (no upstream gate): `voss claims stake/check/release` — `check <paths>` exits 1 on overlap with another agent's registered scope → shell-scriptable pre-edit guard. Makes `adopt.ts`'s already-applied advisory scope *checkable*; reuses `sandbox.rs::validate_scope` canonicalization for overlap detection; URI claims `card://<id>` = V5 board cards (work-item locking on the existing ontology); storage = SQLite/server plane. The **tier-C complement** to VCKP-13 enforcement tiers (OS sandbox covers A/B; adopted/unmanaged get the advisory layer).
- **Messaging + wait/inbox** (gated on V15): `voss bus send/inbox/wait` as protocol-plane clients — messages are a new event type in the `contracts/events.schema.json` union; `wait --mention <me>` blocks on the SSE stream until filter match. Replaces A13's result-file + PTY-idle heuristic with deterministic fan-in; unlocks mid-swarm agent↔agent Q&A. Cockpit rendering + AttentionQueue integration free via the union.
- **Advice arrays** (trivial, independent): `advice: [...]` suggested-next-commands in structured CLI output (`RunData`, `voss board`, new verbs) — guides autonomous loops.
- **Conventions, zero code:** label vocabulary (`coord:blocker`, `coord:handoff`, `mission:<id>`, `review-request`) documented in the V16 managed AGENTS.md section — V16 is the delivery vehicle telling external agents these verbs exist.

**Out of scope:** file JSONL substrate + fs locks + byte cursors + fs-notify (server-replacement infra — Voss has the server; reopens only if no-server headless coordination becomes a real constraint); standalone hooks engine (mention→spawn = AttentionQueue action / V7 EM dispatch behavior); delivery guarantees/acks; cross-machine sync; message-type schema enforcement; observer TUI / bridges; global cross-project storage.

**Requirements:** VBUS-01..08 (locked in `V17-SPEC.md`, ambiguity 0.16; V-track phase, requirements live in SPEC not REQUIREMENTS.md).

**Cross-cutting:** Substrate for A13 swarm resume (slice 2 supersedes SWM-04/05/06 one-shot task/result formats) and the Agents-launcher backlog phase (999.1). Claims consumers: `apps/voss-app/src/org/adopt.ts` adopted agents (tier C always). Compliance depends on V16-managed instructions. Eventual `.voss` declaration could compile-to-config per V10. Source + reframe rationale: `.planning/seeds/SEED-001-coordination-bus.md`.

**Plans:** 7 plans, 6 waves (claims/identity/doc waves executable now; bus waves V15-gated).

Plans:
- [ ] V17-01-PLAN.md — Wave 0 test scaffolds: claims/identity RED + bus xfail(V15) + coherence guard green (VBUS-01..08) [wave 1]
- [ ] V17-02-PLAN.md — Claims overlap engine + SQLite storage + atomic stake (VBUS-01, VBUS-02) [wave 2]
- [ ] V17-03-PLAN.md — Claims click verbs + identity exit-codes + advice arrays + CLI registration (VBUS-01, VBUS-02, VBUS-06) [wave 3]
- [ ] V17-04-PLAN.md — VOSS_AGENT_ID slug minting (TS) + env injection at 3 Rust spawn sites (VBUS-03) [wave 2]
- [ ] V17-05-PLAN.md — [V15-GATED] bus.message event type + /bus/* routes + durable journal + SDK regen (VBUS-04, VBUS-05) [wave 4]
- [ ] V17-06-PLAN.md — [V15-GATED] bus send/inbox/wait client verbs + discovery/advice + CLI registration (VBUS-04, VBUS-06) [wave 5]
- [ ] V17-07-PLAN.md — docs/agent-coordination.md + V16 handoff note + coherence-guard verification (VBUS-07, VBUS-08) [wave 6]

---

### Phase V18: Budget-Aware Context Allocator (Token Optimization)

**Goal:** Insert a budget-aware context allocator at the harness's one message-assembly chokepoint (`voss/harness/agent.py:708-716`), which today replays **every** prior iteration in full on every loop entry — unbounded in iteration count. The allocator packs the variable (non-cached) region under a token ceiling: recent iterations full, older as one-line digests, ancient folded into a rolling summary, with re-fetch pointers to existing retrieval. Reuse-not-rebuild: V18 **consumes** M10 code-intel + F2 hybrid search + F3 budget telemetry + T4 caching; it adds no index, embeddings, or second budget system. The competitive-teardown origin (external "Plyrium Forge" paywalled token-saver) confirmed Voss already owns index + budgets + small agents — the packer is the only missing primitive.

**Scope:**
- **Context allocator:** pure, provider-free `ContextAllocator` computing `packing_budget = token_budget − reserve(...)` and rendering replay to fit (estimation via `_default_token_count`, `agent.py:73`).
- **Iteration-age decay:** full / one-line-digest / folded tiers; newest always full; structural/extractive digesting — no LLM-summarization on the default path.
- **Cache-coherent packing:** never repack the T4 `cache_control` prefix (`agent.py:363-395`); recompact tier boundaries only on hysteresis thresholds so the prompt cache stays warm; optional second breakpoint on the stabilized replay prefix.
- **Eviction pointers:** dropped detail leaves a re-fetch hint resolvable via M10 `voss/harness/code/` (or F2) — no extra context stored.
- **Savings ledger:** session-scoped `token-savings.jsonl` (`packed ≤ original`) + honest `/cost` + F3 savings line.
- **Config + escape hatch:** `[context]` config (tier sizes, water marks) + `--no-pack` byte-identical disable; conservative default profile.
- **Quality gate:** M5 packing-on-vs-off eval — success rate not regressed beyond tolerance while input tokens drop; the gate must bite on an over-aggressive profile.

**Out of scope:** new code index / embeddings / vector store (M10/F2 own it); LLM-based summarization as default (opt-in profile, later); context-pane UI (F4 heatmap renders, V18 emits numbers); changing `tools.py` 30KB caps or `HISTORY_WINDOW`; provider exact-tokenizer integration; cross-session/cross-agent shared packing; retroactive savings (only future turns optimized — already-sent tokens are billed).

**Requirements:** VOPT-01..08 (locked in `V18-SPEC.md`, ambiguity 0.19; V-track phase, requirements live in SPEC not REQUIREMENTS.md).

**Cross-cutting:** Reuses M10 (`voss/harness/code/`), F2 (hybrid search), F3 (`recorder.py` budget OSC), T4 (`agent.py` cache prefix + `session.py:115-121` cache-token telemetry). Preserves PRD §9 top risk: `voss do`/`voss chat` working every wave. Origin analysis: competitive teardown of Plyrium Forge token-saver (Electron+Rust ADE; code-RAG index + per-agent budget packer + savings ledger feeding worktree-isolated agents).

**Plans:** 5 plans across 5 waves (serial spine — each layer is proven on the prior; byte-identity + cache-coherence proof ordering forbids parallelizing the agent.py/cli.py seams):
- [ ] V18-01-PLAN.md — Wave 0 RED test scaffold: failing tests for VOPT-01..08 (allocator, agent-packing, savings-ledger, eval-gate)
- [ ] V18-02-PLAN.md — Pure ContextAllocator + tiered decay (full/digest/fold) + eviction pointers + hysteresis (VOPT-01/02/03/04)
- [ ] V18-03-PLAN.md — Cache-coherent integration at agent.py:713 + [context] config + --no-pack byte-identical escape hatch (VOPT-03/06)
- [ ] V18-04-PLAN.md — Savings ledger (packed≤original) + cache-netted $ + /cost & F3 OSC savings line (VOPT-05; D-01..D-04)
- [ ] V18-05-PLAN.md — M5 packing-on-vs-off quality gate (biting) + coherence guard (VOPT-07/08)

---

### Phase V19: Semantic Code Memory + Tiered Index Routing

**Goal:** Add the missing *semantic* (embedding-based) layer to codebase retrieval: a derived, rebuildable vector index over code chunks so agents can answer concept-level queries ("where do we handle retry backoff") without burning frontier-model tokens on agentic grep loops — and route all index-enrichment work (chunk summaries, symbol descriptions, batch classification) to a cheap fast model tier (GPT-OSS/Ollama, Haiku-class) via the existing model router, so the frontier model never pays for index maintenance. Reuse-not-rebuild: V19 **consumes** M10 code-intel (project index, symbol boundaries → chunking), F2 hybrid recall (BM25 + Chroma RRF machinery in `MemoryStore`), `voss_runtime/memory/semantic.py` (Chroma wrapper + embedding-function selection), and `/models` routing (`model_router.py` / `model_catalog.py` tier roles). It adds no second index substrate and no second budget system.

**Primary frame: token economics** (enrichment + retrieval costs move to local embeddings, BM25, and the cheap tier); retrieval quality and ADE differentiation are secondary benefits.

**Headline deliverables (to be locked in SPEC):**
- `CodeIndex` — derived cache under `.voss-cache/` (rebuildable, no tombstones — distinct lifecycle from curated `.voss/memory/`), Chroma collection `voss_code`, content-hash manifest for lazy incremental reindex (never full reindex per session).
- Symbol-aware chunking on function/class boundaries, reusing M10 index symbol data + `language-metadata/` (chunking quality > embedding model choice; model stays a config knob via `default_embedding_model`).
- Semantic recall surface: `code_recall` tool (named to avoid colliding with M10's lexical/structural `code_search`), RRF-merged with BM25 per the F2 pattern — vectors for concept queries, grep/BM25 still wins symbol lookup.
- Tiered routing role for index jobs: enrichment (one-line symbol descriptions, chunk summaries) dispatched to a cheap-tier model through `model_router.py`; pure embed/BM25 passes use no LLM at all.
- Background index worker + progress: session start never blocks (local embedding cold-load is seconds; first big-repo index is minutes).

**Requirements:** VSEM-01..08 (locked in `V19-SPEC.md` — V-track phase, requirements live there not in REQUIREMENTS.md).

**Plans:** 6 plans in 5 waves (wave 0 RED scaffold → CodeIndex core → service+tool / CLI verb → enrichment → injection).

- [ ] V19-01-PLAN.md — Wave 0 RED test scaffold (tests/code_recall/* for VSEM-01..08) + Hit line_start/line_end + slow marker
- [ ] V19-02-PLAN.md — CodeIndex core: symbol-aware chunking + hash manifest + incremental reindex + RRF query [VSEM-01, VSEM-02]
- [ ] V19-03-PLAN.md — Background daemon CodeIndexService + code_recall agent tool (BM25 degradation, p95) [VSEM-03, VSEM-04]
- [ ] V19-04-PLAN.md — `voss recall` unified cross-corpus CLI verb (plain + --json source field) [VSEM-05]
- [ ] V19-05-PLAN.md — V18-region auto-injection (≤1000 tok, evictable, off-switch) [VSEM-06]
- [ ] V19-06-PLAN.md — index_enrich router role + opt-in enrichment + budget cap + ledger line [VSEM-07, VSEM-08]

**Cross-cutting:** Index under `.voss-cache/` per M2 COG-07 / M10 convention. Chroma stays optional (`voss[search]`), BM25-only degradation per F2. Tier assignment must respect V18 budget telemetry (enrichment spend visible in savings/cost ledger).

**Out of scope:** replacing M10 lexical/structural search or LSP surfaces; global cross-project memory layer (separate seed if it grows); ingesting external memory markdown (stretch, separate seed); code-tuned embedding API models as default (start local sentence-transformers, measure, swap via config).

**Seed source:** [`seeds/SEED-002-codebase-rag-tiered-indexing.md`](seeds/SEED-002-codebase-rag-tiered-indexing.md) (enriched 2026-06-11; design notes + breadcrumbs there).

### Phase V20: Harness Residue Hardening

**Goal:** Ship the small, confirmed residue of harness-principles gaps — nothing else. Audit verdict (2026-06-11): the hard parts are already built (V4 spine, budget cages, V5 double-gate, hash-fences, claims); V20 closes only five cheap, in-tree gaps: (1) `voss sync --check` drift gate + managed-doc edit-guard (manifest hashes are write-only today; docs silently clobber user edits), (2) friction scoring — pure reducer over already-recorded failures[]/validation[] into one eval row field + summary column, (3) worker mission brief — agent_task/dispatch_card inject outcome + sibling roster + claimed-scope hints from claims + ticket table, (4) `critical` risk tier with a human-approval Done predicate no agent verdict can clear + operator approve/reject verb, (5) **BUG** Reviewer-B runs fast tier at the Done gate (`b_passes` passes no tier; contract says B.strong at →Done) + B gains a card-borne repo_context field. All gaps re-confirmed against source at planning time (`V20-CONTEXT.md` has file:line evidence).

**Plans:** 01 sync-check, 02 friction, 03 mission-brief, 05 B-strong-tier (all wave 1, independent) → 04 critical-tier (wave 2, depends on 05 — both edit the Done predicate tuples). Tests-first per plan; 05 is a correctness fix committed separately.

**Requirements:** VRES-01..05 (V-track phase — confirmations + requirements live in `V20-CONTEXT.md`, not REQUIREMENTS.md).

**Out of scope (scoped one paragraph each in `V20-DEFERRED-SCOPING.md`, operator promotes individually):** mid-task 429 failover on the default OAuth path (the real model gap — typed errors + FallbackProvider wrap + hung-stream triggers); board/EM crash-recovery rehydrate from the audit snapshot; coordination bus send/inbox/wait verbs (V17 05/06, V15-gated); gate-before-spend + idle backoff in the EM loop; PTY stuck-detection + health badges.

- [ ] V20-01-PLAN.md — `voss sync --check` drift gate + managed-doc edit-guard [VRES-01]
- [ ] V20-02-PLAN.md — friction reducer + eval row field + summary column [VRES-02]
- [ ] V20-03-PLAN.md — mission brief (outcome + siblings + claimed scopes) at dispatch [VRES-03]
- [ ] V20-04-PLAN.md — critical risk tier + human_approved gate + approve/reject verb [VRES-04]
- [ ] V20-05-PLAN.md — BUG: Reviewer-B strong tier at Done + repo_context card field [VRES-05]

### Phase V21: Global Cross-Project Memory

**Goal:** Facts that transcend a single repo — operator preferences, recurring conventions, cross-repo patterns — live in a durable global store (`~/.voss/memory/global/`) and surface in recall everywhere: `MemoryStore.recall()` and the unified `voss recall` verb (V19) query project + global stores and RRF-merge rankings, hits labeled `[global]`. Includes explicit promotion (`voss memory promote <locator>` — copy a project memory into the global store) and scope rules (global store is curated like `.voss/memory/`, tombstones apply; never auto-promoted). Reuse-not-rebuild: second `MemoryStore` instance rooted at the global path + the existing `_rrf_merge`/source-label machinery from V19's cross-corpus CLI — no new store type, no new schema.

**Requirements:** VGMEM-01..08 (minted at plan time from CONTEXT D-01..D-08 + goal — discuss-direct path, no SPEC; traceability table in `V21-REQUIREMENTS.md`).

**Out of scope:** cloud sync / multi-machine (PROJECT.md exclusion stands); auto-promotion heuristics (manual verb only this phase); global code index (code stays per-repo — derived from the repo it describes).

**Origin:** gap #2 from the 2026-06-11 memory/RAG design discussion (see `seeds/SEED-002-codebase-rag-tiered-indexing.md` stretch notes). Depends on: V19 (unified recall surface + source labels).

**Plans:** 4 plans · 3 waves (W0 RED scaffold; W1 store+config foundation; W2 CLI verbs ∥ recall fusion). Executes ONLY AFTER V19 ships (V21-04 extends the as-built V19-04 recall_cmd).

Plans:
- [x] V21-01-PLAN.md — Wave-0 RED scaffold: test_memory_global.py (17 VGMEM stubs) + tmp_voss_global fixture [VGMEM-01..08]
- [x] V21-02-PLAN.md — Foundation: MemoryStore root_override + _global_memory_root/make_global_store/_repo_id + [memory] off-switch [VGMEM-01, VGMEM-07]
- [x] V21-03-PLAN.md — CLI verbs: promote (copy+provenance+dedup+--list) + forget --global + vacuum --global [VGMEM-03, VGMEM-04, VGMEM-05]
- [ ] V21-04-PLAN.md — Recall fusion: dual-store [global] RRF in agent tool + 3 attach sites + voss recall extension [VGMEM-02, VGMEM-06, VGMEM-08]

### Phase V22: External Memory & Docs Ingest

**Goal:** Bring designated markdown corpora into recall as labeled, derived sources: repo docs (README, docs/) and operator-configured external memory directories (e.g. Claude Code file-memory dirs, SecondBrain-style vaults) — so `voss recall` answers from project knowledge that lives outside code and conversation. Each corpus is a config-declared source (`[recall.sources]` — name, path, glob) ingested through the existing `SemanticMemory._ingest_source` lineage into its own labeled collection with a per-source hash manifest (derived cache, rebuildable — same lifecycle as V19's CodeIndex, NOT curated memory). Hits carry the source name; raw external files are NEVER written back (read-only ingest — SecondBrain raw-sources immutability respected by construction). Reuse-not-rebuild: V19 manifest + background-worker + RRF patterns applied to markdown chunks (section-boundary chunking instead of symbol-boundary).

**Requirements:** VXMEM-01..08 (locked in `V22-SPEC.md`; V-track SPEC phase — requirements live in the SPEC, not REQUIREMENTS.md).

**Out of scope:** writing/syncing back to external sources (read-only forever this phase); non-markdown formats (PDF/HTML — later seed); auto-discovery of external dirs (explicit config only); `.planning/` GSD artifacts as a default source (privacy/noise — opt-in path only).

**Origin:** gap #3 from the 2026-06-11 memory/RAG design discussion (V19 SPEC out-of-scope "ingesting external memory markdown"). Depends on: V19 (CodeIndex patterns + unified recall), V21 (source-label conventions across >2 corpora).

**Plans:** 5 plans · 5 waves (W0 RED scaffold + fixture vault; W1 config+chunker; W2 index engine+daemon; W3 voss recall fan-out; W4 agent-tool fan-out + golden gate). Direct port of V19 CodeIndex with heading-boundary chunking. cli.py/tools.py/config.py serialized across waves.

Plans:
- [x] V22-01-PLAN.md — Wave-0 RED scaffold: recall package skeleton + 8 test files (23 VXMEM tests) + committed fixture vault [VXMEM-01..08]
- [x] V22-02-PLAN.md — config get_recall_sources() (tomllib) + extract_md_chunks() heading-boundary chunker [VXMEM-01, VXMEM-02, VXMEM-04]
- [x] V22-03-PLAN.md — ExternalSourceIndex (incremental per-source) + ExternalRecallService daemon (read-only, degrade-until-ready) [VXMEM-03, VXMEM-05, VXMEM-06]
- [x] V22-04-PLAN.md — voss recall fan-out + _recall_hit_fields source passthrough + --refresh rebuild [VXMEM-07]
- [ ] V22-05-PLAN.md — agent memory_recall external fan-out (Option B) + make_toolset spawn + golden-query gate [VXMEM-07, VXMEM-08]

### Phase V23: Retrieval-Aware Memory Ranking & Hygiene

**Goal:** Close the ranking + hygiene gaps surfaced by the froots.ai/memory competitive teardown (2026-06-12). Voss recall is already hybrid (BM25 + Chroma RRF in `MemoryStore.recall()` — stronger than froots' vector-only), but ranking is similarity-only with no quality floor (low-relevance hits still fill `top_k` and burn injected tokens), no retrieval telemetry exists (froots schemas `last_retrieved`/`retrieval_count`; neither product *uses* them — Voss can ship the full loop: telemetry → rescoring boost → retrieval-aware eviction), and the `.voss/memory/` filesystem mirror has no drift detection (hand-edits to mirror files silently diverge from the index — same failure shape `voss sync --check` just closed for managed docs). Reuse-not-rebuild: extends `MemoryStore` (`_rrf_merge`, eviction/vacuum machinery, hash-manifest pattern from V19 CodeIndex); no new store type, no new schema substrate.

**Scope:**
- **Retrieval telemetry:** record `last_retrieved` + `retrieval_count` per memory row at recall time; surfaced in `voss memory list/show`.
- **Quality floor:** per-retriever raw-score floor pre-fusion (BM25 + cosine each have native scales; RRF scores don't threshold meaningfully) + drop hits appearing in neither retriever's top-N — fewer junk injections, pairs with V18 token-ceiling goals.
- **Recency × frequency rescoring:** boost on RRF output from telemetry (configurable weights, off-switch; similarity-only remains the escape hatch).
- **Retrieval-aware eviction:** eviction/vacuum order prefers never-retrieved + stale-retrieved rows over merely-old ones (extends existing eviction tests).
- **Mirror drift gate:** `voss memory reindex` + drift check (hash manifest over mirror files vs index, `--check` mode mirroring V20's sync gate) so hand-edited memory files re-enter the index instead of silently diverging.
- **Pinned tier:** small always-inject tier (deterministic, capped) for must-never-miss memories; everything else competes via recall — froots' core-files split, done as a flag on existing rows not separate files.

**Out of scope:** graph visualization of memory (derived view over the flat store — voss-app/TUI seed if wanted, store stays flat per froots' own "graph is the picture" framing); embedding-model swap (BGE/libsql/DiskANN — chroma works, V19 gotchas already paid); cloud sync / multi-device (PROJECT.md exclusion stands); supersession edges between memories (telemetry first, supersession is a later seed); auto-pinning heuristics (manual pin verb only).

**Requirements:** VRNK-* (SPEC pending — V-track phase, requirements live in `V23-SPEC.md` not REQUIREMENTS.md).

**Origin:** froots.ai/memory teardown (2026-06-12) — their schema admits retrieval metadata + score floor matter; neither product ships the ranking loop yet. Depends on: V19 (shipped — recall surface + manifest patterns). Coordinate with V21 (telemetry/floor/pinning must apply per-store once the global store lands; dual-store RRF already merges per-source).

**Plans:** 8 plans · 7 waves. memory_store.py is serialized across waves 1-5 (single-file ownership rule); W5 runs V23-06 ∥ V23-07 (disjoint files). W0 RED scaffold → W1 telemetry → W2 floors → W3 rescore → W4 eviction+reindex → W5 pinned tier ∥ CLI verbs → W6 regression lock.

Plans:
- [ ] V23-01-PLAN.md — W0 RED scaffold: tests/memory/test_retrieval_ranking.py + conftest bridge [VRNK-01..08]
- [ ] V23-02-PLAN.md — W1 Retrieval telemetry sidecar (.retrieval.jsonl) + agent-path record point + vacuum compaction [VRNK-01]
- [ ] V23-03-PLAN.md — W2 Pre-fusion quality floors (chroma 0.25 abs, BM25 0.1 rel-to-top), default-on [VRNK-02]
- [ ] V23-04-PLAN.md — W3 Recency×frequency rescore on RRF output (default-off, byte-identical off-path) [VRNK-03]
- [ ] V23-05-PLAN.md — W4 Retrieval-aware eviction + pin primitives + `voss memory reindex` drift gate [VRNK-04, VRNK-05]
- [ ] V23-06-PLAN.md — W5 Pinned tier: V18-region non-evictable injection, token caps, overflow warn [VRNK-06]
- [ ] V23-07-PLAN.md — W5 CLI verbs: pin/unpin/list/show/reindex (telemetry + pin columns, --global) [VRNK-07]
- [ ] V23-08-PLAN.md — W6 Regression + coherence guard: full suites green, byte-identical lock, no schema drift [VRNK-08]

### Phase V24: ADE Product Revamp + Swarm Observability

**Goal:** Reframe `apps/voss-app` into a product-coherent ADE for Ben first and developer teams later: a terminal workbench the user can run manually, an agent mission-control layer for managed Voss work, and a review/observability system that makes agent activity understandable. The revamp must preserve Warp-style terminal pane functionality, multiple terminals, command palette/grid operations, project-less use, and user-owned terminal workflows. Voss should be the operating layer around the work, not a requirement imposed on every pane.

**Product thesis:** Terminals are where work runs. Voss is where agent work becomes scoped, observable, reviewable, and trustworthy.

**Scope:**
- **Product context + design contract:** write the missing product/design context for the ADE surface before code. Default register = product; primary user = Ben; future audience = developer teams licensing controlled agent work. Success means a fluent developer can understand what Voss does without learning internal labels first.
- **Information architecture reset:** replace top-level implementation chrome with a left portal: Overview, Runs, Agents, Swarm Map, Review, Context, Memory, Settings. The portal is the navigation model; the terminal grid remains the canvas.
- **Quiet top chrome:** keep project/window identity, command palette/status, and mode indicators only. Demote `fanout/pipeline/swarm/watchers` to a layout menu or pane toolbar; they are layout presets, not product navigation.
- **Humane run intake:** replace the exposed `Plan/Edit/Auto`, `Voss run`, `Terminal agent`, and budget/scope clutter with a progressive composer: "Ask Voss to..." plus advanced controls for safety mode (`Read only`, `Can edit`, `Autopilot`), scope, agent target, team, budget, and attached context.
- **Terminal-first preservation:** opening/splitting/focusing terminals, running arbitrary commands, launching custom CLI agents, project-less workflows, and session persistence must continue to work without Voss credentials or Voss interpretation.
- **Run/agent mission control:** Overview/Runs/Agents surfaces show active, blocked, reviewing, done, adopted, and terminal-agent work with clear statuses and attention actions. It should feel closer to Linear for agent work than a toolbar of raw run controls.
- **Swarm Map / Run Graph:** add an observability surface over runs. Center node = objective/run; agent nodes = Voss/Codex/Claude/reviewer/tester/etc.; work nodes = board cards/tasks; artifact nodes = files/diffs/tests/PRs/decisions; alert nodes = permissions, failed tests, budget/scope gates. Animated edges show delegation, messages, tool calls, file edits, review, validation, and blockers. Clicking nodes deep-links to panes, drawers, diffs, permission actions, or session nodes.
- **Replay + audit mode:** completed runs can be replayed through the graph timeline so the user/team can see how work moved between agents, tools, files, and review. This is a trust/audit feature, not decorative motion.

**Out of scope:** replacing the terminal grid with an IDE/editor; mandatory Voss wrapping for all panes; cloud/team admin product surfaces; billing/licensing UI; generic observability SaaS dashboards; decorative-only graph animation; changing harness orchestration semantics; adding new agent protocols beyond existing `voss serve`, SDK/SSE, PTY registry, board/session/audit data, and later V17 bus events.

**Requirements:** VADE2-01..11 (V-track phase, requirements live in `V24-SPEC.md` not REQUIREMENTS.md).

**Origin:** 2026-06-14 ADE design discussion. Current screenshot/problem: the app exposes layout presets, internal modes, target plumbing, and snapshot/review labels before the user understands what Voss delivers. Market signal: Warp separates terminal and agent contexts and manages multi-agent work through vertical tabs/notifications/review; Codex/Devin frame agent work as a command center; agent observability tools expose graphs/traces/cost/tool calls. Voss differentiator: terminal-first control plane with memory, scope, budget, review, audit, and visible swarm coordination.

**Depends on:** V14 for cockpit components and selection model; V15 for live sidecar/SSE/protocol panes; A1-A13 for terminal grid and swarm substrate. **Consumes when available:** V17 coordination bus/claims for graph edges and agent-to-agent messages; V20 residue hardening for mission briefs and critical-risk gates; V9 audit artifacts for replay and review trust.

**Cross-cutting constraints:**
- L1 terminal credibility is non-negotiable: a user can ignore Voss and still use the app as a terminal.
- The Swarm Map must render from real events/artifacts. If a signal is not available, show an honest placeholder or omit it; never fake agent communication.
- Motion must communicate live state, flow, or replay. Respect reduced-motion and provide a static trace/list fallback.
- Keep app state boundaries intact: Solid owns UI state; Tauri/Rust owns process/filesystem lifecycle; Python harness remains the orchestration source of truth.
- No hidden writes to `.voss/` on project open. Durable project writes remain lazy and intentional.

**Plans:** 11 plans, 9 waves (W0-W8). Wave assignment is dependency-resolved by single-file ownership: App.tsx serializes V24-02 (W1) → V24-03 (W2) → V24-04 (W3); PortalShell.tsx serializes V24-02 (W1) → V24-05 (W2) → V24-06 (W3) → V24-10 (W7); swarmMap.css/SwarmMap.tsx serializes V24-06 (W3) → V24-07 (W4). W0=V24-01 (contract); W1=V24-02 (portal+canvas-swap); W2=V24-03 (quiet chrome) ∥ V24-05 (mission control); W3=V24-04 (composer) ∥ V24-06 (Swarm Map static); W4=V24-07 (live+replay); W5=V24-08 (validation, has human checkpoint); W6=V24-09 (collapsible PortalRail); W7=V24-10 (Context/Settings/Memory surface wiring — closes SPEC §41/86/91 gap); W8=V24-11 (Memory server route + live surface). **V24-09/10 added 2026-06-16:** 08 shipped 8 plans but the rail UX (09) and three SPEC-required surface wirings (10, originally stubbed as placeholders in 02) were outstanding.

Plans:
- [x] V24-01-PLAN.md — W0 product/design contract: PRODUCT.md/DESIGN.md or ADE-specific UI-SPEC, IA decisions, copy vocabulary, success criteria [VADE2-01]
- [x] V24-02-PLAN.md — W1 left portal shell + canvas-swap route/state model: Overview/Tasks/Agents/Swarm Map/Review/Context/Memory/Settings, grid stays mounted (PortalView contract authored here) [VADE2-02]
- [x] V24-03-PLAN.md — W1 quiet top chrome + layout control demotion: project/status/palette only; fanout/pipeline/swarm/watchers moved to layout menu/pane controls [VADE2-03]
- [x] V24-04-PLAN.md — W2 humane run intake: progressive "Ask Voss to..." composer, safety-mode labels, scope/agent/budget/context advanced controls, no raw internal labels by default [VADE2-04]
- [x] V24-05-PLAN.md — W2 mission-control Overview/Tasks/Agents surfaces: active/blocked/reviewing/done/adopted/terminal-agent rows, attention actions, pane/drawer deep links [VADE2-05]
- [x] V24-06-PLAN.md — W3 Swarm Map static model: derive nodes/edges from RunData, board/session tree, registry, budget/context, audit/review artifacts; honest missing-signal handling [VADE2-06]
- [x] V24-07-PLAN.md — W4 Live Swarm Map + replay: SSE/registry edge updates, subtle animated connectors, reduced-motion fallback, timeline scrubber for completed runs [VADE2-07]
- [x] V24-08-PLAN.md — W5 validation: terminal-grid regression, cockpit/deep-link tests, visual screenshot checks, a11y/reduced-motion, no fake-signal guard, focused Tauri/Rust/TS verification [VADE2-08]
- [x] V24-09-PLAN.md — W6 collapsible Workspaces-first PortalRail: lucide-solid icons, persisted expand state, Workspaces routes to grid canvas (canvas-swap) [VADE2-09]
- [x] V24-10-PLAN.md — W7 close SPEC §41/86/91 gap: wire Context (reuse ContextPanel), Settings (appearance store), Memory (honest harness-backed state) surfaces; delete the "Coming in a later V24 plan" placeholder [VADE2-10]
- [x] V24-11-PLAN.md — W8 Memory server route + live surface: bearer-authed read-only `GET /memory` (MemoryStore summary+recall) + regen contract; MemorySurface fetches live data with honest no-server fallback [VADE2-11]

---

### Phase V25: Server-Native Swarm Runtime (supersedes A13 transport)

> **⊘ Supersedes A13's filesystem-as-IPC transport.** A13 (and the external BridgeSwarm design it mirrors) coordinated agents through `.voss/swarm/` files + fs-watch because no daemon mediated them. Voss now ships the harness server + sidecar + SSE bus, so V25 re-bases swarm coordination on **server + SSE**. A13-01 (shipped) file schema is retained as V25's git-diffable **audit layer**; A13-02..06 (file-bus decompose/spawn/result-watch/sidebar/persist) are superseded.

**Goal:** N role-typed agents (coordinator/builder/reviewer; scout folded into chroma) coordinate as harness `ServerSession`s through the existing FastAPI server + SSE event bus, with a `SwarmStore` as the single server-side source of truth. The filesystem (`.voss/swarm/<id>/events/*.jsonl`) is an append-only audit/replay mirror, never the runtime transport.

**Why now:** Voss already owns every primitive BridgeSwarm/A13 built from scratch — multiplexed sessions (`POST /session/{id}/message`), SSE push (`GET /session/{id}/events`), semantic memory (`MemoryStore.recall`), write-scope enforcement (`PermissionGate.check`, deny-wins `.voss/permissions.yml` layer), grid panes + per-pane `agent_registry`, and a multi-provider model router. V25 is wiring over them, not new infrastructure. This deletes the nudge.txt/stdin-injection/PATH-bash-CLI/per-OS-process hacks the file-bus required.

**Scope:**
- **SwarmStore + transport (foundation):** new harness module `swarm_store.py` (sibling to `session_store`/`memory_store`). `Swarm{scopeId, goal, roster[Role], tasks[Task]}` held server-side; mirrored append-only to `.voss/swarm/<id>/events/*.jsonl` for git-diff/replay. Task lifecycle `open→assigned→building→review→done` (+`blocked`,`cancelled`); fields `ownedFiles`/`acceptanceCriteria`/`dependsOn`/`owner`/`notes`. New SSE event types on the existing bus: `swarm.assign`/`worker_done`/`gate`/`needs_operator`/`complete`. Endpoints `POST /swarm`, `GET /swarm/{id}`, `POST /swarm/{id}/task`, `POST /swarm/{id}/message`.
- **Spawn-gating (no race):** builder sessions created in `waiting` state, unblocked only on coordinator `swarm.assign`. Replaces BridgeSwarm's "coordinator first, builders +2s, poll 60s" sleep/poll race with a deterministic server gate.
- **Server-enforced ownership:** per-session swarm policy injected into `PermissionGate` denies `fs_write`/`fs_edit` outside the task's `ownedFiles` (reuse the existing project-policy deny-wins layer; writes already funnel through `PermissionGate.check`). SwarmStore rejects overlapping `ownedFiles` at task-create unless sequenced via `dependsOn`. Turns the file-ownership honor-system into a real lock.
- **Memory-shared context:** per agent turn, auto-inject `MemoryStore.recall(query, scope=task.ownedFiles)`. Scout role folds into chroma (optional index-warmer only, not a default roster member).
- **Grid topology binding:** swarm spawn applies a layout preset (`layouts.rs`); panes bound to sessions via `agent_registry` (+`swarm_id`/`role`/`owned_files` columns). Coordinator pane top, builders tiled below (Warp locked tiling). Feeds V24's Swarm Map.
- **Per-role model routing:** each `Role` carries a model resolved through the existing `_resolve_provider`/router (e.g. coordinator=Opus, builders=cheaper/Codex, reviewer=third).
- **Operator + decisions:** `needs_input` reuses the permission-gate UI; `@operator` is a first-class roster member. Gate decisions (approve/reject/conflict) write `.voss/decisions/*.md` with `confidence`+`related_session`.

**Out of scope:** nudge.txt / stdin-injection wakeups; PATH-injected `bs-*` bash CLIs; per-agent OS process or per-agent `CLAUDE_CONFIG_DIR`; the filesystem as runtime transport (audit-only); scout as a default standalone agent; the V24 Swarm Map UI itself (V25 emits the live plane it renders); changing V3/V5/V7 cage semantics (V25 is CLI-agent-pane swarm runtime, distinct from the autonomous-org board/EM loop — they may converge later but not here).

**Requirements:** VSWARM-01..11 (locked in `V25-SPEC.md`). **Plans:** 6 plans, 4 waves (planned 2026-06-17).

Plans:
- [ ] V25-01-PLAN.md — SwarmStore + append-only JSONL event log + overlap validation + session index + ownership-policy builder + scoped-recall helper + role-prompt templates
- [ ] V25-02-PLAN.md — 5 swarm SSE event types + ServerSession gate_event/swarm fields
- [ ] V25-03-PLAN.md — agent_registry.rs swarm_id/role/owned_files columns + list_agents_by_swarm (cargo-tested)
- [ ] V25-04-PLAN.md — /swarm routes + app-scoped SwarmStore + spawn-gate wiring + per-role model routing + fan-out emit
- [ ] V25-05-PLAN.md — ownership deny at PermissionGate + swarm.needs_operator escalation + scoped-recall injection + decision .md recording
- [ ] V25-06-PLAN.md — 2-builder enforced end-to-end integration test (SPEC acceptance bar)

**Relationship to existing tracks:** supersedes **A13** transport (file-bus → server+SSE); pairs with **V24** as runtime↔observability (V25 emits, V24 renders the Swarm Map); reuses **V3** model-tiering/scope concepts and **V15** live-plane sidecar handshake; distinct from the **V5/V7** autonomous-org cage (different surface: human-launched CLI-agent panes vs. EM-routed LLM roster).

**Depends on:** harness server + `PermissionGate` + `MemoryStore` + `agent_registry` (shipped); **V15** live-plane sidecar/SSE for the webview-facing wiring. **Consumed by:** V24 Swarm Map.

**Concurrency note:** the harness is single-process asyncio — N agents = N interleaving `session.task`s in one shared sidecar. Write collisions are prevented **by construction** via disjoint `ownedFiles` + the PermissionGate deny, not by file locks. SwarmStore overlap-validation at task-create is the belt-and-suspenders.

**Origin:** 2026-06-16 BridgeSwarm architecture teardown — recognized A13 as the same filesystem-as-IPC design and reframed the swarm around Voss's now-existing daemon.

**Plans:** TBD by SPEC. Suggested waves: (1) SwarmStore + SSE + spawn-gate foundation; (2) grid binding ∥ per-role routing; (3) memory injection ∥ ownership gate; (4) operator + decisions.

---

## E-prefixed phases: Internal Proof Suite (E2E + Evals)

E1–E5 prove the **product** works — model + functionality end-to-end — not just that unit tests pass. Motivated by false-green history (scaffold tests passing without real behavior, stale sentinels). **Internal-only, on-demand**: never shipped, no packaging, no public docs; runs ride **subscription-backed flagship models via existing voss auth** (`--auth=codex` etc.; Ollama optional fallback) at $0 marginal spend with a per-run budget/turn cap. Scoring is **hybrid**: deterministic gates (tests pass in target repo, diff applies, exit code) decide pass/fail; LLM-judge scores quality on top. The matrix is **runtime surfaces** (CLI, server plane, SDK, TUI, voss-app) × **target repo shapes** (Python, Rust, TS). Supersedes M5's eval scope (EVAL-01..05 → E1/E2; M5-06 packaging smoke already shipped). If E-track becomes an engineering-team workflow, add LangSmith only as an optional export/trace adapter for shared dashboards, annotation, and evaluator calibration; local JSONL/summary artifacts stay canonical. Each phase locks requirements in its own `E{n}-SPEC.md` (V-track mechanism). Full decision log: `.planning/notes/e-track-eval-decisions.md`.

**Build order:** E1 → E2 → E3/E4 (parallel-ok) → E5. E1 is the substrate everything else consumes; V18-05's packing-on-vs-off quality gate consumes E1 instead of M5.

### Phase E1: Eval Substrate

**Goal:** The runnable core every other E-phase consumes — define a task, run it against a real subscription-backed model, score it hybrid, record results.

**Scope:**
- Suite loader + TaskSpec (pydantic) + fixture isolation (absorbs M5-01 ground).
- Runner: on-demand entrypoint (make target / internal dev verb — not a shipped CLI surface), per-run budget/turn cap so a suite run can't eat weekly sub limits.
- Model wiring through existing voss auth resolution (codex OAuth, /models routing); honors known backend quirks.
- Hybrid scoring: deterministic gate predicates + judge_run LLM-judge layer (absorbs M5-02).
- Results: JSONL per run + summary.md (success rate, mean cost, confidence correlation — absorbs M5-03/04).

**Out of scope:** CI integration, scheduled runs, public `voss eval` surface, live dashboards.
LangSmith/team dashboards are a likely later adapter if this becomes multi-user, but E1 must not depend on them.

**Requirements:** EVSUB-01..07 (locked in `E1-SPEC.md`; absorbs EVAL-01..04 intent).

**Cross-cutting:** Seed material = M5-01..04 plans + existing `tests/eval/`. Open questions for spec/discuss: budget-cap defaults, judge model routing (same sub? same model as actor?), relationship to existing `tests/e2e/` pytest layer.

**Plans:** 5 plans · 4 waves
- [ ] E1-01-PLAN.md — Deterministic checks schema (AnyCheck union) + _run_checks executor (EVSUB-01)
- [ ] E1-02-PLAN.md — [eval] config section + VOSS_DEV dev gate + --max-turns flag (EVSUB-05)
- [ ] E1-03-PLAN.md — Hybrid gate/judge plumbing + turn cap + judge-model split + summary columns (EVSUB-02/04/06)
- [ ] E1-04-PLAN.md — Retrofit deterministic checks onto all 6 golden tasks (EVSUB-03)
- [ ] E1-05-PLAN.md — Live full-suite proof run on codex auth, ≥5/6 gate_pass (EVSUB-07)

### Phase E2: Golden Tasks × Repo Matrix

**Goal:** Golden agentic tasks (analyze, plan-only, approved edit, validation, resume) run against fixture repos in Python, Rust, and TS — proving cognition + edits across project shapes.

**Requirements:** EVGLD-01 (synthetic-minimal py/rust/ts fixtures + matrix suite loads), EVGLD-02 (curated 12-cell matrix task.tomls with per-language checks), EVGLD-03 (per-language behavioral gates: toolchain test exit 0 + edit-landed), EVGLD-04 (cognition gates: analyze names lang-correct manifest), EVGLD-05 (toolchain require-present + recorded-skip + preflight + `--require-all-toolchains`), EVGLD-06 (summary.md skipped column, never silent-green), EVGLD-07 (matrix stub-run green + manual live-proof, gated after E1-05). *Minted from CONTEXT D-01..D-04 by E2 planning; absorbs M5-05 / EVAL-05 intent. To be adopted by a future E2-SPEC.md.*

**Plans:** 9 plans, 4 waves (W1 fixtures parallel per language; W2 task.tomls + runner infra parallel; no TaskSpec schema change — language carried by the task_id prefix)

Plans:
- [ ] E2-01-PLAN.md — RED test scaffolds: 4 matrix test files, one Nyquist selector per EVGLD-* (strict-xfail runner + skip-guarded suite/stub) [EVGLD-01..07]
- [ ] E2-02-PLAN.md — Python fixtures: 3 flat calc shape repos (py-01/03/04) + 3 golden-reuse fixtures (py-02/05/06) [EVGLD-01]
- [ ] E2-03-PLAN.md — Rust fixtures: 3 self-contained calc crates (rust-01/03/04), no [workspace], integration-test call site [EVGLD-01]
- [ ] E2-04-PLAN.md — TypeScript fixtures: 3 ESM calc projects (ts-01/03/04), node:test no-install, no global tsc [EVGLD-01]
- [ ] E2-05-PLAN.md — Python task.tomls: 3 shape cells (cognition+behavioral) + 3 reuse cells [EVGLD-02, EVGLD-03, EVGLD-04]
- [ ] E2-06-PLAN.md — Rust task.tomls: 3 shape cells, cargo test timeout=120, both-file rename [EVGLD-02, EVGLD-03, EVGLD-04]
- [ ] E2-07-PLAN.md — TypeScript task.tomls: 3 shape cells, npm test, camelCase sumTwo rename [EVGLD-02, EVGLD-03, EVGLD-04]
- [ ] E2-08-PLAN.md — runner toolchain preflight + skip-row (gate_pass=None) + `--require-all-toolchains` + summary skipped column [EVGLD-05, EVGLD-06]
- [ ] E2-09-PLAN.md — full 12-cell matrix stub-run green + manual live-proof checkpoint (gated after E1-05) [EVGLD-07]

### Phase E3: Surface E2E

**Goal:** Each runtime entry point — CLI verbs, server plane (serve/SSE/permission gates) — driven end-to-end with real model inference and hybrid-scored.

**Requirements:** EVSRF-01 (surface field + per-surface dispatch), EVSRF-02 (CLI subprocess drivers, live-auth, no stub injection), EVSRF-03 (serve spawn+handshake+SSE+events), EVSRF-04 (permission Allow/Deny flow), EVSRF-05 (surfaces suite scenarios), EVSRF-06 (live proof run on codex auth, human checkpoint).

**Plans:** 4 plans, 4 waves (file-overlap on runner.py serializes the driver plans)

Plans:
- [ ] E3-01-PLAN.md — surface/target_file fields on TaskSpec + additive JSONL surface field + sentinel + dispatch skeleton (E1-merge gate) [EVSRF-01]
- [ ] E3-02-PLAN.md — cli:do/cli:chat/cli:edit subprocess drivers (live auth, no stub injection) + stub tests [EVSRF-02]
- [ ] E3-03-PLAN.md — serve HTTP/SSE driver + permission Allow/Deny + FAKE_TURN integration + parser unit tests [EVSRF-03, EVSRF-04]
- [ ] E3-04-PLAN.md — 6 surface scenarios + suite-load/dispatch test + live proof checkpoint on codex auth [EVSRF-05, EVSRF-06]

### Phase E4: SDK Proof

**Goal:** The four public SDK surfaces — `sdk:python` (in-process `voss.harness`/`voss_runtime` embedder), `sdk:ts`, `sdk:go`, `sdk:rust` (client SDKs against live `voss serve`) — exercised as real external consumers driving live model runs, hybrid-scored through the E1 substrate. The external-consumer contract (spawn → session → typed SSE → permission gate → final → read) proven, not just type-checked.

**Requirements:** EVSDK-01 (surface dispatch — `sdk:*` Literal + `_drive_sdk_client`/`_drive_sdk_python`), EVSDK-02 (`sdk:python` in-process driver, public API), EVSDK-03 (`sdk:ts` consumer subprogram), EVSDK-04 (`sdk:go` consumer subprogram), EVSDK-05 (`sdk:rust` consumer subprogram), EVSDK-06 (sdk task.tomls + suite wiring + single-substrate scoring), EVSDK-07 (permission-gate live scenario per client), EVSDK-08 (live proof run on codex auth, human checkpoint). *Minted from CONTEXT D-01..D-08 — no SPEC; see `E4-01-PLAN.md`.*

**Plans:** 7 plans, 5 waves (E3-01 dependency satisfied — extends the executed `surface` Literal additively; W3 consumer plans parallelize on separate dirs)

Plans:
- [x] E4-01-PLAN.md — RED Nyquist scaffold + three consumer subprograms build (ts/go/rust; resolve go.mod/TS-import/rust-example open Qs) [EVSDK-01..05] ✓ 2026-06-12
- [x] E4-02-PLAN.md — extend surface Literal with sdk:* + _drive_sdk_python (in-process) + _drive_sdk_client (serve+consumer) dispatch [EVSDK-01, EVSDK-02] ✓ 2026-06-12
- [x] E4-03-PLAN.md — harden ts consumer (typed SSE decode, env-driven reply, six-key JSON) [EVSDK-03] ✓ 2026-06-12
- [x] E4-04-PLAN.md — harden go consumer (AttachClient, typed channel type-switch, json.Marshal) [EVSDK-04] ✓ 2026-06-12
- [x] E4-05-PLAN.md — harden rust consumer (VossClient::new, AgentEvent stream match, auto-discovered example) [EVSDK-05] ✓ 2026-06-12
- [x] E4-06-PLAN.md — four sdk task.tomls + shape-agnostic fixture + suite wiring + three consumer end-to-end FAKE_TURN schema tests [EVSDK-03..06] ✓ 2026-06-12
- [ ] E4-07-PLAN.md — ts Deny variant + permission_choice forwarding + live proof run on codex auth (human checkpoint) [EVSDK-07, EVSDK-08]

### Phase E5: TUI + voss-app Autonomous Driving

**Goal:** The interactive surfaces (Textual TUI, voss-app desktop) driven autonomously end-to-end. Hardest phase: Tauri WebDriver is impossible on macOS (A2 finding) — approach (e.g. protocol-level driving, accessibility tree, screenshot judge) decided at spec time.

**Requirements:** EVUI-01..0N (TBD by `E5-SPEC.md`).

**Plans:** TBD

---

## Coverage

| Phase | Requirements | Count |
|---|---|---:|
| BOS1 | BOS-PROD-01..04, BOS-PLAN-01..04 | 8 |
| BOS2 | BOS-ARCH-01..04, BOS-PROD-04 | 5 |
| BOS3 | BOS-DATA-01, BOS-DATA-06, BOS-DATA-07 | 3 |
| BOS4 | BOS-DATA-02 | 1 |
| BOS5 | BOS-DATA-03..05 | 3 |
| BOS6 | BOS-GOV-01..04 | 4 |
| BOS7 | BOS-PROD-04, BOS-SWARM-04, BOS-WORK-03 | 3 |
| BOS8 | BOS-WORK-01..03 | 3 |
| BOS9 | BOS-POL-01..03, BOS-REC-01..03, BOS-BEH-01..03 | 9 |
| BOS10 | BOS-SWARM-01..04 | 4 |
| BOS11 | BOS-INT-01, BOS-INT-03 | 2 |
| BOS12 | BOS-INT-02 | 1 |
| BOS13 | BOS-DATA-05, BOS-POL-03, BOS-RL-02 | 3 |
| BOS14 | BOS-RL-01..03 | 3 |
| BOS15 | BOS-POL-03, BOS-REC-02 | 2 |
| BOS16 | BOS-PROD-04, BOS-SWARM-04 | 2 |
| BOS17 | BOS-PM-01..03 | 3 |
| BOS18 | BOS-PM-01..03 | 3 |
| M0 | SCOPE-01..04 | 4 |
| M1 | CLIH-01..10, CTRL-01..09 | 19 |
| M2 | COG-01..08 | 8 |
| M3 | LANG-01..10 | 10 |
| M4 | DOG-01..08 | 8 |
| M5 | EVAL-01..05 | 5 |
| M6 | NPM-01..05 | 5 |
| M7 | SDK-01..05 | 5 |
| **v0.1 Total** |  | **64 / 64** |
| M8 | MEM-01..07 | 7 |
| M9 | TUI-01..10 | 10 |
| M10 | CODE-01..07 | 7 |
| M11 | VTOOL-01..05 | 5 |
| M12 | MCP-01..0N | TBD by `M12-SPEC.md` |
| M13 | MAG-01..MAG-08 | 8 |
| M14 | WATCH-01..0N | TBD by `M14-SPEC.md` |
| M15 | SKILL-01..06 | 6 |
| **T-phases (daily-driver gap closure)** | | |
| T6 (v0.1.1 patch) | SLASH-01..07 | 7 (Complete) |
| T1 | ITER-01..06 | 6 |
| T4 | CACHE-01..04 | 4 |
| T2 | PAR-01..04 | 4 |
| T3 | NET-01..07 | 7 |
| T5 | SHELL-01..05 | 5 |
| T7 | SKL-01..06 | 6 |
| T8 | INPUT-01..05 | 5 |
| **T-total** | | **42** |
| **A-phases (voss-app desktop ADE Layer 1)** | | |
| A1 | SHL-01..0N | TBD by `A1-SPEC.md` |
| A2 | PTY-01..0N | TBD by `A2-SPEC.md` |z 
| A3 | GRD-01..0N | TBD by `A3-SPEC.md` |
| A4 | LAY-01..0N | TBD by `A4-SPEC.md` |
| A5 | WS-01..0N | TBD by `A5-SPEC.md` |
| A6 | PER-01..0N | TBD by `A6-SPEC.md` |
| A7 | CMD-01..0N | TBD by `A7-SPEC.md` |
| A8 | UXP-01..0N | TBD by `A8-SPEC.md` |
| A9 | CFG-01..0N | TBD by `A9-SPEC.md` |
| A10 | BAR-01..0N | TBD by `A10-SPEC.md` |
| A11 | OBD-01..0N + REL-01..0N | TBD by `A11-SPEC.md` |
| A12 | ADE-01..08 | 8 plans (P1–P8) |
| **A-total (Layer 1)** | | **TBD per SPEC** |
| **O-phases (ADE orchestration — Caged Autonomous Eng Team)** | | |
| O1 | OST-01..0N | TBD by `O1-SPEC.md` |
| O2 | OTEAM-01..0N | TBD by `O2-SPEC.md` |
| O3 | OBRD-01..0N | TBD by `O3-SPEC.md` |
| O4 | ORVW-01..0N | TBD by `O4-SPEC.md` |
| O5 | OEM-01..0N | TBD by `O5-SPEC.md` |
| O6 | OAUD-01..08 | 8 |
| **O-total** | | **TBD per SPEC** |
| **F-phases (substrate features — v1 Layer 2)** | | |
| F1 | FPRS-01..05 | 5 |
| F2 | FSRCH-01..04 | 4 |
| F3 | FVIZ-01..0N | TBD by `F3-SPEC.md` |
| F4 | FCTX-01..0N | TBD by `F4-SPEC.md` |
| F5 | D-01..D-16 | 2 |
| F6 | FCNCL-01..0N | TBD by `F6-SPEC.md` |
| **F-total** | | **TBD per SPEC** |

All v0.2 BOS implementation requirements are mapped to BOS1-BOS18. All v0.1 requirements mapped. Older v0.2 M-track requirement IDs are minted by `/gsd-spec-phase` per phase. T-phase requirement IDs locked in this roadmap; full SPEC pending per-phase `/gsd-spec-phase`. A-phase requirement IDs are placeholder prefixes; per-phase SPEC locks the count + exact text.

---

## v0.2 Candidate Phases

Identified but **not committed to a milestone**. Each lands when its trigger
condition fires — usually real-user demand surfacing during v0.1 dogfood.

> **Note:** M7 (SDK Polish) was originally listed here as a v0.2 candidate
> on 2026-05-12; it was promoted to a formal v0.1 phase on 2026-05-13. See
> "Phase M7: SDK Polish" above.

### Other v0.2 candidates (not yet phased)

- **DIST-01** Rust harness shell — trigger: bundled-Python (M6) startup
  latency or wheel size proves painful in real use.
- **DIST-02** Homebrew distribution — trigger: macOS install friction
  surfaces despite npm wrapper.
- **DIST-03** MCP bridge — **RETIRED 2026-05-14.** Promoted to formal phase
  **M12 MCP Bridge (CAPS-01c)** — see "Phase M12" above.
- **EDIT-01/02** Tree-sitter + VSCode marketplace — trigger: language users
  ask for editor support beyond the existing scratch extension.
- **LING-01** GitHub Linguist upstream PR — trigger: enough public `.voss`
  code exists for syntax recognition to matter.
- **JS-SDK** TS/JS library — trigger: real JS-side embedders ask for a
  library API (not just `npx voss`).
- **TEAM-*** / **WEB-*** — far post-v0.1.

### Coding-agent v0.2 phases *(planted 2026-05-14 via /gsd-explore, promoted to formal phases same day)*

The three CAPS/TUI/MEM seeds were promoted to formal phases on 2026-05-14.
After `M10-SPEC.md` scope-cut M10 to codebase intelligence only, the other
five capabilities from the original CAPS-01 seed were also promoted to
formal follow-on phases M11–M15. Seed files remain in `.planning/seeds/`
as the source brainstorm; the thesis note remains in `.planning/notes/`
as cross-phase context.

- **MEM-01 → M8 Project Memory** — see
  [`seeds/project-memory-voss-md.md`](seeds/project-memory-voss-md.md).
- **TUI-01 → M9 TUI Shell** — see
  [`seeds/tui-shell-textual.md`](seeds/tui-shell-textual.md).
- **CAPS-01 → M10–M15** — see
  [`seeds/agent-capability-surface.md`](seeds/agent-capability-surface.md).
  Originally one bundled phase; split during M10-SPEC into:
  - **M10 Codebase Intelligence (CAPS-01a)** — locked SPEC, ready to discuss.
  - **M11 Voss-aware Tools (CAPS-01b)** — scaffolded, no SPEC yet.
  - **M12 MCP Bridge (CAPS-01c)** — scaffolded, no SPEC yet; subsumes retired DIST-03.
  - **M13 Multi-agent in Chat (CAPS-01d)** — scaffolded, no SPEC yet.
  - **M14 Long-running Tasks + Watch (CAPS-01e)** — scaffolded, no SPEC yet.
  - **M15 Skill / Plugin Marketplace (CAPS-01f)** — scaffolded, no SPEC yet.
- **Thesis note** (not a phase) — Voss agent unfair advantage. See
  [`notes/voss-agent-unfair-advantage.md`](notes/voss-agent-unfair-advantage.md).
  Re-read before scoping M8 / M9 / M10–M15.

These do NOT block v0.1 ship. Listed so the roadmap has a memory of what's
next without forcing premature commitment.


## F-prefixed phases: Substrate Features (v1 Layer 2)

F-phases add Layer 2 features to the voss-app ADE — Voss integration,
semantic search, budget visualization, and multi-model capabilities.
They depend on the A-phase Layer 1 terminal-grid substrate being in place.

### Phase F1: Durable Session Persistence

**Goal:** When the ADE quits with active Voss agent panes, relaunching the app auto-restarts those agent subprocesses in the correct panes with the correct session IDs, cwd, and CLI arguments — without user intervention.

**Requirements:** FPRS-01..05 (5 locked in `F1-SPEC.md`)

**Plans:** 3 plans, 2 waves

Plans:
- [ ] F1-01-PLAN.md — Rust agent_registry.rs + spawn_command_session + Tauri command wrappers
- [ ] F1-02-PLAN.md — Frontend agentConfig prop plumbing + command palette + gitignore
- [ ] F1-03-PLAN.md — Boot restore orchestration + quit lifecycle + orphan sweep + verification

**Success Criteria:**
1. Quit app with 2 agent panes + 1 shell pane -> relaunch -> agents restart, shell stays shell
2. Agent exit marks registry row as stopped
3. Clean quit updates last_seen on all active rows
4. Orphaned registry rows cleaned on boot
5. No regression in A6 session geometry restore

**Cross-cutting:** Builds on A6 session persistence (geometry) + A2 PTY subsystem + A7 command palette. Does NOT modify PaneLeaf/GridState/session.json schema — registry is the sole source of truth for agent metadata.

---

### Phase F2: Hybrid Semantic Search

**Goal:** Improve harness memory recall by replacing naive keyword scan with symbol-aware BM25 and fusing BM25 with optional Chroma vector recall via Reciprocal Rank Fusion.

**Requirements:** FSRCH-01..04 (locked in `F2-CONTEXT.md`)

**Plans:** 3 plans, 3 waves

Plans:
- [ ] F2-01-PLAN.md — symbol-aware BM25 tokenizer, corpus builder, and BM25-only recall fallback
- [ ] F2-02-PLAN.md — hybrid BM25 + Chroma recall using RRF with BM25 degradation on Chroma failure
- [ ] F2-03-PLAN.md — base `rank-bm25` dependency placement, lock validation, and targeted recall regressions

**Success Criteria:**
1. Chroma-unavailable recall uses BM25 and never crashes.
2. Chroma-available recall merges BM25 and vector results with RRF k=60.
3. Source and tombstone filtering apply to both lexical and vector results.
4. Symbol-heavy terms like `getUserById` and `parse_config_file` are tokenized consistently in corpus and query.
5. Base installs include BM25 without requiring heavyweight vector-search extras.

**Cross-cutting:** Scope is limited to `MemoryStore.recall()` and its tests. Code search remains out of scope for F2 and belongs to the M10/code-search track.


---

### Phase F3: Budget & Token Visualization

**Goal:** Live HUD in voss-app showing token budget consumption and cost accumulation for agent panes. Budget/cost data flows from the Voss harness process (running inside a PTY pane) to the ADE UI via custom OSC escape sequences in the PTY stream.

**Requirements:** D-01..D-14 (locked in `F3-CONTEXT.md`)

**Plans:** 3 plans, 3 waves

Plans:
- [x] F3-01-PLAN.md — Rust OSC parser + BudgetData/BudgetUpdate + Python _emit_budget_osc + agent.py wiring
- [x] F3-02-PLAN.md — Frontend transport extension + Popover + BudgetBar + BudgetPopover components
- [x] F3-03-PLAN.md — PaneComponent integration + CSS transition + closeout verification

**Success Criteria:**
1. Python harness emits OSC 1337 voss-budget= with cumulative totals after each LLM response.
2. Rust PTY reader strips OSC from display bytes and emits BudgetUpdate event.
3. Agent panes show cost text + conditional progress bar in 22px header.
4. Shell panes show nothing.
5. Click budget segment opens detail popover with tokens, model, turns, cost.
6. 3-tier color thresholds: green (<70%), amber (70-90%), red (90-100%).
7. Budget state resets on app restart; first OSC repopulates (self-heal).

**Cross-cutting:** Builds on A2 PTY subsystem (reader.rs, commands.rs, PtyEvent, PtyTransport) + A3 PaneComponent inline header. Does NOT modify PaneHeader.tsx (grid layer uses it; PaneComponent has its own inline header). Creates a thin Popover.tsx primitive forward-compatible with A10 status bar popover pattern.

### Phase F5: Commit with Critique Hook

**Goal:** `voss consensus` CLI command for single-shot LLM critique of diffs against natural-language constraints in `.voss/constraints.yml`, plus `voss hooks install/uninstall` to wire it as a git pre-commit hook.

**Requirements:** D-01..D-16 (locked in `F5-CONTEXT.md`)

**Plans:** 2 plans, 2 waves

Plans:
- [ ] F5-01-PLAN.md — Core consensus module + Pydantic models + CLI command + tests (D-01..D-04, D-08..D-16)
- [ ] F5-02-PLAN.md — Hook lifecycle install/uninstall + hook tests (D-05..D-07)

**Success Criteria:**
1. `voss consensus --staged` critiques staged diff against constraints.yml rules.
2. Exits 0 silently when no constraints.yml exists (D-04).
3. Exits 1 on violations when mode=block; exits 0 when mode=warn (D-09).
4. Fails open on LLM errors — exit 0 + warning (D-16).
5. `voss hooks install` writes 3-line shell shim; refuses if hook exists (D-07).
6. `voss hooks uninstall` removes only voss-installed hooks.
7. Zero new dependencies.

### Phase 1: voss-app ADE Visual Redesign — Left Sidebar + Warm Site Palette

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 0
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 1 to break down)

---

## Backlog

Unsequenced parking-lot ideas (999.x). Promote with `/gsd:review-backlog`.

### Phase 999.1: voss-app Agents launcher + manager (BACKLOG)

**Goal:** A titlebar/navbar "Agents" affordance to manage and spawn agents, plus
shippable launch prefixes that open a new terminal pane and launch a specific
agent CLI — named targets: Claude (`claude`), Codex, Gemini, OpenCode.
**Requirements:** TBD
**Plans:** 0 plans

Context: validated when Claude Code ran interactively inside the A2 PTY pane
(header showed `claude.exe` via OSC title). Candidate **A-track phase AFTER
A3** — agent panes are grid panes, so the A3 Grid Engine (Warp-style locked
tiling) must land first. Likely shape: (a) agent registry config
(name → launch command + cwd), (b) titlebar "Agents" panel to manage/spawn,
(c) prefix dispatch spawning a new A3 grid pane running the agent CLI (reuse
A2 `PtyTransport` + A3 split). See session memory
`voss-agents-launcher-feature`, `voss-app-grid-warp-parity`,
`voss-app-track-build-order`.

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: voss-app focused-pane resize keybind ⌘/Win +/− (BACKLOG)

**Goal:** `⌘ +` / `⌘ -` (Windows key on Windows — reuse the A1-03
`@tauri-apps/plugin-os` platform gate) grows/shrinks the **focused** terminal
pane within the tiling grid.
**Requirements:** TBD (fold into A3 keymap when A3 executes)
**Plans:** 0 plans

Context: this belongs to **A3 (Grid Engine)**, which already plans
split/fork/close/equalize + focus+resize (`⌘=` global equalize). This entry
exists so the `⌘+`/`⌘-` focused-pane grow/shrink keybind is not lost — when
A3 is executed (or replanned), add it to the A3 keymap/requirements rather
than building a standalone phase. Snap-locked tiling, no free-canvas resize
(memory `voss-app-grid-warp-parity`).

Plans:
- [ ] TBD (fold into A3 keymap on A3 execution / promote with /gsd:review-backlog)

### Phase 999.3: Human Sprint Orchestration over Agent Board (BACKLOG)

**Goal:** Human-facing sprint/kanban management layered on the V5 Board State
Machine — time-boxed sprints, human+agent mixed assignment, estimation, and
velocity/burndown. Distinct from V5/V7, which are *autonomous agent-org*
orchestration (EM routes cards to an LLM roster, continuous flow, no human
ceremonies).
**Requirements:** TBD
**Plans:** 0 plans

Context: V5 already ships the kanban substrate — columns
`Backlog→Planned→InProgress→InReview→Blocked→Done`, per-column WIP limits,
gated transitions, `Card` = ticket backed by a V4 session-tree node carrying
idea/role/scope/risk/AC/budget/status. V7 EM loop converts idea→tickets/AC/DoD
and routes by role. **What's missing for human sprint management:** (a) no
sprints/iterations — board is continuous flow, no time-boxes; (b) no human
assignee — cards route to LLM roster (backend/frontend/ui/ai), not human devs;
(c) no estimation/velocity/burndown/story-points; (d) no human standup
(line 1682 flags Standup→`semantic.memory` poisoning as an *unaddressed leak*,
not a feature); (e) no human-facing ticket CRUD UI (`voss board` renders agent
state, not a Jira-style board).

Likely shape: extend `Card` schema (add `assignee`, `sprint_id`, `estimate`)
rather than a parallel store; sprint grouping + velocity over the existing
board; ADE sprint view as a V11 panel. Two build paths — (1) extend
**V5 + V11** in place, or (2) standalone phase (A14 / next free V) atop V5. Note: the
external `/jira:*` skill covers Jira integration but is not native Voss board
tooling. Decide native-vs-integration at promotion.

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
