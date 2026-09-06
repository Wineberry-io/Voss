"""End-to-end happy path for M1.

Drives `voss do` with a mocked provider, then exercises sessions save/list/load.
Asserts:
  - voss do runs to completion in mode plan without crashing.
  - the saved session JSON contains no provider creds (D-16 lockdown).
  - voss sessions lists the new session.
  - SessionRecord.load rehydrates cwd / transcript.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from voss.harness import session as session_store
from voss.harness.cli import do_cmd, sessions_cmd


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key-for-tests")
    return tmp_path


@pytest.fixture
def mock_provider(monkeypatch):
    """Stub out the provider so no network call happens.

    `ProviderResponse` is the actual class name in voss_runtime.providers.base.
    The `model` field is REQUIRED — must be passed.
    """
    from voss.harness.agent import Plan, ToolCall
    from voss_runtime.providers.base import ProviderResponse

    plan = Plan(
        rationale="trivial summary",
        steps=[ToolCall(name="fs_glob", args={"pattern": "*.md"}, why="find docs")],
        confidence=0.9,
        final_when_done="repo summary: {{step_0}}",
    )
    resp = ProviderResponse(
        text="",
        model="claude-sonnet-4-20250514",
        prompt_tokens=10,
        completion_tokens=10,
        cost_usd=0.001,
        parsed=plan,
    )

    async def fake_complete(*args, **kwargs):
        return resp

    fake = MagicMock()
    fake.complete = AsyncMock(side_effect=fake_complete)
    monkeypatch.setattr(
        "voss.harness.cli._resolve_auth_or_die",
        lambda pref: (MagicMock(source="env-anthropic", detail="test"), fake),
    )
    return fake


class TestDoHappyPath:
    def test_voss_do_runs_in_plan_mode_without_crash(
        self, isolated_env, mock_provider, tmp_path
    ):
        (tmp_path / "README.md").write_text("# test repo\n")
        result = CliRunner().invoke(
            do_cmd,
            ["summarize", "this", "repo", "--cwd", str(tmp_path), "--yes"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"voss do failed: {result.output}"


class TestSessionsLifecycle:
    def test_save_list_and_load(self, isolated_env, tmp_path):
        from voss_runtime import EpisodicMemory

        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        history.add("summarize", role="user")
        history.add("ok", role="assistant")
        path = session_store.save(record, history)
        assert path.exists()

        records = session_store.list_sessions(cwd=tmp_path)
        assert any(r.id == record.id for r in records)

        loaded_record, loaded_history = session_store.load(record.id[:8], cwd=tmp_path)
        assert loaded_record.id == record.id
        assert loaded_record.cwd == str(tmp_path.resolve())
        assert loaded_history.last(2)[0]["content"] == "summarize"

    def test_session_json_has_no_creds(self, isolated_env, tmp_path):
        from voss_runtime import EpisodicMemory

        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        path = session_store.save(record, history)
        text = path.read_text()
        for forbidden in (
            "access_token", "refresh_token", "Bearer ",
            "sk-ant-", "sk-proj-",
        ):
            assert forbidden not in text, f"creds-shaped leak: {forbidden}"


class TestSessionsCmd:
    def test_sessions_lists_saved(self, isolated_env, tmp_path, monkeypatch):
        from voss_runtime import EpisodicMemory

        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        session_store.save(record, history)

        # sessions_cmd reads from Path.cwd() — chdir into the project dir.
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(sessions_cmd, [])
        assert result.exit_code == 0
        assert record.id[:8] in result.output
