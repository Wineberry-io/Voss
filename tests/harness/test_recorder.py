"""Wave 1 RunRecorder tests (COG-08 mechanical capture, M2-02)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from voss.harness.recorder import RunRecorder
from voss.harness.session import RunRecord


def test_inspect_captures_fs_read() -> None:
    rec = RunRecorder.start()
    rec.observe("fs_read", {"path": "src/a.py"}, "contents", ok=True)
    assert rec.inspected == ["src/a.py"]


def test_change_captures_fs_write() -> None:
    rec = RunRecorder.start()
    rec.observe(
        "fs_write",
        {"path": "out.md", "content": "x"},
        "wrote 1 bytes to out.md",
        ok=True,
    )
    assert rec.changed == ["out.md"]


def test_validation_captures_exit_code() -> None:
    rec = RunRecorder.start()
    rec.observe(
        "shell_run",
        {"cmd": "pytest"},
        "[exit 1]\nfailed assertion",
        ok=True,
    )
    assert rec.validation[0]["exit"] == 1
    assert rec.validation[0]["cmd"] == "pytest"
    summary = rec.validation[0]["summary"]
    assert isinstance(summary, str) and 0 < len(summary) <= 160


def test_failure_captures_tool_error() -> None:
    rec = RunRecorder.start()
    rec.observe(
        "fs_write",
        {"path": "/etc/passwd", "content": "x"},
        "<error: path escapes cwd>",
        ok=False,
    )
    assert rec.failures[0]["tool"] == "fs_write"
    assert "path escapes cwd" in rec.failures[0]["error"]


def test_diff_summary_from_git(git_repo: Path) -> None:
    # Modify README.md after initial commit so `git diff --stat` has content.
    (git_repo / "README.md").write_text("# t\nmodified line\n")
    rec = RunRecorder.start()
    result = rec.finalize(git_repo, cost_usd=0.01)
    assert result.diff_summary, "diff_summary should be non-empty after modification"
    assert "README.md" in result.diff_summary or "file" in result.diff_summary


def test_decisions_mirror_to_markdown_renders_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import voss.harness.cognition as cognition
    import voss.harness.recorder as recorder

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 9, 12, 34, 56, tzinfo=timezone.utc)

    monkeypatch.setattr(cognition, "datetime", FrozenDateTime)
    monkeypatch.setattr(recorder, "datetime", FrozenDateTime)
    run = RunRecord(
        id="r1",
        started_at="t0",
        ended_at="t1",
        decisions=[
            {
                "title": "choose X",
                "body": "because Y",
                "confidence": 0.85,
            }
        ],
    )

    paths = recorder.write_decisions_md(tmp_path, run, session_id="abc123")

    assert [path.relative_to(tmp_path) for path in paths] == [
        Path(".voss/decisions/2026-06-09-choose-x.md")
    ]
    assert paths[0].read_text() == (
        "---\n"
        "id: 2026-06-09-choose-x\n"
        "status: active\n"
        "related_session: abc123\n"
        "confidence: 0.85\n"
        "created_at: 2026-06-09T12:34:56+00:00\n"
        "---\n"
        "\n"
        "# choose X\n"
        "\n"
        "because Y\n"
    )


# ---------------------------------------------------------------------------
# T2-01: begin_batch / end_batch capture API.
# ---------------------------------------------------------------------------


def test_begin_batch_appends_and_returns_record() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    br = rec.begin_batch(batch_index=0, step_indices=[0, 1, 2])
    assert br.batch_index == 0
    assert br.step_indices == [0, 1, 2]
    assert br.parallel_count == 3
    assert br.wall_clock_ms == 0
    assert br.ok_count == 0
    assert br.err_count == 0
    assert rec._iterations[-1].batches[-1] is br


def test_end_batch_patches_trailing_record() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    rec.begin_batch(batch_index=0, step_indices=[0, 1, 2])
    rec.end_batch(wall_clock_ms=125, ok_count=3, err_count=0)
    br = rec._iterations[-1].batches[-1]
    assert br.batch_index == 0
    assert br.step_indices == [0, 1, 2]
    assert br.parallel_count == 3
    assert br.wall_clock_ms == 125
    assert br.ok_count == 3
    assert br.err_count == 0


def test_begin_end_batch_full_state_after_cycle() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    rec.begin_batch(batch_index=0, step_indices=[0])
    rec.end_batch(wall_clock_ms=10, ok_count=1, err_count=0)
    br = rec._iterations[-1].batches[-1]
    assert (
        br.batch_index == 0
        and br.step_indices == [0]
        and br.parallel_count == 1
        and br.wall_clock_ms == 10
        and br.ok_count == 1
        and br.err_count == 0
    )


def test_multiple_sequential_batches_preserve_monotonic_index() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    rec.begin_batch(batch_index=0, step_indices=[0, 1])
    rec.end_batch(wall_clock_ms=50, ok_count=2, err_count=0)
    rec.begin_batch(batch_index=1, step_indices=[3])
    rec.end_batch(wall_clock_ms=30, ok_count=1, err_count=0)
    batches = rec._iterations[-1].batches
    assert [b.batch_index for b in batches] == [0, 1]


def test_begin_batch_outside_iteration_raises() -> None:
    rec = RunRecorder.start()
    with pytest.raises(RuntimeError, match="outside an iteration scope"):
        rec.begin_batch(batch_index=0, step_indices=[0])


def test_end_batch_with_no_iteration_raises() -> None:
    rec = RunRecorder.start()
    with pytest.raises(RuntimeError, match="without a matching begin_batch"):
        rec.end_batch(wall_clock_ms=0, ok_count=0, err_count=0)


def test_end_batch_with_iteration_but_no_batch_raises() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    with pytest.raises(RuntimeError, match="without a matching begin_batch"):
        rec.end_batch(wall_clock_ms=0, ok_count=0, err_count=0)


def test_step_indices_stored_as_defensive_copy() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    indices = [0, 1, 2]
    br = rec.begin_batch(batch_index=0, step_indices=indices)
    indices.append(99)
    indices[0] = -1
    assert br.step_indices == [0, 1, 2]
    assert rec._iterations[-1].batches[-1].step_indices == [0, 1, 2]


def test_batches_nest_within_correct_iteration() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    rec.begin_batch(batch_index=0, step_indices=[0, 1])
    rec.end_batch(wall_clock_ms=10, ok_count=2, err_count=0)
    rec.begin_iteration()
    rec.begin_batch(batch_index=0, step_indices=[5])
    rec.end_batch(wall_clock_ms=20, ok_count=1, err_count=0)
    assert len(rec._iterations) == 2
    assert len(rec._iterations[0].batches) == 1
    assert len(rec._iterations[1].batches) == 1
    assert rec._iterations[0].batches[0].step_indices == [0, 1]
    assert rec._iterations[1].batches[0].step_indices == [5]
