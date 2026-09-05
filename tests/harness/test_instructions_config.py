"""S0.6 — `[instructions]` and `[billing]` config sections."""
from __future__ import annotations

import pytest

from voss.harness import config as hc


@pytest.fixture
def xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def _write(xdg, text: str) -> None:
    p = hc.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_instructions_defaults(xdg) -> None:
    assert hc.get_instructions_config() == {
        "enabled": True, "budget_tokens": 4000, "per_file_tokens": 2000, "read_global": False,
    }


def test_instructions_overrides(xdg) -> None:
    _write(xdg, "[instructions]\nenabled = true\nbudget_tokens = 6000\nper_file_tokens = 3000\nread_global = true\n")
    assert hc.get_instructions_config() == {
        "enabled": True, "budget_tokens": 6000, "per_file_tokens": 3000, "read_global": True,
    }


def test_instructions_bad_values_warn_and_default(xdg) -> None:
    _write(xdg, "[instructions]\nbudget_tokens = nope\nread_global = maybe\n")
    with pytest.warns(RuntimeWarning):
        cfg = hc.get_instructions_config()
    assert cfg["budget_tokens"] == 4000
    assert cfg["read_global"] is False


def test_billing_defaults(xdg) -> None:
    assert hc.get_provider_billing("claude-agent") == "subscription"
    assert hc.get_provider_billing("codex-oauth") == "subscription"
    assert hc.get_provider_billing("env-anthropic") == "metered"
    assert hc.get_provider_billing("voss-openai") == "metered"
    assert hc.get_provider_billing("something-else") == "unknown"


def test_billing_override(xdg) -> None:
    _write(xdg, '[billing]\nclaude-agent = "metered"\nollama = "subscription"\n')
    assert hc.get_provider_billing("claude-agent") == "metered"
    assert hc.get_provider_billing("ollama") == "subscription"


def test_billing_bad_value_warns(xdg) -> None:
    _write(xdg, '[billing]\nclaude-agent = "free"\n')
    with pytest.warns(RuntimeWarning):
        assert hc.get_provider_billing("claude-agent") == "subscription"
