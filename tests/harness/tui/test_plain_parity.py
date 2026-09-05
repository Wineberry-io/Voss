"""M9-01 stdout byte parity for `--plain` and auto-fallback.

The baseline at `tests/harness/tui/baseline/plain_baseline.txt` is the
pre-M9 stdout for a deterministic `voss do --plain` invocation against the
locked `FakeProvider` (imported from `tests/harness/test_voss_loop_parity.py`).
Every subsequent plan in M9 must keep this test green.

Idempotent capture: if the baseline file is missing AND
`VOSS_CAPTURE_BASELINE=1` is set, the test writes the baseline and skips.
Otherwise the test always compares bytes; the env flag is IGNORED when the
file already exists.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from voss.harness.agent import Plan
from voss.harness.cli import do_cmd

from tests.harness.test_voss_loop_parity import FakeProvider


CANNED_PLAN = Plan(
    rationale="locked baseline plan",
    steps=[],
    confidence=0.30,
    open_question="locked baseline question?",
    # T1-05: iteration-loop done-signal requires final_when_done to be
    # non-empty for _is_done_plan to recognize this as a terminating
    # iteration. open_question is what the clarify path surfaces.
    final_when_done="(tentative baseline)",
)


def _baseline_path() -> Path:
    return Path(__file__).parent / "baseline" / "plain_baseline.txt"


def _install_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_res = SimpleNamespace(source="fake", detail="fake")
    fake_provider = FakeProvider(CANNED_PLAN)
    monkeypatch.setattr(
        "voss.harness.cli._resolve_auth_or_die",
        lambda _pref: (fake_res, fake_provider),
    )
    monkeypatch.setattr(
        "voss.harness.cli._git_status",
        lambda _cwd: "no git",
    )


def _invoke_do_plain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    _install_fake_provider(monkeypatch)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        do_cmd,
        ["--plain", "--cwd", str(tmp_path), "echo", "plan-baseline"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"non-zero exit: {result.output}"
    return result.stdout


def test_plain_baseline_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = _invoke_do_plain(tmp_path, monkeypatch)
    baseline = _baseline_path()
    if not baseline.exists():
        if os.environ.get("VOSS_CAPTURE_BASELINE") == "1":
            baseline.parent.mkdir(parents=True, exist_ok=True)
            baseline.write_text(output)
            pytest.skip(f"wrote baseline: {baseline}")
        pytest.fail(
            f"baseline missing at {baseline}; "
            "rerun with VOSS_CAPTURE_BASELINE=1 to capture"
        )

    expected = baseline.read_text()
    assert output == expected, (
        "stdout drift vs locked baseline\n"
        f"---got---\n{output!r}\n---expected---\n{expected!r}"
    )


def test_auto_fallback_matches_plain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without --plain but non-TTY (CliRunner default) → same PlainRenderer path."""
    _install_fake_provider(monkeypatch)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        do_cmd,
        ["--cwd", str(tmp_path), "echo", "plan-baseline"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    plain_output = _invoke_do_plain(tmp_path, monkeypatch)
    assert result.stdout == plain_output


def test_json_mode_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--json must still emit NDJSON (json_mode short-circuits before plain)."""
    _install_fake_provider(monkeypatch)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        do_cmd,
        ["--json", "--cwd", str(tmp_path), "echo", "json-baseline"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert '"type":' in result.stdout
    assert '"v":' in result.stdout


def test_small_terminal_without_force_tui_does_not_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """79x24 + no force_tui → fall through to PlainRenderer; no exit(2)."""
    _install_fake_provider(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((79, 24)),
    )
    runner = CliRunner()
    result = runner.invoke(
        do_cmd,
        ["--cwd", str(tmp_path), "small-term"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0


def test_default_path_after_flip_matches_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M9-07 sanity gate: after the make_renderer default-path flip, the
    NO-flag default invocation (CliRunner is non-TTY) is still byte-identical
    to the M9-01 baseline. Locks the --plain contract through Wave 7.
    """
    _install_fake_provider(monkeypatch)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        do_cmd,
        ["--cwd", str(tmp_path), "echo", "plan-baseline"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    baseline = _baseline_path()
    if not baseline.exists():
        pytest.skip(f"baseline missing at {baseline}")
    assert result.stdout == baseline.read_text(), (
        "default-path stdout drifted from --plain baseline after the M9-07 flip"
    )


def test_force_tui_small_terminal_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VOSS_FORCE_TUI=1 + 79x24 → SystemExit(2) + locked stderr."""
    from voss.harness.tui.capability import TUIDecision

    _install_fake_provider(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VOSS_FORCE_TUI", "1")
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((79, 24)),
    )
    # CliRunner stdout is non-TTY; inject a synthetic decision surfacing the size failure.
    monkeypatch.setattr(
        "voss.harness.tui.capability.tui_should_activate",
        lambda **_kw: TUIDecision(activate=False, reason="terminal below 60x12"),
    )
    runner = CliRunner()
    result = runner.invoke(
        do_cmd,
        ["--cwd", str(tmp_path), "small-term"],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "terminal must be at least 60×12" in result.stderr
