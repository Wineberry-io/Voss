# ADR 0002: Observe capability ceiling is a permission mode

**Date:** 2026-09-05
**Status:** Accepted
**Plan:** `.planning/CANVAS-OBSERVE-INSTRUCTIONS-PLAN.md` S0.7, S6

## Context

Automatic investigations must not write project files, run shell commands, make arbitrary network requests, create worktrees, or commit. The existing modes are `plan`, `edit`, `auto`. `plan` denies mutating tools structurally in `mode_allows` but `PermissionGate.needs_prompt` still prompts for non-read-only tools, and project-policy `allow` rules or `auto_yes` can approve within a mode. That is the wrong shape for an unattended run: a prompt is a hang, and an allow rule is a widening.

`voss/harness/swarm_runtime.py` runs external CLI members in git worktrees and commits their work (`_commit_member_work`). Its ownership enforcement is post-exit reconciliation, not a read-only guarantee.

## Decision

1. A fourth mode, `observe`, in `voss/harness/permissions.py`. `PermissionGate._check_impl` denies first, before project policy, safety overlay, network gate, and prompt path, whenever the tool is mutating, network, in `WRITE`, or in `SHELL`. `needs_prompt` returns `False` in observe mode: reads run without prompting, everything else is denied without prompting. `mode_allows("observe", ...)` mirrors the denial so callers that only consult the predicate agree.
2. Automatic investigations run as native `ServerSession`s with `mode="observe"` and a tool profile limited to `fs_read`, `fs_search`/`fs_grep`/`fs_glob`, `git_status`, `git_diff`, memory recall, and code recall. The allowlist is applied at tool-catalog construction; the mode is the backstop.
3. `swarm_runtime.py` and every path that can create worktrees, candidate commits, background shells, or custom launchers is excluded from the Observe route. A test greps `voss/harness/observe/` for imports of those modules and fails on any hit.
4. Specialists inherit the same gate object, budget, and cancellation token. They cannot widen.
5. UI settings and prompts cannot raise the ceiling. Enrollment can only narrow.

## Consequences

- Twenty lines in `permissions.py` carry the whole guarantee; tests assert the prompt function is never called and a project `allow` rule does not override.
- `plan` mode is unchanged for interactive use.
- `team.py`, `subagents.py`, and `cognition_schemas.py` keep validating `plan|edit|auto` for their own configs; `observe` is not a user-selectable team mode.
- Explicit follow-ups (propose fix, verification) run in a separate session with `mode="edit"` bounded by `EditScope`, never by upgrading an observe session.
