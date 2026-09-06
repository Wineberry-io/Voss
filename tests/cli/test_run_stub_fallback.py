from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from voss.cli import main
from voss.harness.auth import Resolution


BANNER = "voss: no provider creds detected — using __stub__ (deterministic fake responses)"
_SOURCE = "let x = 1\n"


def _write_source(name: str = "app.voss") -> Path:
    path = Path(name)
    path.write_text(_SOURCE)
    return path


def _patch_compile(monkeypatch, script_body: str) -> None:
    def fake_compile(source_path, **kwargs):
        output_path = kwargs.get("output_path")
        if output_path is None:
            output_path = Path(source_path).with_suffix(".py")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(script_body)
        return Path(output_path)

    monkeypatch.setattr("voss.cli._compile_source", fake_compile)


def _capture_subprocess(monkeypatch) -> dict:
    captured: dict = {}

    def fake_run(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="ok\n", stderr=""
        )

    monkeypatch.setattr("voss.cli.subprocess.run", fake_run)
    return captured


def test_auto_register_stub_when_no_creds(monkeypatch):
    _patch_compile(monkeypatch, "print('ok')\n")
    captured = _capture_subprocess(monkeypatch)
    monkeypatch.setattr("voss.cli.auth_mod.resolve", lambda preference="auto": Resolution(source="none", detail="forced"))
    monkeypatch.delenv("VOSS_HERMETIC", raising=False)
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
    assert result.exit_code == 0, result.output
    assert captured["env"] is not None
    assert captured["env"]["VOSS_HERMETIC"] == "1"


def test_stub_fallback_banner_on_stderr(monkeypatch):
    _patch_compile(monkeypatch, "print('ok')\n")
    _capture_subprocess(monkeypatch)
    monkeypatch.setattr("voss.cli.auth_mod.resolve", lambda preference="auto": Resolution(source="none", detail="forced"))
    monkeypatch.delenv("VOSS_HERMETIC", raising=False)
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
    assert result.exit_code == 0, result.output
    assert BANNER in result.stderr
    assert BANNER not in result.stdout


def test_voss_hermetic_env_var_path(monkeypatch):
    _patch_compile(monkeypatch, "print('ok')\n")
    captured = _capture_subprocess(monkeypatch)
    monkeypatch.setenv("VOSS_HERMETIC", "1")
    monkeypatch.setattr("voss.cli.auth_mod.resolve", lambda preference="auto": Resolution(source="env-anthropic", detail="ANTHROPIC_API_KEY"))
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
    assert result.exit_code == 0, result.output
    assert BANNER in result.stderr
    assert captured["env"] is not None
    assert captured["env"]["VOSS_HERMETIC"] == "1"


def test_live_cred_path_no_banner(monkeypatch):
    _patch_compile(monkeypatch, "print('ok')\n")
    captured = _capture_subprocess(monkeypatch)
    monkeypatch.delenv("VOSS_HERMETIC", raising=False)
    monkeypatch.setattr("voss.cli.auth_mod.resolve", lambda preference="auto": Resolution(source="env-anthropic", detail="ANTHROPIC_API_KEY"))
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write_source()
        result = runner.invoke(main, ["run", str(path)])
    assert result.exit_code == 0, result.output
    assert BANNER not in result.stderr
    assert captured["env"] is None
