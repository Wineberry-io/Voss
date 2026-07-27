"""Permission gate for tool calls.

Modes:
- plan : reads auto, every write/shell prompts
- edit : reads + scoped writes auto, shell/net prompt   (default)
- auto : all allowlisted auto, destructive patterns prompt

Decisions persist per-cwd in ~/.config/voss/permissions.json.

CTRL-08: every `fs_write` / `fs_edit` call renders a unified diff preview to
stderr BEFORE the call is allowed to proceed. This is scope-independent — it
fires whether or not an EditScope is attached, so `voss do --mode=edit` and
`voss chat --mode=edit` writes get the same preview as `voss edit`.

Project-level layering (.voss/permissions.yml, added in M2)
-----------------------------------------------------------
When .voss/permissions.yml is loaded into a PermissionsConfig and attached
to the gate, its rules layer on top of the session mode:

  - deny (project) ALWAYS wins, even in mode=auto.
  - allow (project) is recorded but does NOT expand session-mode
    permissions (a project allow does not auto-approve a tool that the
    session mode would have prompted for).

This mirrors M1's "least-privilege wins" stance.
"""
from __future__ import annotations

import difflib
import json
import os
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional
from uuid import uuid4

from portalocker.exceptions import LockException

from .bos_decisions import append_decision, build_as_of, build_verdict_record
from .cognition_schemas import PermissionsConfig, SafetyConfig
from .safety import (
    SafetyActorContext,
    SafetyConfirmRequest,
    build_confirm_request,
    classify,
    confirmation_matches,
    decide,
)

if TYPE_CHECKING:
    from .edit_scope import EditScope

Mode = Literal["plan", "edit", "auto"]

READ_ONLY = {"fs_read", "fs_glob", "fs_grep", "git_status", "git_diff", "voss_check"}
WRITE = {"fs_write", "fs_edit"}
SHELL = {"shell_run", "shell_run_background", "shell_monitor", "shell_signal"}


def _rule_command_arg(tool_name: str, args: dict) -> str:
    """The argument string a per-command sub-map matches against."""
    if tool_name in SHELL:
        return str(args.get("cmd", ""))
    if tool_name in WRITE:
        return str(args.get("path", ""))
    return str(args.get("cmd") or args.get("path") or "")


