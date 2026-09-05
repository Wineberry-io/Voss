"""Phase 4 integration tests: wizard entry into the CLI.

Covers:
  - `voss login` invokes the wizard; success exits 0, cancel exits 2.
  - `voss logout <provider>` removes a keyring entry.
  - `_resolve_auth_or_die` launches the wizard on TTY + no creds, falls back
    to the original exit-2 error on non-TTY.
  - REPL `/login` and `/login status` route to the right handler.
"""
from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from voss.harness import auth as A
from voss.harness import cli as cli_mod
from voss.harness import login_wizard


# ---------------------------------------------------------------------------
# Shared keyring isolation — same pattern as test_login_wizard.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> dict[str, str]:
    """Sandbox HOME + voss keyring helpers; clear API-key env vars."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(A, "_read_macos_keychain", lambda: None)

    store: dict[str, str] = {}
    monkeypatch.setattr(
        A, "save_voss_creds", lambda p, k: store.__setitem__(p, k) or True
    )
    monkeypatch.setattr(A, "load_voss_creds", lambda p: store.get(p))
    monkeypatch.setattr(A, "delete_voss_creds", lambda p: store.pop(p, None) is not None)
    return store


# ---------------------------------------------------------------------------
# `voss login`
# ---------------------------------------------------------------------------


def test_voss_login_non_tty_exits_2():
    """Without an interactive stdin, the command refuses to run."""
    runner = CliRunner()
    result = runner.invoke(cli_mod.login_cmd, [])
    assert result.exit_code == 2
    assert "interactive terminal" in result.output


def test_voss_login_runs_wizard_when_interactive(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_wizard(*, reason: str, **_kwargs: Any) -> A.Resolution:
        captured["reason"] = reason
        return A.Resolution(source="voss-anthropic", detail="test")

    monkeypatch.setattr(login_wizard, "stdin_is_interactive", lambda: True)
    monkeypatch.setattr(login_wizard, "run_login_wizard", fake_wizard)

    runner = CliRunner()
    result = runner.invoke(cli_mod.login_cmd, [])
    assert result.exit_code == 0, result.output
    assert captured["reason"] == "voss login"


def test_voss_login_cancel_exits_2(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(login_wizard, "stdin_is_interactive", lambda: True)
    monkeypatch.setattr(login_wizard, "run_login_wizard", lambda **_k: None)

    runner = CliRunner()
    result = runner.invoke(cli_mod.login_cmd, [])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# `voss logout`
# ---------------------------------------------------------------------------


def test_voss_logout_removes_credential(_isolate_env: dict[str, str]):
    _isolate_env["anthropic"] = "sk-ant-test"
    runner = CliRunner()
    result = runner.invoke(cli_mod.logout_cmd, ["anthropic"])
    assert result.exit_code == 0
    assert "cleared keyring entry" in result.output
    assert "anthropic" not in _isolate_env


def test_voss_logout_missing_credential_exits_1(_isolate_env: dict[str, str]):
    runner = CliRunner()
    result = runner.invoke(cli_mod.logout_cmd, ["openai"])
    assert result.exit_code == 1


def test_voss_logout_rejects_unknown_provider():
    runner = CliRunner()
    result = runner.invoke(cli_mod.logout_cmd, ["github"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# _resolve_auth_or_die — no creds entry point
# ---------------------------------------------------------------------------


def test_resolve_auth_launches_wizard_on_tty(monkeypatch: pytest.MonkeyPatch):
    """TTY + source=='none' → wizard runs and a successful resolution wins."""
    monkeypatch.setattr(login_wizard, "stdin_is_interactive", lambda: True)
    monkeypatch.setattr(
        login_wizard,
        "run_login_wizard",
        lambda **_k: A.Resolution(source="env-anthropic", detail="from wizard"),
    )

    res, provider = cli_mod._resolve_auth_or_die("auto")
    assert res.source == "env-anthropic"
    assert provider is not None


def test_resolve_auth_non_tty_skips_wizard(monkeypatch: pytest.MonkeyPatch):
    """Non-TTY callers (CI / pipes) still get the original exit-2 error."""
    monkeypatch.setattr(login_wizard, "stdin_is_interactive", lambda: False)

    def boom(**_kwargs):
        raise AssertionError("wizard should not run when stdin is not a TTY")

    monkeypatch.setattr(login_wizard, "run_login_wizard", boom)

    with pytest.raises(SystemExit) as ex:
        cli_mod._resolve_auth_or_die("auto")
    assert ex.value.code == 2


def test_resolve_auth_tty_but_wizard_cancelled(monkeypatch: pytest.MonkeyPatch):
    """TTY + wizard returns None → still exits 2 with the error message."""
    monkeypatch.setattr(login_wizard, "stdin_is_interactive", lambda: True)
    monkeypatch.setattr(login_wizard, "run_login_wizard", lambda **_k: None)

    with pytest.raises(SystemExit) as ex:
        cli_mod._resolve_auth_or_die("auto")
    assert ex.value.code == 2
