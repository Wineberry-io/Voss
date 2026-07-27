"""M9-05 permissions bridge — modal-driven prompt_fn / scope_prompt_fn."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from voss.harness.permissions import PermissionGate, PermissionStore
from voss.harness.tui.permissions_bridge import install_tui_permissions


@pytest.fixture(autouse=True)
def _tty_stdin(monkeypatch):
    """Bridge runs while a TUI owns stdin; gate's tty-check should pass."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


class _Host(App):
    def compose(self) -> ComposeResult:
        return []

    def push_modal_and_wait(self, modal, on_decision_callback) -> None:
        self.push_screen(modal, on_decision_callback)


def test_install_sets_both_callables() -> None:
    gate = PermissionGate()
    assert gate.prompt_fn is None
    assert gate.scope_prompt_fn is None
    install_tui_permissions(gate, app=object())
    assert callable(gate.prompt_fn)
    assert callable(gate.scope_prompt_fn)


@pytest.mark.asyncio
async def test_permission_a_grants_once(tmp_path: Path) -> None:
    app = _Host()
    gate = PermissionGate(mode="edit", store=PermissionStore(cwd=tmp_path))
    async with app.run_test() as pilot:
        install_tui_permissions(gate, app)
        check = asyncio.create_task(
            asyncio.to_thread(
                gate.check,
                "fs_write",
                {"path": str(tmp_path / "a.txt"), "content": "x"},
            )
        )
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        allowed, why = await check
        assert allowed is True
        assert why == "allowed once"


@pytest.mark.asyncio
async def test_permission_A_grants_always(tmp_path: Path) -> None:
    app = _Host()
    gate = PermissionGate(mode="edit", store=PermissionStore(cwd=tmp_path))
    async with app.run_test() as pilot:
        install_tui_permissions(gate, app)
        check = asyncio.create_task(
            asyncio.to_thread(
                gate.check,
                "fs_write",
                {"path": str(tmp_path / "b.txt"), "content": "x"},
            )
        )
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        allowed, why = await check
        assert allowed is True
        assert why == "allowed always"


@pytest.mark.asyncio
async def test_permission_d_denies(tmp_path: Path) -> None:
    app = _Host()
    gate = PermissionGate(mode="edit", store=PermissionStore(cwd=tmp_path))
    async with app.run_test() as pilot:
        install_tui_permissions(gate, app)
        check = asyncio.create_task(
            asyncio.to_thread(
                gate.check,
                "fs_write",
                {"path": str(tmp_path / "c.txt"), "content": "x"},
            )
        )
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        allowed, why = await check
        assert allowed is False
        assert why == "denied"


@pytest.mark.asyncio
async def test_permission_escape_denies(tmp_path: Path) -> None:
    app = _Host()
    gate = PermissionGate(mode="edit", store=PermissionStore(cwd=tmp_path))
    async with app.run_test() as pilot:
        install_tui_permissions(gate, app)
        check = asyncio.create_task(
            asyncio.to_thread(
                gate.check,
                "fs_write",
                {"path": str(tmp_path / "d.txt"), "content": "x"},
            )
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        allowed, why = await check
        assert allowed is False
        assert why == "denied"


@pytest.mark.asyncio
async def test_scope_prompt_routes_through_modal(tmp_path: Path) -> None:
    """ScopeExpandModal -> 'always' maps to out-of-scope: always."""
    from voss.harness.edit_scope import EditScope

    (tmp_path / "in_scope").mkdir()
    (tmp_path / "out").mkdir()
    scope = EditScope.resolve(tmp_path, "in_scope")
    gate = PermissionGate(
        mode="edit",
        store=PermissionStore(cwd=tmp_path),
        edit_scope=scope,
        auto_yes=True,  # skip the inner prompt; only test scope expansion
    )
    app = _Host()
    async with app.run_test() as pilot:
        install_tui_permissions(gate, app)
        check = asyncio.create_task(
            asyncio.to_thread(
                gate.check,
                "fs_write",
                {"path": str(tmp_path / "out" / "x.txt"), "content": "x"},
            )
        )
        await pilot.pause()
        await pilot.press("a")  # always
        await pilot.pause()
        allowed, why = await check
        assert allowed is True
        assert why == "out-of-scope: always"


@pytest.mark.asyncio
async def test_scope_prompt_n_denies(tmp_path: Path) -> None:
    from voss.harness.edit_scope import EditScope

    (tmp_path / "in_scope").mkdir()
    (tmp_path / "out").mkdir()
    scope = EditScope.resolve(tmp_path, "in_scope")
    gate = PermissionGate(
        mode="edit",
        store=PermissionStore(cwd=tmp_path),
        edit_scope=scope,
        auto_yes=True,
    )
    app = _Host()
    async with app.run_test() as pilot:
        install_tui_permissions(gate, app)
        check = asyncio.create_task(
            asyncio.to_thread(
                gate.check,
                "fs_write",
                {"path": str(tmp_path / "out" / "y.txt"), "content": "x"},
            )
        )
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        allowed, why = await check
        assert allowed is False
        assert why == "out-of-scope denied"


def test_permissions_py_signature_unchanged() -> None:
    """Guard: PermissionGate must NOT gain new fields from this bridge."""
    import dataclasses

    from voss.harness.permissions import PermissionGate as PG

    field_names = {f.name for f in dataclasses.fields(PG)}
    expected = {
        "mode",
        "store",
        "auto_yes",
        "prompt_fn",
        "edit_scope",
        "scope_prompt_fn",
        "project_policy",
        "allow_net",  # network-permission gate (added post-M9-05)
        "cwd",  # BOS4 decision-ledger root; unrelated to this bridge
        # V12 safety overlay (552cd00) — irreversible-operation validation;
        # added by the safety phase, not this bridge.
        "safety_policy",
        "safety_actor",
        "safety_confirm_fn",
    }
    assert field_names == expected
