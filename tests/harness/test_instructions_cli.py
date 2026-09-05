"""S0.8 — `voss instructions show|check`."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from voss.harness.cli import AGENT_COMMANDS, instructions_group


def _run(args: list[str]):
    return CliRunner().invoke(instructions_group, args)


def _w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_registered() -> None:
    assert instructions_group in AGENT_COMMANDS


def test_show_lists_files_in_order(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "root\n")
    _w(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _w(tmp_path / "src" / "AGENTS.md", "nested\n")
    res = _run(["show", "--cwd", str(tmp_path), "--target", "src"])
    assert res.exit_code == 0, res.output
    lines = res.output.splitlines()
    assert lines[0].strip().startswith("AGENTS.md")
    assert lines[1].strip().startswith("src/AGENTS.md")
    assert "CLAUDE.md  [collapsed]" in res.output
    assert "bundle:" in res.output


def test_show_json(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "root\n")
    res = _run(["show", "--cwd", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert [f["path"] for f in data["files"]] == ["AGENTS.md"]
    assert data["files"][0]["kind"] == "agents"
    assert len(data["bundle_hash"]) == 64


def test_show_empty(tmp_path: Path) -> None:
    res = _run(["show", "--cwd", str(tmp_path)])
    assert res.exit_code == 0
    assert "(no instruction files found)" in res.output


def test_check_ok(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "root\n")
    res = _run(["check", "--cwd", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "ok: 1 file(s)" in res.output


def test_check_fails_on_cycle(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "@B.md\n")
    _w(tmp_path / "B.md", "@AGENTS.md\n")
    res = _run(["check", "--cwd", str(tmp_path)])
    assert res.exit_code == 1
    assert "cycle" in res.output


def test_check_fails_on_overflow(tmp_path: Path, monkeypatch) -> None:
    from voss.harness import cli as cli_mod

    _w(tmp_path / "AGENTS.md", "rule\n" * 30_000)
    monkeypatch.setattr(
        "voss.harness.config.get_instructions_config",
        lambda: {"enabled": True, "budget_tokens": 100, "per_file_tokens": 100, "read_global": False},
    )
    res = _run(["check", "--cwd", str(tmp_path)])
    assert res.exit_code == 1
    assert "budget overflow: AGENTS.md" in res.output
    assert cli_mod is not None
