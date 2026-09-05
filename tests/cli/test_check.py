from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from voss.ast_nodes import Span
from voss.cli import main
from voss.diagnostics import AnalysisResult, Diagnostic


_PROBABLE_WARNING_SOURCE = (
    "fn doIt(x: string) -> string {\n"
    "    let intent: probable<string> = ask(\"classify\")\n"
    "    return intent.value\n"
    "}\n"
)

_CLEAN_SOURCE = "let x = 1\n"
_INVALID_TEAM_SOURCE = '''team Eng {
  ceiling { budget: 100 tokens, scope: "src/**" }
  roster e {
    backend { budget: 200 tokens, scope: "src/api/**", tools: ["fs"] }
  }
}
'''
_SEMANTIC_MATCH_SOURCE = (
    "fn route(x: string) -> string {\n"
    "    match x {\n"
    "        case similar(\"billing\") => {\n"
    "            return \"billing\"\n"
    "        }\n"
    "        case _ => {\n"
    "            return \"general\"\n"
    "        }\n"
    "    }\n"
    "}\n"
)


def _write(name: str, body: str) -> Path:
    path = Path(name)
    path.write_text(body)
    return path


def test_check_prints_analyzer_warning_and_exits_zero_by_default():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write("warn.voss", _PROBABLE_WARNING_SOURCE)
        result = runner.invoke(main, ["check", str(path)])
        assert result.exit_code == 0, result.output
        assert "ANLY001" in result.output
        assert "warning" in result.output
        assert "warn.voss" in result.output


def test_check_warnings_as_errors_exits_nonzero():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write("warn.voss", _PROBABLE_WARNING_SOURCE)
        result = runner.invoke(main, ["check", "--warnings-as-errors", str(path)])
        assert result.exit_code != 0
        assert "ANLY001" in result.output


def test_check_errors_exit_nonzero(monkeypatch):
    err_diag = Diagnostic(
        severity="error",
        code="ANLY999",
        message="forced error for test",
        span=Span(file="boom.voss", line_start=1, col_start=1, line_end=1, col_end=1),
    )

    def fake_analyze(program, **kwargs):
        return AnalysisResult(diagnostics=(err_diag,), indexes=())

    monkeypatch.setattr("voss.cli.analyze", fake_analyze)
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write("boom.voss", _CLEAN_SOURCE)
        result = runner.invoke(main, ["check", str(path)])
        assert result.exit_code != 0
        assert "ANLY999" in result.output
        assert "forced error for test" in result.output


def test_check_runs_team_semantic_validation() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write("team.voss", _INVALID_TEAM_SOURCE)
        result = runner.invoke(main, ["check", str(path)])
        assert result.exit_code == 1
        assert "team.budget" in result.output
        assert "team.voss:4" in result.output
        assert "hint:" in result.output


def test_check_does_not_emit_indexes_or_cache_files():
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        path = _write("clean.voss", _CLEAN_SOURCE)
        result = runner.invoke(
            main, ["check", "--cache-dir", ".voss-cache", str(path)]
        )
        assert result.exit_code == 0, result.output
        fs_path = Path(fs)
        assert not (fs_path / ".voss-cache").exists()
        assert not list(fs_path.glob("**/*.idx"))


def test_check_passes_emit_indexes_false_to_analyzer(monkeypatch):
    captured: dict = {}

    def fake_analyze(program, **kwargs):
        captured.update(kwargs)
        return AnalysisResult(diagnostics=(), indexes=())

    monkeypatch.setattr("voss.cli.analyze", fake_analyze)
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write("clean.voss", _CLEAN_SOURCE)
        result = runner.invoke(main, ["check", str(path)])
        assert result.exit_code == 0, result.output
        assert captured.get("emit_indexes") is False


def test_check_directory_walks_voss_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("demo").mkdir()
        _write("demo/a.voss", _CLEAN_SOURCE)
        _write("demo/b.voss", _CLEAN_SOURCE)
        result = runner.invoke(main, ["check", "demo"])
        assert result.exit_code == 0, result.output


def test_check_directory_errors_when_no_voss_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("empty").mkdir()
        result = runner.invoke(main, ["check", "empty"])
        assert result.exit_code != 0
        assert "no .voss files found" in result.output


def test_check_semantic_match_does_not_build_embedding_index(monkeypatch):
    def fail_builder(*args, **kwargs):
        raise AssertionError("check should not build semantic indexes")

    monkeypatch.setattr("voss.analyzer.SemanticMatcherIndexBuilder", fail_builder)
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = _write("route.voss", _SEMANTIC_MATCH_SOURCE)
        result = runner.invoke(main, ["check", str(path)])
        assert result.exit_code == 0, result.output
