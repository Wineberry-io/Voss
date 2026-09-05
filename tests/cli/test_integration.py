from __future__ import annotations

import ast as _ast
import json
from pathlib import Path

from click.testing import CliRunner

from voss.cli import main


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLES_DIR = _REPO_ROOT / "samples"


def _hermetic_source() -> str:
    return "let x = 1\nprint(x)\n"


def _list_repo_indexes() -> set[str]:
    return {
        str(p)
        for p in _REPO_ROOT.glob("**/.voss-cache/*.idx")
        if ".pytest_cache" not in p.parts
    }


def test_cli_init_ast_check_smoke():
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        result_init = runner.invoke(main, ["init", "project"])
        assert result_init.exit_code == 0, result_init.output

        hello = Path("project/hello.voss")
        result_ast = runner.invoke(
            main, ["ast", "--normalize-spans", str(hello)]
        )
        assert result_ast.exit_code == 0, result_ast.output
        json.loads(result_ast.output)

        result_check = runner.invoke(main, ["check", str(hello)])
        assert result_check.exit_code == 0, result_check.output

        assert not (Path(fs) / ".voss-cache").exists()


def test_cli_compile_run_smoke_with_hermetic_generated_python():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("app.voss").write_text(_hermetic_source())
        compile_result = runner.invoke(
            main, ["compile", "app.voss", "--output", "app.py"]
        )
        assert compile_result.exit_code == 0, compile_result.output
        text = Path("app.py").read_text()
        _ast.parse(text)

        run_result = runner.invoke(main, ["run", "app.voss"])
        assert run_result.exit_code == 0, run_result.output
        assert "1" in run_result.output


def test_samples_ast_and_check_smoke(tmp_path):
    runner = CliRunner()
    cache = tmp_path / ".voss-cache"
    for sample in _SAMPLES_DIR.glob("*.voss"):
        ast_result = runner.invoke(
            main, ["ast", "--normalize-spans", str(sample)]
        )
        assert ast_result.exit_code == 0, ast_result.output
        check_result = runner.invoke(
            main,
            [
                "check",
                "--cache-dir",
                str(cache),
                "--project-root",
                str(tmp_path),
                str(sample),
            ],
        )
        # Errors fail; warnings are allowed.
        assert check_result.exit_code == 0, (
            f"{sample.name} check exit {check_result.exit_code}: {check_result.output}"
        )


def test_no_repo_local_cache_or_generated_outputs_after_smoke(tmp_path):
    before = _list_repo_indexes()
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("app.voss").write_text(_hermetic_source())
        runner.invoke(main, ["compile", "app.voss"])
        runner.invoke(main, ["run", "app.voss"])
        runner.invoke(main, ["check", "app.voss"])
    after = _list_repo_indexes()
    assert after == before, after - before
    # No .py file generated under the repo.
    repo_py = list((_REPO_ROOT / "samples").glob("*.py"))
    assert repo_py == []
