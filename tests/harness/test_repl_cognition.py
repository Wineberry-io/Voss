"""
Tests covering COG requirements:
COG-REPL-01, COG-REPL-02, COG-REPL-03, COG-REPL-04, COG-REPL-05
"""
from __future__ import annotations

import io
import json

from rich.console import Console

from voss.harness.agent import (
    COGNITION_BUDGET_TOKENS,
    _compose_cognition_prompt,
)
from voss.harness.cognition import CognitionBundle
from voss.harness.cognition_schemas import ConstraintRule, ConstraintsConfig
from voss.harness.render import JsonRenderer, TtyRenderer


def test_cognition_status_line_tty() -> None:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120, highlight=False)
    r = TtyRenderer(console=console)
    r.show_cognition(architecture_tokens=1200, constraints_count=2)
    out = buf.getvalue()
    assert "cognition: architecture (1.2k) + 2 constraints" in out


def test_cognition_loaded_ndjson_event(capsys) -> None:
    r = JsonRenderer()
    r.show_cognition(
        architecture_tokens=1200,
        constraints_count=2,
        plans_loaded=0,
        decisions_loaded=0,
    )
    out = capsys.readouterr().out.strip()
    evt = json.loads(out)
    assert evt == {
        "v": 1,
        "type": "cognition_loaded",
        "architecture_tokens": 1200,
        "constraints_count": 2,
        "plans_loaded": 0,
        "decisions_loaded": 0,
    }


def test_cognition_overflow_truncates_constraints(capsys) -> None:
    # Bundle whose architecture is "large" by the stub token counter.
    bundle = CognitionBundle(
        initialized=True,
        architecture_md="ARCH BODY\n" * 200,
        architecture_tokens=8000,
        constraints=ConstraintsConfig(
            rules=[ConstraintRule(forbid=["foo"]), ConstraintRule(custom="bar")]
        ),
    )

    # Stub token counter: report 8000 unconditionally → triggers overflow.
    def stub_tok(text: str, *, model: str) -> int:
        return 8000

    r = JsonRenderer()
    text = _compose_cognition_prompt(
        bundle, model="m", token_count_fn=stub_tok, renderer=r
    )

    # Constraints dropped from prompt entirely.
    assert "## Constraints" not in text
    assert "constraints truncated due to budget" in text
    # Architecture remains.
    assert "ARCH BODY" in text

    out = capsys.readouterr().out.strip()
    evt = json.loads(out)
    assert evt["type"] == "cognition_overflow"
    assert evt["architecture_tokens"] == 8000
    assert evt["budget"] == COGNITION_BUDGET_TOKENS


def test_drift_hint_printed_non_blocking(monkeypatch, tmp_path, capsys) -> None:
    """Stale frontmatter → REPL banner prints drift hint + exits cleanly on /exit."""
    from datetime import datetime, timedelta, timezone

    from voss_runtime import EpisodicMemory

    from voss.harness import session as session_store
    from voss.harness.cli import _run_repl

    # Build a "stale" cognition: analyzed 30 days ago, current HEAD, file count
    # left at 0 so file delta won't dominate the reason.
    voss = tmp_path / ".voss"
    voss.mkdir()
    stale_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    (voss / "architecture.md").write_text(
        "---\n"
        "git_head: deadbeef\n"
        f"analyzed_at: {stale_iso}\n"
        "file_count: 0\n"
        "analyzer_version: 1\n"
        "---\n"
        "# Arch\n"
    )

    class _NoopProvider:
        async def complete(self, **_):
            raise AssertionError("provider.complete should not be called")

        def count_tokens(self, **_):
            return 1

    record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-test")
    lines = iter(["/exit"])
    monkeypatch.setattr("builtins.input", lambda *_: next(lines))

    _run_repl(
        cwd=tmp_path,
        json_mode=False,
        mode="plan",
        history=EpisodicMemory(capacity=10),
        record=record,
        provider=_NoopProvider(),
        auth_detail="stub",
    )
    out = capsys.readouterr().out
    assert "cognition stale" in out
    assert "/analyze to refresh" in out


def test_bad_yaml_loud_failure(git_repo) -> None:
    from voss.harness.cognition import load

    voss = git_repo / ".voss"
    voss.mkdir()
    (voss / "architecture.md").write_text(
        "---\ngit_head: abc\nanalyzed_at: 2026-05-10T00:00:00+00:00\n"
        "file_count: 1\nanalyzer_version: 1\n---\n# Arch\n"
    )
    (voss / "project.json").write_text(
        '{"name": "t", "primary_language": "python"}'
    )
    (voss / "constraints.yml").write_text("rules: [\n")  # malformed YAML

    b = load(git_repo)
    assert b.load_errors, "load_errors should be populated on malformed YAML"
    assert any("constraints.yml" in e for e in b.load_errors)
