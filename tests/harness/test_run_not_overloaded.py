"""CLIH-10: `voss run` remains the compiler verb, NOT an agent task runner.

Guards against a future refactor that overloads `voss run` for natural-language
tasks. If anyone confuses `voss run` with `voss do`, this test fails.
"""
from __future__ import annotations


from click.testing import CliRunner

from voss.cli import main


class TestRunIsCompilerVerb:
    def test_run_help_describes_compilation(self):
        result = CliRunner().invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert any(
            tok in output_lower
            for tok in ("voss source", "compile and execute", ".voss")
        ), f"voss run --help should describe compiler semantics, got: {result.output!r}"
        assert "natural-language" not in output_lower
        assert "agent task" not in output_lower

    def test_run_does_not_require_auth(self, tmp_path):
        src = tmp_path / "hello.voss"
        src.write_text('print("hi")\n')
        result = CliRunner().invoke(main, ["run", str(src)])
        # Compiler may succeed or surface a compile error, but must NOT ask
        # for credentials.
        assert "no usable credentials" not in result.output

    def test_run_not_in_agent_commands(self):
        from voss.harness.cli import AGENT_COMMANDS
        names = {cmd.name for cmd in AGENT_COMMANDS}
        assert "run" not in names, (
            "voss run must remain a compiler command; AGENT_COMMANDS contains it"
        )

    def test_do_and_run_are_different_commands(self):
        do_help = CliRunner().invoke(main, ["do", "--help"])
        run_help = CliRunner().invoke(main, ["run", "--help"])
        assert do_help.exit_code == 0
        assert run_help.exit_code == 0
        assert "task" in do_help.output.lower()
        assert "natural" not in run_help.output.lower()