def _decision_for(value: Any, arg_str: str) -> str | None:
    """Resolve a rule value to a decision. Sub-maps: last matching wins."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        decision: str | None = None
        for pattern, dec in value.items():
            if fnmatch(arg_str, str(pattern)):
                decision = dec
        return decision
    return None


def match_permission_rules(
    rules: dict | None, tool_name: str, args: dict
) -> str | None:
    """OpenCode-style wildcard rule lookup → "allow" | "ask" | "deny" | None.

    A specific tool key wins over the "*" wildcard. For a per-command sub-map
    (e.g. `{"*": "ask", "git status *": "allow"}`) the last matching pattern
    wins, so callers list "*" first.
    """
    if not rules:
        return None
    arg_str = _rule_command_arg(tool_name, args)
    if tool_name in rules:
        d = _decision_for(rules[tool_name], arg_str)
        if d is not None:
            return d
    if "*" in rules:
        d = _decision_for(rules["*"], arg_str)
        if d is not None:
            return d
    return None


def mode_allows(mode: Mode, tool_name: str, is_mutating: bool) -> tuple[bool, str]:
    """Strict tier check. Returns (allowed_by_mode, reason).

    plan : read-only — denies all mutating tools.
    edit : reads + fs_write/fs_edit — explicitly denies shell_run.
    auto : everything — caller still enforces allowlist/timeouts downstream.
    """
    if mode == "plan":
        if is_mutating:
            return False, "denied by mode plan"
        return True, "ok"
    if mode == "edit":
        if tool_name in {"shell_run", "shell_run_background", "shell_signal"}:
            return False, "denied by mode edit"
        # D-12: shell_monitor omitted deliberately — read-only, executes nothing
        return True, "ok"
    return True, "ok"


def _config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "voss" / "permissions.json"


def compute_diff_text(tool_name: str, args: dict, base_dir: Path) -> str:
    """Compute the unified diff text for an fs_write / fs_edit call.

    Returns the diff string (may be empty). Pure: does not write to stderr.
    Used by both the stderr-preview path (PermissionGate._render_diff_preview)
    and the TUI modal-bridge path. Failure (file unreadable, encoding) yields
    an empty string — diff preview is best-effort.
    """
    try:
        path = args.get("path", "")
        if not path:
            return ""
        base = Path(base_dir).resolve()
        p = (base / path).resolve()
        current = p.read_text() if p.exists() else ""
        if tool_name == "fs_write":
            new = args.get("content", "")
        elif tool_name == "fs_edit":
            old = args.get("old", "")
            replacement = args.get("new", "")
            new = current.replace(old, replacement, 1) if old in current else current
        else:
            return ""
        return "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
            )
        )
    except (OSError, UnicodeDecodeError):
        return ""


@dataclass
class PermissionStore:
    """Persisted always-allow decisions per cwd."""

    cwd: Path
    always: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, cwd: Path) -> "PermissionStore":
        p = _config_path()
        if not p.exists():
            return cls(cwd=cwd)
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            return cls(cwd=cwd)
        key = str(cwd.resolve())
        always = set(data.get(key, {}).get("always", []))
        return cls(cwd=cwd, always=always)

    def save(self) -> None:
        p = _config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(p.read_text()) if p.exists() else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        key = str(self.cwd.resolve())
        data[key] = {"always": sorted(self.always)}
        p.write_text(json.dumps(data, indent=2))

    def remember(self, signature: str) -> None:
        self.always.add(signature)
        self.save()


@dataclass
class PermissionGate:
    mode: Mode = "edit"
    store: PermissionStore | None = None
    auto_yes: bool = False  # for tests + non-interactive runs
    prompt_fn: Optional[Callable] = None  # injected for tests
    edit_scope: Optional["EditScope"] = None  # set by voss edit; None for do/chat
    scope_prompt_fn: Optional[Callable] = None  # injected for tests
    project_policy: Optional[PermissionsConfig] = None  # .voss/permissions.yml
    allow_net: Optional[bool] = None  # per-gate override; None → process config
    # V12 safety overlay (additive). When a safety_policy is attached, classified
    # dangerous/factory-only operations are confirmed/routed/denied BEFORE the
    # normal mode/prompt path — auto_yes cannot bypass irreversible confirmation.
    safety_policy: Optional[SafetyConfig] = None  # .voss/safety.yml
    safety_actor: Optional[SafetyActorContext] = None  # role/model-tier context
    safety_confirm_fn: Optional[Callable] = None  # injected for tests; SafetyConfirmRequest -> str
    # Explicit decision-ledger root; falls back to store.cwd when available.
    cwd: Path | None = field(default=None, kw_only=True)

    def needs_prompt(self, tool_name: str, *, is_mutating: bool = False) -> bool:
        if self.auto_yes:
            return False
        if self.mode == "auto":
            return False
        if self.mode == "plan":
            return tool_name not in READ_ONLY
        # edit
        return is_mutating or tool_name in WRITE or tool_name in SHELL

    def signature(self, tool_name: str, args: dict) -> str:
        if tool_name == "shell_run":
            return f"shell_run:{args.get('cmd', '').split()[0] if args.get('cmd') else ''}"
        if tool_name == "shell_run_background":
            return f"shell_run_background:{args.get('cmd', '').split()[0] if args.get('cmd') else ''}"
        return tool_name

    def check(
        self,
        tool_name: str,
        args: dict,
        *,
        is_mutating: bool = False,
        is_network: bool = False,
    ) -> tuple[bool, str]:
        allowed, why = self._check_impl(
            tool_name, args, is_mutating=is_mutating, is_network=is_network
        )
        from . import telemetry

        if telemetry.enabled():
            telemetry.emit(
                "permission.result",
                "info",
                data={
                    "tool": tool_name,
                    "allowed": allowed,
                    "why": why,
                    "mode": self.mode,
                    "args": telemetry.redact_tool_args(dict(args)),
                },
            )
        return allowed, why

    def _check_impl(
        self,
        tool_name: str,
        args: dict,
        *,
        is_mutating: bool = False,
        is_network: bool = False,
    ) -> tuple[bool, str]:
        """Return (allowed, reason).

        Order of operations:
          0. Project-policy deny (`.voss/permissions.yml`) — deny wins over
             allow and over session-mode auto. Project allow does NOT expand
             mode (recorded but not short-circuiting).
          0a. T3-02 net gate (D-10): when is_network=True, evaluate per-gate
              PermissionGate.allow_net before process config:
              - False → deny ("per-gate override"), ignoring harness allow_net.
              - True → skip process net check (project deny in step 0 still
                applies).
              - None → legacy: deny when get_config().allow_net is False.
              Net is a separate safety axis from mutating writes.
          1. Mode-tier structural denial (skips everything else).
          2. CTRL-08 diff preview for any fs_write/fs_edit (scope-independent).
          3. Scope check (only if edit_scope set) — expand-prompt fires AFTER
             the diff render, so user sees the diff before deciding.
          4. Within-mode interactive prompt or auto-yes path.
        """
        rule_decision: str | None = None
        if self.project_policy is not None:
            if tool_name in self.project_policy.tool_policy.deny:
                return False, "denied by .voss/permissions.yml"
            rule_decision = match_permission_rules(
                getattr(self.project_policy, "rules", None), tool_name, args
            )
            if rule_decision == "deny":
                return False, "denied by permission rule (.voss/permissions.yml)"

        # V12 safety overlay — runs before the net/mode/prompt path so that
        # `auto_yes`/auto-mode cannot suppress irreversible confirmation or
        # factory routing. A None result means "no safety match → continue".
        safety_result = self._safety_check(tool_name, args)
        if safety_result is not None:
            return safety_result

        if is_network:
            if self.allow_net is False:
                return False, "net disabled for this role (per-gate override)"
            if self.allow_net is None:
                from voss_runtime._config import get_config

                if not get_config().allow_net:
                    return False, (
                        "net disabled: set tools.allow_net = true in "
                        "harness.toml or pass --allow-net"
                    )

        allowed, why = mode_allows(self.mode, tool_name, is_mutating)
        if not allowed:
            return False, why

        # CTRL-08: diff preview for ALL mutating writes, regardless of scope.
        diff_summary = ""
        if tool_name in WRITE:
            diff_summary = self._render_diff_preview(tool_name, args)

        # Scope check for writes — only if an edit_scope is attached.
        if self.edit_scope is not None and tool_name in WRITE:
            target = args.get("path", "")
            if target and not self.edit_scope.allows_write(target):
                ok, expand_kind = self._prompt_expand(target)
                if not ok:
                    return False, "out-of-scope denied"
                if expand_kind == "always":
                    self.edit_scope.expand(target)
                return True, f"out-of-scope: {expand_kind}"

        # H5.1: rule "allow" auto-approves (within mode, checked above);
        # rule "ask" forces a prompt even in auto-mode / over a remembered
        # decision. Project policy is authoritative over session ergonomics.
        if rule_decision == "allow":
            return True, "allowed by permission rule (.voss/permissions.yml)"

        # V1 CAP-09: mutability is capability metadata, not a tool-name guess.
        # This covers native, attached, and MCP tools uniformly in edit mode.
        needs = self.needs_prompt(tool_name, is_mutating=is_mutating) or rule_decision == "ask"
        if not needs:
            return True, "auto"
        if self.store is not None and rule_decision != "ask":
            sig = self.signature(tool_name, args)
            if sig in self.store.always:
                return True, "remembered"
        return self._prompt(
            tool_name,
            args,
            is_mutating=is_mutating,
            diff_summary=diff_summary,
        )

    def _safety_check(self, tool_name: str, args: dict) -> tuple[bool, str] | None:
        """V12 safety overlay. Returns:

        - None: no safety rule matched, OR an irreversible action was confirmed
          with the exact token → continue to the normal gate path.
        - (False, reason): denied — confirmation failed, or a dangerous/factory
          operation is routed to a runbook/pipeline (direct execution blocked).
        """
        if self.safety_policy is None:
            return None
        c = classify(self.safety_policy, tool_name, args, actor=self.safety_actor)
        if not c.matched:
            return None

        # VSAFE-01: irreversible actions require exact-action confirmation; this
        # path is evaluated even when auto_yes is True.
        if c.requires_confirmation:
            req = build_confirm_request(tool_name, args, c)
            if self.safety_confirm_fn is None and not sys.stdin.isatty():
                return False, (
                    f"safety: irreversible action requires confirmation but none "
                    f"available (non-interactive): {req.exact_action}"
                )
            fn = self.safety_confirm_fn or _interactive_safety_confirm
            response = fn(req)
            if not confirmation_matches(req, response):
                return False, (
                    f"safety: confirmation did not match exact action "
                    f"'{req.exact_action}'"
                )
            return None  # confirmed → proceed to the existing mode/project gate

        # VSAFE-02/03/04: route dangerous/factory operations through their named
        # runbook/pipeline; V12 blocks direct execution before invocation.
        d = decide(c)
        if d.action == "runbook" and c.runbook is not None:
            rb = next(
                (r for r in self.safety_policy.runbooks if r.name == c.runbook), None
            )
            if rb is None or not rb.steps:
                return False, (
                    f"safety: runbook '{c.runbook}' has no defined procedure; "
                    f"direct execution denied"
                )
            return False, (
                f"safety: routed to runbook '{c.runbook}'; direct execution blocked"
            )
        if d.action == "runbook" and c.pipeline is not None:
            return False, (
                f"safety: routed to fixed pipeline '{c.pipeline}'; "
                f"direct execution blocked"
            )
        if d.action == "scaffold":
            target = c.runbook or "scaffold"
            return False, (
                f"safety: weak-model scaffold required ('{target}'); "
                f"direct execution blocked"
            )
        # Matched but no actionable route (e.g. runbook field unexpectedly None).
        return False, "safety: factory operation requires a runbook; none configured"

    def _render_diff_preview(self, tool_name: str, args: dict) -> str:
        """Render a unified diff to stderr before applying a write (CTRL-08).

        Scope-independent: runs for every fs_write / fs_edit. Resolves the
        target against `edit_scope.cwd`, explicit `cwd`, `store.cwd`, or the
        process cwd, in that order.
        Failure (file unreadable, encoding error) is swallowed silently —
        diff preview is best-effort and must not block the gate.

        Returns a non-sensitive summary when a diff was rendered.
        """
        if self.edit_scope is not None:
            base_dir = self.edit_scope.cwd
        elif self.cwd is not None:
            base_dir = self.cwd
        elif self.store is not None:
            base_dir = self.store.cwd
        else:
            base_dir = Path(".")
        diff = compute_diff_text(tool_name, args, base_dir)
        if not diff:
            return ""
        sys.stderr.write("\n  diff preview:\n")
        for line in diff.splitlines():
            sys.stderr.write(f"    {line}\n")
        sys.stderr.flush()
        return f"{tool_name} diff preview rendered"

    def _prompt_expand(self, target: str) -> tuple[bool, str]:
        """Prompt: expand scope to include <target>? [y/once/always/n]."""
        if self.scope_prompt_fn is None and not sys.stdin.isatty():
            return False, "non-interactive denial"
        prompt = self.scope_prompt_fn or _interactive_expand_prompt
        choice = prompt(target)
        if choice in ("y", "once"):
            return True, "once"
        if choice == "always":
            return True, "always"
        return False, "denied"

    def _prompt(
        self,
        tool_name: str,
        args: dict,
        *,
        is_mutating: bool = False,
        diff_summary: str = "",
    ) -> tuple[bool, str]:
        # An injected prompt_fn (server permission bridge, TUI bridge, tests)
        # must be consulted even without a TTY — same contract as
        # _prompt_expand below. Only the interactive fallback needs stdin.
        if self.prompt_fn is None and not sys.stdin.isatty():
            return False, "non-interactive denial"
        prompt = self.prompt_fn or _interactive_prompt
        choice = prompt(tool_name, args)
        if choice == "a":
            allowed, reason = True, "allowed once"
        elif choice == "A":
            if self.store is not None:
                self.store.remember(self.signature(tool_name, args))
            allowed, reason = True, "allowed always"
        else:
            allowed, reason = False, "denied"

        # Inline human-verdict emission (D-R01/D-R04): only post-prompt answers.
        ledger_cwd = self.cwd
        if ledger_cwd is None and self.store is not None:
            ledger_cwd = self.store.cwd
        if ledger_cwd is not None:
            try:
                record = build_verdict_record(
                    decision_id=f"dec-perm-{uuid4().hex}",
                    verdict="approve" if allowed else "dismiss",
                    actor_id="operator",
                    feature_snapshot={
                        "tool_name": tool_name,
                        "is_mutating": is_mutating,
                        "mode": self.mode,
                        "signature": self.signature(tool_name, args),
                        "diff_summary": diff_summary,
                    },
                    entity_ref={},
                    as_of=build_as_of(
                        ledger_cwd / ".voss" / "bos" / "events.jsonl"
                    ),
                    reason=f"permission prompt: {tool_name}",
                    rationale=(
                        f"permission gate verdict for {tool_name} in mode {self.mode}"
                    ),
                    autonomy_band="",
                )
                append_decision(ledger_cwd, record)
            except (OSError, ValueError, LockException):
                pass
        return allowed, reason


def _interactive_safety_confirm(req: "SafetyConfirmRequest") -> str:
    """TTY confirmation for an irreversible safety action (VSAFE-01)."""
    sys.stderr.write(f"\n  ⛔ SAFETY: {req.risk_summary}\n")
    sys.stderr.write(f"     exact action: {req.exact_action}\n")
    sys.stderr.write("     re-type the exact action to confirm: ")
    sys.stderr.flush()
    return sys.stdin.readline().strip()


def _interactive_expand_prompt(target: str) -> str:
    sys.stderr.write(f"\n  ⚠  expand scope to include {target}?\n")
    sys.stderr.write("     [y] yes once  [a] always (this session)  [n] no: ")
    sys.stderr.flush()
    line = sys.stdin.readline().strip().lower()
    if not line:
        return "n"
    if line.startswith("a"):
        return "always"
    if line.startswith("y"):
        return "once"
    return "n"


def _interactive_prompt(tool_name: str, args: dict) -> str:
    argstr = ", ".join(f"{k}={_short(v)}" for k, v in args.items())
    sys.stderr.write(f"\n  ⚠  {tool_name}({argstr})\n")
    sys.stderr.write("     [a] allow once  [A] allow always  [d] deny: ")
    sys.stderr.flush()
    line = sys.stdin.readline().strip()
    if not line:
        return "d"
    return line[0]


def _short(v: object, limit: int = 60) -> str:
    s = str(v)
    return s[: limit - 1] + "…" if len(s) > limit else s
