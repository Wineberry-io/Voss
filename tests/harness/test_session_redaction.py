"""Lock the SessionRecord redaction guarantee (D-17).

If a future change adds a SessionRecord field that holds provider creds or
adds a serialization path that bypasses the dataclass, these tests fail.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from voss_runtime import EpisodicMemory

from voss.harness import session as session_store
from voss.harness.session import RunRecord, SessionRecord


@pytest.fixture
def state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state" / "voss" / "sessions"


class TestSchemaAllowlist:
    def test_saved_json_has_exactly_schema_keys(self, state_dir, tmp_path):
        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        history.add("hello", role="user")
        path = session_store.save(record, history)
        data = json.loads(path.read_text())
        expected = {
            "id", "name", "cwd", "model", "started_at", "updated_at",
            "total_cost_usd", "turns", "runs",
            # M9-06 fork lineage (additive Optional, default None).
            "parent_id", "parent_turn_index",
            # S0.5 instruction-file bundle identity (paths + hash only, never text).
            "instructions_hash", "instructions_files",
        }
        assert set(data.keys()) == expected

    def test_no_credentials_keys_at_top_level(self, state_dir, tmp_path):
        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        path = session_store.save(record, history)
        text = path.read_text()
        forbidden_top_level_keys = (
            '"access_token"', '"refresh_token"', '"api_key"',
            '"Authorization"', '"anthropic-beta"', '"oauth_token"',
            '"credentials"', '"provider"', '"headers"',
        )
        for key in forbidden_top_level_keys:
            assert key not in text, f"forbidden key present: {key}"

    def test_secret_patterns_absent_from_clean_session(self, state_dir, tmp_path):
        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        history.add("summarize this repo", role="user")
        history.add("the repo is a Python harness.", role="assistant")
        path = session_store.save(record, history)
        text = path.read_text()
        # Creds-shaped patterns the harness itself would never put in a
        # transcript. Their presence means the schema allowlist broke.
        secret_patterns = (
            "sk-ant-", "sk-proj-", "Bearer ",
            "oauth_token", "access_token", "Authorization",
        )
        for pat in secret_patterns:
            assert pat not in text, f"secret pattern leaked: {pat!r}"


class TestUserPromptsArePassthrough:
    """User prompt content is intentionally not redacted — the user typed it."""

    def test_user_prompt_with_secret_shape_is_preserved(self, state_dir, tmp_path):
        record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        history.add("debug this: my key was sk-test-DEADBEEF", role="user")
        path = session_store.save(record, history)
        text = path.read_text()
        assert "sk-test-DEADBEEF" in text  # user typed it; we preserve it


class TestDocstringFreezesGuarantee:
    def test_module_docstring_mentions_redaction_guarantee(self):
        assert session_store.__doc__ is not None
        assert "Redaction guarantee" in session_store.__doc__


class TestRunRecordRedaction:
    def test_run_record_top_level_keys(self):
        rec = RunRecord(id="t", started_at="t0", ended_at="t1")
        expected = {
            "id",
            "started_at",
            "ended_at",
            "goal",
            "plan",
            "inspected",
            "changed",
            "avoided",
            "assumptions",
            "decisions",
            "risks",
            "validation",
            "failures",
            "diff_summary",
            "follow_ups",
            "cost_usd",
            # T1-01: additive iteration-loop fields. None carry credentials.
            "iterations",
            "iteration_count",
            "exit_reason",
            "iteration_total_prompt_tokens",
            "iteration_total_completion_tokens",
            # M15-05: skill audit events (additive, no credentials).
            "skill_events",
            "scope_denials",
            # V1-04: capability-invocation audit (additive; args redacted via
            # telemetry.redact_tool_args or omitted, no credentials).
            "capability_invocations",
            # V12 VSAFE-05: factory-fallback audit (additive; args redacted via
            # telemetry.redact_tool_args or omitted, no credentials).
            "factory_fallbacks",
            # S0.5: instruction bundle identity (paths + hash, never file text).
            "instructions_hash", "instructions_files",
        }
        assert set(asdict(rec).keys()) == expected
        assert len(dataclasses.fields(RunRecord)) == 27

    def test_run_record_no_secret_patterns(self, state_dir, tmp_path):
        record = SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
        history = EpisodicMemory(capacity=10)
        history.add("summarize", role="user")
        run = RunRecord(
            id="t1",
            started_at="t0",
            ended_at="t1",
            goal="summarize",
            inspected=["src/a.py"],
        )
        record.runs.append(asdict(run))
        path = session_store.save(record, history)
        text = path.read_text()
        secret_patterns = (
            "sk-ant-",
            "sk-proj-",
            "Bearer ",
            "oauth_token",
            "access_token",
            "Authorization",
        )
        for pat in secret_patterns:
            assert pat not in text, f"secret pattern leaked: {pat!r}"
