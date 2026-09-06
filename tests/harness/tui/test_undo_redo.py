"""Tests for the git-backed /undo and /redo slash commands (OpenCode-leverage
port). Drives the handlers via the registry against a real temp git repo."""
from __future__ import annotations

import subprocess
import types


from voss.harness.cli import _build_slash_registry


def _git(args, cwd) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init_repo(tmp_path):
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)


def _ctx(tmp_path, runs):
    return types.SimpleNamespace(
        cwd=tmp_path,
        record=types.SimpleNamespace(runs=runs),
        redo_stack=[],
    )


def _handlers():
    reg = _build_slash_registry()
    return reg.lookup("/undo").handler, reg.lookup("/redo").handler


def test_undo_reverts_then_redo_restores(tmp_path) -> None:
    _init_repo(tmp_path)
    f = tmp_path / "a.txt"
    f.write_text("committed\n")
    _git(["add", "a.txt"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)

    # simulate the agent editing the tracked file in the last run
    f.write_text("agent change\n")
    ctx = _ctx(tmp_path, runs=[{"changed": ["a.txt"]}])
    undo, redo = _handlers()

    undo(ctx, [], "")
    assert f.read_text() == "committed\n", "/undo reverts to committed content"
    assert ctx.redo_stack, "/undo records a redo entry"

    redo(ctx, [], "")
    assert f.read_text() == "agent change\n", "/redo restores the agent's content"
    assert not ctx.redo_stack, "/redo consumes the entry"


def test_undo_no_runs(tmp_path) -> None:
    _init_repo(tmp_path)
    ctx = _ctx(tmp_path, runs=[])
    undo, _ = _handlers()
    undo(ctx, [], "")  # must not raise
    assert ctx.redo_stack == []


def test_undo_run_with_no_changes(tmp_path) -> None:
    _init_repo(tmp_path)
    ctx = _ctx(tmp_path, runs=[{"changed": []}])
    undo, _ = _handlers()
    undo(ctx, [], "")
    assert ctx.redo_stack == []


def test_redo_without_undo_is_noop(tmp_path) -> None:
    ctx = _ctx(tmp_path, runs=[])
    _, redo = _handlers()
    redo(ctx, [], "")  # must not raise
    assert ctx.redo_stack == []


def test_undo_untracked_file_reports_failure(tmp_path) -> None:
    # Untracked (agent-created) files can't be `git checkout`-reverted; the
    # command should not crash and should leave nothing to redo for them.
    _init_repo(tmp_path)
    seed = tmp_path / "seed.txt"
    seed.write_text("x\n")
    _git(["add", "seed.txt"], tmp_path)
    _git(["commit", "-m", "seed"], tmp_path)

    created = tmp_path / "new.txt"
    created.write_text("brand new\n")
    ctx = _ctx(tmp_path, runs=[{"changed": ["new.txt"]}])
    undo, _ = _handlers()
    undo(ctx, [], "")
    # untracked file still present, nothing recorded for redo
    assert created.exists()
    assert ctx.redo_stack == []
