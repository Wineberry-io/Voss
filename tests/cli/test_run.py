from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from voss.cli import main


_SOURCE = "let x = 1\n"


def _write_source(name: str = "app.voss") -> Path:
    path = Path(name)
    path.write_text(_SOURCE)
    return path


def _patch_compile(monkeypatch, script_body: str):
    """Replace _compile_source with a stub that writes a known generated script."""

    def fake_compile(source_path, **kwargs):
        output_path = kwargs.get("output_path")
        if output_path is None:
            output_path = Path(source_path).with_suffix(".py")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(script_body)
        return Path(output_path)

    monkeypatch.setattr("voss.cli._compile_source", fake_compile)


def test_run_executes_generated_python_with_current_interpreter(monkeypatch):
    _patch_compile(monkeypatch, "print('ok')\n")

    captured: dict = {}
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        return real_run(
            [sys.executable, "-c", "import sys; sys.stdout.write('ok'); sys.exit(0)"],
            *args,
            **kwargs,
        )

    monkeypatch.setattr("voss.cli.subprocess.run", fake_run)
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
        assert result.exit_code == 0, result.output
        cmd = captured["cmd"]
        assert cmd[0] == sys.executable
        assert cmd[1].endswith(".py")


def test_run_forwards_stdout_and_exit_zero(monkeypatch):
    _patch_compile(monkeypatch, "print('ok')\n")
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
        assert result.exit_code == 0, result.output
        assert "ok" in result.output


def test_run_forwards_subprocess_exit_code(monkeypatch):
    _patch_compile(monkeypatch, "import sys\nsys.exit(7)\n")
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
        assert result.exit_code == 7


def test_run_does_not_use_exec():
    text = Path("voss/cli.py").read_text()
    assert "exec(" not in text
    assert "eval(" not in text
