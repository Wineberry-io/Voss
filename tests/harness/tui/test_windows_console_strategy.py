"""M9-07 Windows-console capability branch.

UI-SPEC + CONTEXT-locked decision: legacy Windows console (cmd.exe /
conhost without WT_SESSION) hard-blocks the TUI and falls back to
PlainRenderer with the locked stderr notice.
`sys.platform == "win32"` + presence of `WT_SESSION` (set by Windows
Terminal) preserves the normal capability check.

Non-win32 platforms are unaffected.
"""
from __future__ import annotations


import pytest

from voss.harness.tui.capability import TUIDecision, tui_should_activate


WIN_NOTICE_REASON = "Windows console missing capability"


def test_win32_without_wt_session_hard_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("voss.harness.tui.capability.sys.platform", "win32")
    env: dict[str, str] = {}
    d = tui_should_activate(
        argv=[],
        env=env,
        stdout_isatty=True,
        json_mode=False,
        size=(120, 40),
    )
    assert d == TUIDecision(activate=False, reason=WIN_NOTICE_REASON)


def test_win32_with_wt_session_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows Terminal sets `WT_SESSION`. Capability check proceeds normally."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("voss.harness.tui.capability.sys.platform", "win32")
    d = tui_should_activate(
        argv=[],
        env={"WT_SESSION": "abc"},
        stdout_isatty=True,
        json_mode=False,
        size=(120, 40),
    )
    # On a healthy WT_SESSION, decision should activate (textual is installed
    # in the test env).
    assert d.activate is True or d.reason in (
        "textual not installed",
        "terminal below 60x12",
    )
    assert d.reason != WIN_NOTICE_REASON


def test_non_win32_unaffected_by_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """On linux/darwin, missing WT_SESSION must NOT trigger the Windows branch."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("voss.harness.tui.capability.sys.platform", "linux")
    d = tui_should_activate(
        argv=[],
        env={},
        stdout_isatty=True,
        json_mode=False,
        size=(120, 40),
    )
    assert d.reason != WIN_NOTICE_REASON


def test_win32_branch_fires_before_size_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Win-console reason wins over terminal-below-60x12 reason (order locked)."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("voss.harness.tui.capability.sys.platform", "win32")
    d = tui_should_activate(
        argv=[],
        env={},
        stdout_isatty=True,
        json_mode=False,
        size=(40, 10),  # also too small, but Windows branch wins
    )
    assert d == TUIDecision(activate=False, reason=WIN_NOTICE_REASON)


def test_render_factory_emits_locked_notice_on_win_console(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """make_renderer emits the locked stderr notice and returns PlainRenderer."""
    from voss.harness.render import PlainRenderer, make_renderer
    from voss.harness.tui.capability import TUIDecision as _Dec

    monkeypatch.setattr(
        "voss.harness.tui.capability.tui_should_activate",
        lambda **kw: _Dec(activate=False, reason=WIN_NOTICE_REASON),
    )
    renderer = make_renderer(json_mode=False, plain=False, force_tui=False)
    assert isinstance(renderer, PlainRenderer)
    captured = capsys.readouterr()
    assert "Windows console missing capability" in captured.err
    assert "using --plain mode" in captured.err
