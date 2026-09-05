"""Phase 2 tests for the interactive login wizard.

All external IO is injected, so no real terminal, subprocess, or filesystem
access happens. The wizard's job is to route the user to one of three credential
paths and return a Resolution (or None if they quit).
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console

from voss.harness import auth as A
from voss.harness import login_wizard as W


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ScriptedInput:
    """Returns answers in order; raises if the wizard asks more than scripted."""

    def __init__(self, answers: list[str]):
        self._answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._answers:
            raise AssertionError(f"unexpected prompt: {prompt!r}")
        return self._answers.pop(0)


def _no_console() -> Console:
    """A Console that writes to an in-memory buffer (silent under pytest)."""
    return Console(file=io.StringIO(), force_terminal=False, no_color=True)


@pytest.fixture(autouse=True)
def _isolate_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Replace voss credential helpers with a per-test in-memory dict.

    Avoids hitting the real OS keychain in tests; save/load stay coherent so
    `resolve("api")` returns a `voss-*` source when the wizard's apikey branch
    persists a key.
    """
    store: dict[str, str] = {}

    def fake_save(provider: str, key: str) -> bool:
        store[provider] = key
        return True

    def fake_load(provider: str):
        return store.get(provider)

    monkeypatch.setattr(A, "save_voss_creds", fake_save)
    monkeypatch.setattr(A, "load_voss_creds", fake_load)
    return store


def _claude_resolution() -> A.Resolution:
    return A.Resolution(
        source="claude-agent",
        detail="test",
        anthropic_oauth=A.AnthropicOAuthCreds(
            access_token="x",
            refresh_token="y",
            expires_at_ms=10**13,
            subscription_type="max",
        ),
    )


# ---------------------------------------------------------------------------
# Quit
# ---------------------------------------------------------------------------


def test_quit_returns_none():
    inp = ScriptedInput(["q"])
    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=lambda _p: "",
        detect=lambda _name: None,
        spawn=lambda _argv: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is None


def test_eof_at_menu_quits():
    def raise_eof(_p: str) -> str:
        raise EOFError

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=raise_eof,
        secret_input_fn=lambda _p: "",
        detect=lambda _name: None,
        spawn=lambda _argv: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is None


# ---------------------------------------------------------------------------
# Claude branch
# ---------------------------------------------------------------------------


def test_claude_branch_success():
    spawn_calls: list[list[str]] = []
    inp = ScriptedInput(["1"])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=lambda _p: "",
        detect=lambda name: Path("/usr/local/bin/claude") if name == "claude" else None,
        spawn=lambda argv: (spawn_calls.append(argv) or 0),
        waiter=lambda _provider, **_k: _claude_resolution(),
    )
    assert res is not None
    assert res.source == "claude-agent"
    assert spawn_calls == [["/usr/local/bin/claude"]]


def test_claude_branch_cli_missing_loops_back():
    """No `claude` on PATH → prints install hint and loops back to the menu."""
    inp = ScriptedInput(["1", "q"])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=lambda _p: "",
        detect=lambda _name: None,
        spawn=lambda _argv: pytest.fail("spawn should not run when CLI missing"),
        waiter=lambda _p, **_k: pytest.fail("waiter should not run when CLI missing"),
    )
    assert res is None
    # The wizard asked twice: once for the first menu, once after the failure.
    assert len(inp.prompts) == 2


def test_claude_branch_timeout_loops_back():
    """Spawn returns but waiter returns None → loop, then user quits."""
    inp = ScriptedInput(["1", "q"])
    spawn_calls = 0

    def fake_spawn(_argv: list[str]) -> int:
        nonlocal spawn_calls
        spawn_calls += 1
        return 0

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=lambda _p: "",
        detect=lambda _name: Path("/x/claude"),
        spawn=fake_spawn,
        waiter=lambda _p, **_k: None,
    )
    assert res is None
    assert spawn_calls == 1


# ---------------------------------------------------------------------------
# Codex branch
# ---------------------------------------------------------------------------


def test_codex_branch_success():
    spawn_calls: list[list[str]] = []
    inp = ScriptedInput(["2"])
    codex_res = A.Resolution(
        source="codex",
        detail="test",
        openai_api_key="sk-test",
    )

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=lambda _p: "",
        detect=lambda name: Path("/usr/local/bin/codex") if name == "codex" else None,
        spawn=lambda argv: (spawn_calls.append(argv) or 0),
        waiter=lambda _p, **_k: codex_res,
    )
    assert res is codex_res
    assert spawn_calls == [["/usr/local/bin/codex", "login"]]


# ---------------------------------------------------------------------------
# API-key branch
# ---------------------------------------------------------------------------


def test_apikey_anthropic_persists_to_keyring(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    saved: dict[str, str] = {}
    monkeypatch.setattr(
        A,
        "save_voss_creds",
        lambda provider, key: saved.__setitem__(provider, key) or True,
    )
    monkeypatch.setattr(A, "load_voss_creds", lambda provider: saved.get(provider))

    inp = ScriptedInput(["3", "1"])  # menu → apikey → Anthropic
    secret = ScriptedInput(["sk-ant-test-key"])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=secret,
        detect=lambda _n: None,
        spawn=lambda _a: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is not None
    assert res.source == "voss-anthropic"
    assert saved == {"anthropic": "sk-ant-test-key"}


def test_apikey_openai_persists_to_keyring(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    saved: dict[str, str] = {}
    monkeypatch.setattr(
        A,
        "save_voss_creds",
        lambda provider, key: saved.__setitem__(provider, key) or True,
    )
    monkeypatch.setattr(A, "load_voss_creds", lambda provider: saved.get(provider))

    inp = ScriptedInput(["3", "2"])
    secret = ScriptedInput(["sk-openai-test-key"])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=secret,
        detect=lambda _n: None,
        spawn=lambda _a: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is not None
    assert res.source == "voss-openai"
    assert saved == {"openai": "sk-openai-test-key"}


def test_apikey_keyring_unavailable_falls_back_to_env(monkeypatch: pytest.MonkeyPatch):
    """No keyring backend → wizard sets env var, still returns a usable resolution."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(A, "save_voss_creds", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(A, "load_voss_creds", lambda _p: None)

    inp = ScriptedInput(["3", "1"])
    secret = ScriptedInput(["sk-ant-fallback"])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=secret,
        detect=lambda _n: None,
        spawn=lambda _a: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is not None
    assert res.source == "env-anthropic"
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-fallback"


def test_apikey_empty_loops_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    inp = ScriptedInput(["3", "1", "q"])  # apikey → Anthropic → empty → q
    secret = ScriptedInput([""])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=secret,
        detect=lambda _n: None,
        spawn=lambda _a: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is None


def test_apikey_wrong_prefix_still_accepted(monkeypatch: pytest.MonkeyPatch):
    """Prefix mismatch warns but does not block — user may have a non-stdrd key."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    inp = ScriptedInput(["3", "1"])
    secret = ScriptedInput(["weird-key-no-prefix"])

    res = W.run_login_wizard(
        console=_no_console(),
        input_fn=inp,
        secret_input_fn=secret,
        detect=lambda _n: None,
        spawn=lambda _a: 0,
        waiter=lambda _p, **_k: None,
    )
    assert res is not None
    # Stored via the autouse keyring stub → resolves as voss-anthropic.
    assert res.source == "voss-anthropic"
