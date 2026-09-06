"""M9-01 capability + --plain + auto-fallback + min-size guard tests."""
from __future__ import annotations


import pytest

from voss.harness.tui.capability import (
    TUIDecision,
    min_size_guard,
    tui_available,
    tui_should_activate,
)


def test_tui_available_with_textual() -> None:
    assert tui_available() is True


def test_plain_flag_returns_false() -> None:
    d = tui_should_activate(
        argv=["--plain"],
        env={},
        stdout_isatty=True,
        json_mode=False,
        size=(120, 40),
    )
    assert d == TUIDecision(activate=False, reason="--plain flag")


def test_voss_plain_env_returns_false() -> None:
    d = tui_should_activate(
        argv=[],
        env={"VOSS_PLAIN": "1"},
        stdout_isatty=True,
        json_mode=False,
        size=(120, 40),
    )
    assert d == TUIDecision(activate=False, reason="VOSS_PLAIN env")


def test_non_tty_returns_false() -> None:
    d = tui_should_activate(
        argv=[],
        env={},
        stdout_isatty=False,
        json_mode=False,
        size=(120, 40),
    )
    assert d == TUIDecision(activate=False, reason="non-TTY stdout")


def test_json_mode_returns_false() -> None:
    d = tui_should_activate(
        argv=[],
        env={},
        stdout_isatty=True,
        json_mode=True,
        size=(120, 40),
    )
    assert d == TUIDecision(activate=False, reason="--json mode")


@pytest.mark.parametrize("size", [(59, 24), (60, 11), (50, 10)])
def test_too_small_returns_false(size: tuple[int, int]) -> None:
    d = tui_should_activate(
        argv=[],
        env={},
        stdout_isatty=True,
        json_mode=False,
        size=size,
    )
    assert d == TUIDecision(activate=False, reason="terminal below 60x12")


def test_happy_path_activates() -> None:
    d = tui_should_activate(
        argv=[],
        env={},
        stdout_isatty=True,
        json_mode=False,
        size=(60, 12),
    )
    assert d == TUIDecision(activate=True, reason="ok")


def test_min_size_guard_locked_string() -> None:
    assert min_size_guard((79, 24)) == (
        "voss: terminal must be at least 60×12 "
        "(current: 79×24). Resize or use --plain."
    )


def test_capability_module_has_no_top_level_textual_import() -> None:
    """`capability.py` must NOT import textual at module top level.

    Static check on the source file so we don't have to mutate sys.modules
    at runtime (which would leak monkeypatched module bindings across tests).
    Top-level means column 0 (no indentation).
    """
    import voss.harness.tui.capability as cap_mod

    source = open(cap_mod.__file__).read()
    for line in source.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith("import textual") or line.startswith("from textual"):
            pytest.fail(f"top-level textual import found: {line!r}")
