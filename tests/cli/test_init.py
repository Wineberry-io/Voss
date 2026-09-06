from __future__ import annotations

import importlib.resources
import tomllib
from pathlib import Path

from click.testing import CliRunner

from voss import parse
from voss.cli import main


_LINGUIST_LINE = "*.voss linguist-language=Voss linguist-detectable=true"
_SCAFFOLD_FILES = (".gitattributes", ".gitignore", "pyproject.toml", "README.md", "hello.voss")


def test_init_creates_minimal_project_scaffold():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "my-project"])
        assert result.exit_code == 0, result.output
        target = Path("my-project")
        for name in _SCAFFOLD_FILES:
            assert (target / name).exists(), name
        assert _LINGUIST_LINE in (target / ".gitattributes").read_text()
        data = tomllib.loads((target / "pyproject.toml").read_text())
        assert data["project"]["name"] == "my-project"
        assert (target / "README.md").read_text().startswith("# my-project")


def test_init_hello_voss_parses():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "proj"])
        assert result.exit_code == 0, result.output
        hello = Path("proj/hello.voss")
        parse(hello.read_text(), file=str(hello))


def test_init_name_option_controls_template_context():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "proj", "--name", "Ben's Demo"])
        assert result.exit_code == 0, result.output
        data = tomllib.loads(Path("proj/pyproject.toml").read_text())
        assert data["project"]["name"] == "ben-s-demo"
        assert Path("proj/README.md").read_text().startswith("# ben-s-demo")


def test_init_renders_exact_template_bytes():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "proj", "--name", "Ben's Demo"])
        assert result.exit_code == 0, result.output

        target = Path("proj")
        assert (target / ".gitattributes").read_text() == (
            "*.voss linguist-language=Voss linguist-detectable=true\n"
        )
        assert (target / ".gitignore").read_text() == (
            "__pycache__/\n"
            "*.pyc\n"
            "*.pyo\n"
            ".voss-cache/\n"
            "build/\n"
            "dist/\n"
            "*.egg-info/\n"
            ".venv/\n"
            ".env\n"
        )
        assert (target / "pyproject.toml").read_text() == (
            "[project]\n"
            'name = "ben-s-demo"\n'
            'version = "0.1.0"\n'
            'description = "A Voss project."\n'
            'requires-python = ">=3.11"\n'
            "dependencies = [\n"
            '    "voss",\n'
            "]\n"
        )
        assert (target / "README.md").read_text() == (
            "# ben-s-demo\n"
            "\n"
            "A new Voss project scaffolded by `voss init`.\n"
            "\n"
            "## Quick start\n"
            "\n"
            "```sh\n"
            "voss check hello.voss\n"
            "voss compile hello.voss\n"
            "voss run hello.voss\n"
            "```\n"
            "\n"
            "## Linguist\n"
            "\n"
            "`.gitattributes` overrides this repository so `*.voss` files render as Voss on\n"
            "hosting providers that respect Linguist overrides.\n"
        )
        assert (target / "hello.voss").read_text() == (
            "# hello.voss\n"
            'let greeting = "hello, voss"\n'
            "print(greeting)\n"
        )


def test_init_refuses_non_empty_directory_without_force():
    runner = CliRunner()
    with runner.isolated_filesystem():
        target = Path("target")
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_text("keep me")
        result = runner.invoke(main, ["init", "target"])
        assert result.exit_code != 0
        assert sentinel.read_text() == "keep me"


def test_init_force_allows_existing_directory_without_deleting_unrelated_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        target = Path("target")
        target.mkdir()
        unrelated = target / "keep.txt"
        unrelated.write_text("keep me")
        result = runner.invoke(main, ["init", "--force", "target"])
        assert result.exit_code == 0, result.output
        assert unrelated.read_text() == "keep me"
        for name in _SCAFFOLD_FILES:
            assert (target / name).exists(), name


def test_init_writes_only_under_target_directory():
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        result = runner.invoke(main, ["init", "isolated"])
        assert result.exit_code == 0, result.output
        fs_root = Path(fs)
        top = {p.name for p in fs_root.iterdir()}
        # Only the target directory should appear at the runner root.
        assert top == {"isolated"}, top


def test_init_templates_are_package_resources():
    template_root = importlib.resources.files("voss").joinpath("templates/init")
    for name in _SCAFFOLD_FILES:
        resource_name = {
            "pyproject.toml": "pyproject.toml.jinja",
            "README.md": "README.md.jinja",
        }.get(name, name)
        assert template_root.joinpath(resource_name).is_file(), resource_name
