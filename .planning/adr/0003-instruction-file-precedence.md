# ADR 0003: AGENTS.md and CLAUDE.md as one hashed bundle

**Date:** 2026-09-05
**Status:** Accepted
**Plan:** `.planning/CANVAS-OBSERVE-INSTRUCTIONS-PLAN.md` §0 decisions 7 and 8, S0.3, S4

## Context

The harness reads `VOSS.md` and `.voss/` (cognition, principles, permissions, safety) and nothing else. `AGENTS.md` (Codex, Cursor, and the vendor-neutral convention) and `CLAUDE.md` (Claude Code) are never loaded, never hashed, never synced. `voss sync` writes a `VOSS.md` fence; the V16 roadmap text promised a managed block in the agent instruction file but the shipped template targets `VOSS.md` only. A native Voss run in a repo therefore ignores the rules every external agent in the same repo obeys, and nothing records which rules were in force when a decision was made.

## Decision

**Peers, one body.** `AGENTS.md` and `CLAUDE.md` carry the same content for a project. Voss keeps one canonical body (`VOSS.md` managed content plus `.voss/instructions.md`, S4) and renders agent-specific managed blocks into each file: `CLAUDE.md` for Claude panes, `AGENTS.md` for Codex and Cursor panes. The launch modal checks the file matching the CLI being launched.

**Loading.** `voss/harness/instructions.py` discovers files in this order and injects them in this order: optional global files, project-root `AGENTS.md` then `CLAUDE.md`, then each directory from the root down to the target directory (nearest last). Claude Code `@path` imports are inlined once, depth ≤ 3, cycle-guarded. A `CLAUDE.md` whose non-blank content is only imports of files already in the bundle collapses. Identical content across two files is kept once. Budget: 4,000 tokens total, 2,000 per file, overflow surfaced as `instructions_overflow`.

**Hash.** `bundle_hash` identifies the effective bundle: sha256 over ordered `(path, sha256)` pairs of the files that made the bundle, followed by `budget_tokens`, `per_file_tokens`, and the ordered list of truncated paths. Changing a budget or crossing a truncation boundary therefore changes the hash, so two runs with the same files but a different injected prompt never share one. It is recorded on `SessionRecord` at creation and on every `RunRecord`; later on the agent registry row (S4) and as a BOS4 decision feature (S9).

**Imports.** `@path` targets must resolve, after following symlinks, inside the instruction root: the project root for repository files, the file's own directory for opt-in global files. Absolute, home-relative, and traversal paths are rejected and reported in `load_errors`; nothing outside the root is ever read into the prompt.

**Global files.** `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` are read only when `[instructions] read_global = true` in `config.toml`. Default off: they often hold personal rules and occasionally credentials.

**Prompt position.** The `## Instructions` block sits immediately after the `VOSS.md` fence and before cognition, inside the cacheable static prefix.

## Consequences

- Native runs and external agents obey the same rules; the difference is now measurable per hash.
- Budget truncation cuts the last (most specific) files first. Acceptable for S0; S4 may reorder by scope distance if it bites.
- Because the hash includes budget settings, changing `[instructions]` in config.toml shows as an instruction change on resume. Intended: the effective prompt did change.
- `SessionRecord.new` now touches the filesystem to compute the hash. Cost is a handful of small reads.
- Every renderer gains `show_instructions_overflow`; the server event union gains `instructions_overflow`; contracts and SDK types regenerate.
- The redaction allowlist grows by two fields on both records. Instruction text itself is never stored in records, only paths and hashes.
