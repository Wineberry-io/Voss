"""`voss tools` + `voss config` CLI tests (CLIH-07, CLIH-09)."""
from __future__ import annotations


from click.testing import CliRunner

from voss.harness.cli import config_cmd, tools_cmd
from voss.harness.tools import make_toolset


class TestToolsCmd:
    def test_help_mentions_tools(self):
        result = CliRunner().invoke(tools_cmd, ["--help"])
        assert result.exit_code == 0
        assert "tool" in result.output.lower()

    def test_lists_registered_tools(self, tmp_path):
        result = CliRunner().invoke(tools_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 0
        assert "name" in result.output
        assert "mutating" in result.output
        assert "description" in result.output
        for name in make_toolset(tmp_path):
            assert name in result.output, f"missing tool name: {name}"

    def test_marks_mutating_tools(self, tmp_path):
        result = CliRunner().invoke(tools_cmd, ["--cwd", str(tmp_path)])
        for line in result.output.splitlines():
            stripped = line.lstrip()
            for mut_name in ("fs_write", "fs_edit", "shell_run"):
                if stripped.startswith(mut_name + " "):
                    assert " yes" in line, (
                        f"{mut_name} should be marked mutating: {line!r}"
                    )
            for ro_name in (
                "fs_read", "fs_glob", "fs_grep",
                "git_status", "git_diff", "voss_check",
            ):
                if stripped.startswith(ro_name + " "):
                    assert " no" in line, (
                        f"{ro_name} should NOT be marked mutating: {line!r}"
                    )


class TestConfigCmd:
    def test_show_on_missing_file_creates_and_prints(self, tmp_path):
        cfg = tmp_path / "config.toml"
        result = CliRunner().invoke(
            config_cmd, ["--show", "--config-path", str(cfg)]
        )
        assert result.exit_code == 0
        assert cfg.exists()

    def test_show_existing_content(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('[harness]\npreferred_model = "claude-sonnet-4"\n')
        result = CliRunner().invoke(
            config_cmd, ["--show", "--config-path", str(cfg)]
        )
        assert result.exit_code == 0
        assert 'preferred_model = "claude-sonnet-4"' in result.output

    def test_open_invokes_editor(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.toml"
        called: list = []

        def fake_run(argv, **kwargs):
            called.append(argv)

            class R:
                returncode = 0

            return R()

        from voss.harness import cli as cli_mod

        monkeypatch.setattr(cli_mod.subprocess, "run", fake_run)
        monkeypatch.setenv("EDITOR", "my-editor")
        result = CliRunner().invoke(config_cmd, ["--config-path", str(cfg)])
        assert result.exit_code == 0
        assert called and called[0][0] == "my-editor"
        assert called[0][1] == str(cfg)
        assert cfg.exists()
        assert "[harness]" in cfg.read_text()
