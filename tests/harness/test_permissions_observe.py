"""S0.7 — `observe` mode: read-only, never prompts, deny wins (AC-S0-5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from voss.harness.cognition_schemas import PermissionsConfig
from voss.harness.permissions import PermissionGate, PermissionStore, mode_allows


def _fail_prompt(*_a, **_k) -> str:
    pytest.fail("prompt called in observe mode")


def _gate(tmp_path: Path, **kw) -> PermissionGate:
    g = PermissionGate(mode="observe", store=PermissionStore(cwd=tmp_path), **kw)
    g.prompt_fn = _fail_prompt
    g.scope_prompt_fn = _fail_prompt
    g.safety_confirm_fn = _fail_prompt
    return g


class TestModeAllows:
    def test_reads_ok(self) -> None:
        assert mode_allows("observe", "fs_read", False) == (True, "ok")
        assert mode_allows("observe", "git_diff", False) == (True, "ok")

    def test_writes_shell_and_mutating_denied(self) -> None:
        for tool, mut in (("fs_write", True), ("fs_edit", True), ("shell_run", True),
                          ("shell_run_background", True), ("mcp_thing", True)):
            assert mode_allows("observe", tool, mut) == (False, "denied by mode observe")


class TestGate:
    @pytest.mark.parametrize("tool", ["fs_write", "fs_edit", "shell_run", "shell_run_background", "shell_signal"])
    def test_denied_without_prompt(self, tmp_path: Path, tool: str) -> None:
        gate = _gate(tmp_path)
        allowed, why = gate.check(tool, {"path": "x", "cmd": "ls"}, is_mutating=True)
        assert (allowed, why) == (False, "denied by mode observe")

    def test_mutating_metadata_denied_even_for_unknown_tool(self, tmp_path: Path) -> None:
        gate = _gate(tmp_path)
        assert gate.check("custom_tool", {}, is_mutating=True)[0] is False

    def test_network_denied(self, tmp_path: Path) -> None:
        gate = _gate(tmp_path, allow_net=True)
        assert gate.check("web_fetch", {"url": "https://x"}, is_network=True) == (
            False, "denied by mode observe",
        )

    def test_reads_auto_approved(self, tmp_path: Path) -> None:
        gate = _gate(tmp_path)
        assert gate.check("fs_read", {"path": "a.py"}) == (True, "auto")
        assert gate.needs_prompt("fs_read") is False

    def test_auto_yes_does_not_widen(self, tmp_path: Path) -> None:
        gate = _gate(tmp_path, auto_yes=True)
        assert gate.check("fs_write", {"path": "a"}, is_mutating=True)[0] is False

    def test_project_allow_rule_does_not_override(self, tmp_path: Path) -> None:
        policy = PermissionsConfig.model_validate(
            {"tool_policy": {"allow": ["fs_write", "shell_run"], "deny": []},
             "rules": {"fs_write": "allow", "shell_run": "allow"}}
        )
        gate = _gate(tmp_path, project_policy=policy)
        assert gate.check("fs_write", {"path": "a"}, is_mutating=True)[0] is False
        assert gate.check("shell_run", {"cmd": "ls"}, is_mutating=True)[0] is False

    def test_remembered_always_does_not_override(self, tmp_path: Path) -> None:
        store = PermissionStore(cwd=tmp_path)
        store.always.add("shell_run:ls")
        gate = PermissionGate(mode="observe", store=store)
        gate.prompt_fn = _fail_prompt
        assert gate.check("shell_run", {"cmd": "ls"}, is_mutating=True)[0] is False
