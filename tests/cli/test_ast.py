from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from voss.cli import main


_SIMPLE_PROGRAM = "let x = 1\n"


def _write_source(name: str = "tiny.voss") -> Path:
    path = Path(name)
    path.write_text(_SIMPLE_PROGRAM)
    return path


def test_ast_prints_normalized_json_for_voss_file():
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        path = _write_source()
        result = runner.invoke(main, ["ast", "--normalize-spans", str(path)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["_node"] == "Program"
        body = data["body"]
        assert isinstance(body, list)
        assert body[0]["_node"] == "LetStmt"
        span = data["span"]
        assert span["file"] == "tiny.voss"
        assert span["lines"] == [0, 0]
        assert not (Path(fs) / ".voss-cache").exists()


def test_ast_compact_outputs_valid_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(
            main, ["ast", "--normalize-spans", "--compact", str(path)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["_node"] == "Program"
        # Compact output has no leading-space indentation.
        assert "\n  " not in result.output


def test_ast_is_read_only():
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        path = _write_source()
        result = runner.invoke(main, ["ast", "--normalize-spans", str(path)])
        assert result.exit_code == 0, result.output
        fs_path = Path(fs)
        assert not (fs_path / ".voss-cache").exists()
        assert not (fs_path / "tiny.py").exists()
        for sibling in fs_path.iterdir():
            assert sibling.suffix != ".py", sibling
