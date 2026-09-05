"""Wave 1 + Wave 3 tests for voss/harness/cognition.py.

Wave 1: COG-01, COG-02, COG-07 (load, drift, repo.idx, gitignore).
Wave 3 (M2-04): hybrid bootstrap helpers, /save-plan, analyze skill.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml as _yaml
from voss_runtime.providers.base import ProviderResponse

from voss.harness.agent import Plan, ToolCall
from voss.harness.cognition import (
    FRONTMATTER_RE,
    _render_steps_for_plan_md,
    append_gitignore_line_idempotent,
    build_bootstrap_inventory,
    build_repo_idx,
    detect_primary_language,
    drift_check,
    init_voss_stubs,
    load,
    reserve_filename,
    slug,
    write_plan_md,
    write_voss_gitignore,
)
from voss.harness.cognition_schemas import (
    ConstraintsConfig,
    PermissionsConfig,
    ProjectMeta,
    ValidationConfig,
)


def _arch_content(inventory: dict) -> str:
    """Build well-formed architecture.md matching inventory frontmatter."""
    return (
        "---\n"
        f"git_head: {inventory['git_head']}\n"
        f"analyzed_at: {inventory['analyzed_at']}\n"
        f"file_count: {inventory['file_count']}\n"
        "analyzer_version: 1\n"
        "---\n\n"
        "# Project\n\nsmall test project.\n\n"
        "## Primary language\n\npython\n\n"
        "## Entry points\n\n- (none)\n\n"
        "## Module map\n\n- src/\n\n"
        "## Key dependencies\n\n- none\n\n"
        "## Testing approach\n\npytest\n"
    )


class _StubAnalyzeProvider:
    """Stub with stream() (iteration-loop planning) + complete() (record_run)."""

    def __init__(self, architecture_content: str):
        self.architecture_content = architecture_content
        self.calls: list[dict] = []
        self._stream_index = 0

    def _build_plan(self):
        from voss.harness.agent import Plan as _Plan

        return _Plan(
            rationale="bootstrap architecture.md",
            steps=[
                ToolCall(
                    name="fs_write",
                    args={
                        "path": ".voss/architecture.md",
                        "content": self.architecture_content,
                    },
                    why="bootstrap",
                )
            ],
            confidence=0.95,
            final_when_done="wrote .voss/architecture.md",
        )

    async def complete(
        self,
        *,
        messages,
        model,
        response_format=None,
        tools=None,
        temperature=1.0,
        max_tokens=None,
        timeout=None,
    ) -> ProviderResponse:
        from voss.harness.agent import Plan as _Plan
        from voss.harness.agent import RunSemantics as _RunSemantics

        self.calls.append({"schema": response_format})

        if response_format is _Plan:
            plan = self._build_plan()
            return ProviderResponse(
                text=plan.model_dump_json(),
                model=model,
                prompt_tokens=10,
                completion_tokens=10,
                cost_usd=0.0,
                raw={"stub": True},
                parsed=plan,
            )
        if response_format is _RunSemantics:
            sem = _RunSemantics(goal="bootstrap", decisions=[])
            return ProviderResponse(
                text=sem.model_dump_json(),
                model=model,
                prompt_tokens=5,
                completion_tokens=5,
                cost_usd=0.0,
                raw={"stub": True},
                parsed=sem,
            )
        return ProviderResponse(
            text="", model=model, prompt_tokens=0, completion_tokens=0,
            cost_usd=0.0, raw={}, parsed=None,
        )

    def stream(self, **kwargs):
        from voss.harness.agent import Plan as _Plan
        from voss.harness.providers import Done, ParsedPlan, TextDelta, Usage

        self.calls.append({"schema": kwargs.get("response_format")})
        idx = self._stream_index
        self._stream_index += 1
        if idx == 0:
            plan_to_emit = self._build_plan()
        else:
            plan_to_emit = _Plan(
                rationale="(synthetic done)",
                steps=[],
                confidence=0.95,
                final_when_done="wrote .voss/architecture.md",
            )

        async def _gen():
            yield TextDelta(text="…")
            yield ParsedPlan(plan=plan_to_emit)
            yield Usage(prompt_tokens=10, completion_tokens=10, cost_usd=0.0)
            yield Done(stop_reason="end_turn")

        return _gen()

    def count_tokens(self, *, text: str, model: str) -> int:
        return max(len(text) // 4, 1)


def _run_analyze(cwd: Path, inventory: dict) -> None:
    from voss_runtime import EpisodicMemory

    from voss.harness import session as session_store
    from voss.harness.permissions import PermissionGate
    from voss.harness.render import PlainRenderer
    from voss.harness.skills.analyze import run as analyze_run
    from voss.harness.tools import make_toolset

    record = session_store.SessionRecord.new(cwd=cwd, model="claude-test")
    analyze_run(
        cwd=cwd,
        provider=_StubAnalyzeProvider(_arch_content(inventory)),
        history=EpisodicMemory(capacity=10),
        record=record,
        renderer=PlainRenderer(),
        tools=make_toolset(cwd),
        gate=PermissionGate(auto_yes=True),
    )


# ---------------------------------------------------------------------------
# Hybrid bootstrap helpers (Wave 3 / M2-04)
# ---------------------------------------------------------------------------


def test_detect_primary_language_python(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    (tmp_path / "c.py").write_text("z = 3\n")
    (tmp_path / "notes.md").write_text("hi\n")
    assert detect_primary_language(tmp_path) == "python"


def test_init_voss_stubs_creates_valid_files(tmp_path: Path) -> None:
    inv = build_bootstrap_inventory(tmp_path)
    results = init_voss_stubs(tmp_path, inventory=inv)
    assert set(results.keys()) == {
        "project.json",
        "constraints.yml",
        "permissions.yml",
        "validation.yml",
    }
    assert all(results.values())

    pj = json.loads((tmp_path / ".voss" / "project.json").read_text())
    ProjectMeta.model_validate(pj)
    ConstraintsConfig.model_validate(_yaml.safe_load((tmp_path / ".voss" / "constraints.yml").read_text()) or {})
    PermissionsConfig.model_validate(_yaml.safe_load((tmp_path / ".voss" / "permissions.yml").read_text()) or {})
    ValidationConfig.model_validate(_yaml.safe_load((tmp_path / ".voss" / "validation.yml").read_text()) or {})


def test_init_voss_stubs_preserve_if_exists(tmp_path: Path) -> None:
    (tmp_path / ".voss").mkdir()
    pre = "rules:\n  - forbid: [foo]\n"
    (tmp_path / ".voss" / "constraints.yml").write_text(pre)

    inv = build_bootstrap_inventory(tmp_path)
    results = init_voss_stubs(tmp_path, inventory=inv)

    assert results["constraints.yml"] is False
    assert results["project.json"] is True
    assert (tmp_path / ".voss" / "constraints.yml").read_text() == pre


def test_voss_gitignore_autogenerated(tmp_path: Path) -> None:
    assert write_voss_gitignore(tmp_path) is True
    body = (tmp_path / ".voss" / ".gitignore").read_text()
    assert "sessions/" in body
    assert write_voss_gitignore(tmp_path) is False


# ---------------------------------------------------------------------------
# /analyze end-to-end via stub provider
# ---------------------------------------------------------------------------


def test_analyze_writes_architecture_md(git_repo: Path) -> None:
    inv = build_bootstrap_inventory(git_repo)
    _run_analyze(git_repo, inv)

    arch = git_repo / ".voss" / "architecture.md"
    assert arch.exists()
    text = arch.read_text()
    assert "# Project" in text
    assert "## Module map" in text


def test_architecture_md_frontmatter_well_formed(git_repo: Path) -> None:
    inv = build_bootstrap_inventory(git_repo)
    _run_analyze(git_repo, inv)

    text = (git_repo / ".voss" / "architecture.md").read_text()
    m = FRONTMATTER_RE.match(text)
    assert m, "frontmatter did not match"
    fm = _yaml.safe_load(m.group(1))
    assert set(fm.keys()) == {"git_head", "analyzed_at", "file_count", "analyzer_version"}
    assert fm["analyzer_version"] == 1


def test_analyze_emits_project_root_gitignore_append(tmp_path: Path) -> None:
    g = tmp_path / ".gitignore"
    g.write_text("# existing\nbuild/\n")
    assert append_gitignore_line_idempotent(g, ".voss-cache/") is True
    assert append_gitignore_line_idempotent(g, ".voss-cache/") is False
    body = g.read_text()
    assert body.count(".voss-cache/") == 1
    assert "build/" in body


# ---------------------------------------------------------------------------
# /save-plan (COG-04)
# ---------------------------------------------------------------------------


def _sample_plan(rationale: str = "refactor X for clarity") -> Plan:
    return Plan(
        rationale=rationale,
        steps=[
            ToolCall(
                name="fs_read",
                args={"path": "cli.py", "limit": 10},
                why="locate symbol",
            )
        ],
        confidence=0.9,
        final_when_done="done",
    )


def test_save_plan_writes_plan_md(tmp_path: Path) -> None:
    plan = _sample_plan()
    path = write_plan_md(
        tmp_path, plan, session_id="sess-1", model="claude-opus-4-7"
    )
    assert path.parent == tmp_path / ".voss" / "plans"
    text = path.read_text()
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    fm = _yaml.safe_load(text[4:end])
    assert set(fm.keys()) == {
        "id", "status", "related_session", "model", "confidence", "created_at",
    }
    assert fm["status"] == "open"
    assert fm["related_session"] == "sess-1"
    assert fm["model"] == "claude-opus-4-7"
    assert f"{float(fm['confidence']):.2f}" == "0.90"
    assert fm["id"] == path.stem


def test_save_plan_no_op_when_no_prior_plan(tmp_path: Path, capsys) -> None:
    from voss.harness import session as session_store
    from voss.harness.cli import _handle_save_plan

    record = session_store.SessionRecord.new(cwd=tmp_path, model="claude-test")
    _handle_save_plan(cwd=tmp_path, last_plan=None, record=record, line="/save-plan")
    out = capsys.readouterr()
    assert "no plan to save yet" in out.err
    assert not (tmp_path / ".voss" / "plans").exists()


def test_save_plan_collision_appends_suffix(tmp_path: Path) -> None:
    plan = _sample_plan()
    p1 = write_plan_md(tmp_path, plan, session_id="s", model="m")
    p2 = write_plan_md(tmp_path, plan, session_id="s", model="m")
    assert p1 != p2
    assert p2.stem.endswith("-2")


def test_save_plan_step_serialization_kwargs_style(tmp_path: Path) -> None:
    plan = _sample_plan()
    path = write_plan_md(tmp_path, plan, session_id="s", model="m")
    body = path.read_text()
    # JSON-compact via json.dumps separators=(',', ':')
    assert '- fs_read(path="cli.py", limit=10) — locate symbol' in body


def test_render_steps_kwargs_style_unit() -> None:
    plan = _sample_plan()
    out = _render_steps_for_plan_md(plan.steps)
    assert out == '- fs_read(path="cli.py", limit=10) — locate symbol'


@pytest.mark.skip(reason="Wave 2 — pending plan M2-04")
def test_analyze_writes_project_json() -> None:
    pass


def test_load_parses_frontmatter(git_repo: Path) -> None:
    voss = git_repo / ".voss"
    voss.mkdir()
    (voss / "architecture.md").write_text(
        "---\n"
        "git_head: abc\n"
        "analyzed_at: 2026-05-10T00:00:00+00:00\n"
        "file_count: 5\n"
        "analyzer_version: 1\n"
        "---\n"
        "# Arch\n"
    )

    b = load(git_repo)
    assert b.initialized is True
    assert b.architecture_md == "# Arch\n"
    assert b.architecture_frontmatter is not None
    assert b.architecture_frontmatter.git_head == "abc"
    assert b.architecture_frontmatter.file_count == 5


def test_drift_commits_threshold(git_repo: Path) -> None:
    voss = git_repo / ".voss"
    voss.mkdir()
    # Use an unreachable SHA — 40-char hex but not in repo history
    unreachable_sha = "deadbeef" * 5
    now_iso = datetime.now(timezone.utc).isoformat()
    (voss / "architecture.md").write_text(
        f"---\n"
        f"git_head: {unreachable_sha}\n"
        f"analyzed_at: {now_iso}\n"
        f"file_count: 1\n"
        f"analyzer_version: 1\n"
        f"---\n"
        f"# Arch\n"
    )

    b = load(git_repo)
    assert b.architecture_frontmatter is not None
    result = drift_check(git_repo, b.architecture_frontmatter)
    assert result.is_stale is True
    reason_lower = result.reason.lower()
    assert "head" in reason_lower or "commit" in reason_lower


def test_drift_file_count_threshold(git_repo: Path) -> None:
    # Add a second file and commit it
    (git_repo / "second.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "more"],
        cwd=str(git_repo),
        check=True,
        capture_output=True,
    )

    # Get the first commit's SHA (HEAD~1)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        cwd=str(git_repo),
        capture_output=True,
        text=True,
        check=True,
    )
    first_sha = result.stdout.strip()

    voss = git_repo / ".voss"
    voss.mkdir()
    now_iso = datetime.now(timezone.utc).isoformat()
    # frontmatter says 1 file, but repo now has 2
    (voss / "architecture.md").write_text(
        f"---\n"
        f"git_head: {first_sha}\n"
        f"analyzed_at: {now_iso}\n"
        f"file_count: 1\n"
        f"analyzer_version: 1\n"
        f"---\n"
        f"# Arch\n"
    )

    b = load(git_repo)
    assert b.architecture_frontmatter is not None
    drift = drift_check(git_repo, b.architecture_frontmatter)
    assert drift.is_stale is True
    assert drift.file_count_delta > 0


def test_drift_days_threshold(git_repo: Path) -> None:
    # Get current HEAD
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(git_repo),
        capture_output=True,
        text=True,
        check=True,
    )
    current_head = result.stdout.strip()

    # Get current file count
    ls_result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(git_repo),
        capture_output=True,
        text=True,
        check=True,
    )
    current_count = len(ls_result.stdout.splitlines())

    # analyzed_at is 10 days ago
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    voss = git_repo / ".voss"
    voss.mkdir()
    (voss / "architecture.md").write_text(
        f"---\n"
        f"git_head: {current_head}\n"
        f"analyzed_at: {ten_days_ago}\n"
        f"file_count: {current_count}\n"
        f"analyzer_version: 1\n"
        f"---\n"
        f"# Arch\n"
    )

    b = load(git_repo)
    assert b.architecture_frontmatter is not None
    drift = drift_check(git_repo, b.architecture_frontmatter)
    assert drift.is_stale is True
    assert "d old" in drift.reason


def test_plan_filename_and_frontmatter(tmp_path: Path) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = reserve_filename(tmp_path / "plans", slug("My Plan Title"))
    assert p.name.startswith(today + "-")
    assert p.name.endswith("-my-plan-title.md")


def test_reserve_filename_collision(tmp_path: Path) -> None:
    d = tmp_path / "plans"
    d.mkdir()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = slug("collision test")

    # Create the first candidate
    first = d / f"{today}-{base}.md"
    first.write_text("exists\n")

    p2 = reserve_filename(d, base)
    assert p2.name == f"{today}-{base}-2.md"

    # Create the second candidate too
    p2.write_text("exists\n")
    p3 = reserve_filename(d, base)
    assert p3.name == f"{today}-{base}-3.md"


def test_decision_frontmatter(tmp_path: Path) -> None:
    """COG-06: decisions/*.md frontmatter has the 5 required keys."""
    import yaml as _yaml
    from voss.harness.recorder import write_decisions_md
    from voss.harness.session import RunRecord

    run = RunRecord(
        id="r1",
        started_at="t0",
        ended_at="t1",
        decisions=[{"title": "choose X", "body": "because Y", "confidence": 0.85}],
    )
    paths = write_decisions_md(tmp_path, run, session_id="abc123")
    assert len(paths) == 1
    text = paths[0].read_text()

    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    fm_block = text[4:end]
    fm = _yaml.safe_load(fm_block)

    expected_keys = {"id", "status", "related_session", "confidence", "created_at"}
    assert set(fm.keys()) == expected_keys
    assert fm["status"] == "active"
    assert fm["related_session"] == "abc123"
    assert 0.0 <= float(fm["confidence"]) <= 1.0
    # id matches the file stem.
    assert fm["id"] == paths[0].stem


def test_repo_idx_schema(git_repo: Path) -> None:
    idx = build_repo_idx(git_repo)
    assert idx["version"] == 1
    assert len(idx["git_head"]) == 40
    assert all(c in "0123456789abcdef" for c in idx["git_head"])
    assert isinstance(idx["files"], list)
    assert len(idx["files"]) > 0
    entry = idx["files"][0]
    assert set(entry.keys()) == {"path", "size", "mtime", "sha"}
    assert len(entry["sha"]) == 40
    assert all(c in "0123456789abcdef" for c in entry["sha"])


def test_gitignore_idempotent(tmp_path: Path) -> None:
    g = tmp_path / ".gitignore"
    assert append_gitignore_line_idempotent(g, ".voss-cache/") is True
    assert append_gitignore_line_idempotent(g, ".voss-cache/") is False
    assert g.read_text().count(".voss-cache/") == 1


