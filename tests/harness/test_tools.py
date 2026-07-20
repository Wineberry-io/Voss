import asyncio
from pathlib import Path

import pytest

from voss.harness.tools import ToolEntry, make_toolset


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# proj\n")
    return tmp_path


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_ephemeral_toolset_skips_background_indexing(tmp_path: Path, monkeypatch) -> None:
    from voss.harness.code.service import CodeIntelService
    from voss.harness.recall.external_index import ExternalRecallService

    def fail(*args, **kwargs):
        raise AssertionError("background indexer started")

    monkeypatch.setattr(CodeIntelService, "_get_code_index_service", fail)
    monkeypatch.setattr(ExternalRecallService, "__init__", fail)

    tools = make_toolset(tmp_path, background_indexing=False)

    assert "shell_run" in tools
    assert "code_recall" not in tools


class TestFsRead:
    def test_reads_text_file(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["fs_read"].invoke(path="src/a.py"))
        assert "hello" in out

    def test_missing_file_returns_error(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["fs_read"].invoke(path="missing.txt"))
        assert "not found" in out

    def test_directory_returns_error(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["fs_read"].invoke(path="src"))
        assert "directory" in out

    def test_path_escape_rejected(self, project: Path) -> None:
        tools = make_toolset(project)
        with pytest.raises(Exception):
            _run(tools["fs_read"].invoke(path="../../../etc/passwd"))


class TestHashlineEdits:
    def test_annotate_emits_anchors(self, tmp_path: Path) -> None:
        from voss.harness.tools import _line_anchor

        (tmp_path / "f.txt").write_text("alpha\nbeta\n")
        tools = make_toolset(tmp_path)
        out = _run(tools["fs_read"].invoke(path="f.txt", annotate=True))
        assert out == f"{_line_anchor('alpha')}│alpha\n{_line_anchor('beta')}│beta\n"

    def test_edit_by_anchor(self, tmp_path: Path) -> None:
        from voss.harness.tools import _line_anchor

        (tmp_path / "f.txt").write_text("alpha\nbeta\ngamma\n")
        tools = make_toolset(tmp_path)
        out = _run(
            tools["fs_edit"].invoke(path="f.txt", anchor=_line_anchor("beta"), new="BETA")
        )
        assert "edited f.txt" in out
        assert (tmp_path / "f.txt").read_text() == "alpha\nBETA\ngamma\n"

    def test_edit_span_anchor(self, tmp_path: Path) -> None:
        from voss.harness.tools import _line_anchor

        (tmp_path / "f.txt").write_text("a\nb\nc\nd\n")
        tools = make_toolset(tmp_path)
        _run(
            tools["fs_edit"].invoke(
                path="f.txt",
                anchor=_line_anchor("b"),
                end_anchor=_line_anchor("c"),
                new="X\nY\nZ",
            )
        )
        assert (tmp_path / "f.txt").read_text() == "a\nX\nY\nZ\nd\n"

    def test_stale_anchor_errors(self, tmp_path: Path) -> None:
        (tmp_path / "f.txt").write_text("alpha\n")
        tools = make_toolset(tmp_path)
        out = _run(tools["fs_edit"].invoke(path="f.txt", anchor="deadbeef", new="x"))
        assert "stale" in out

    def test_ambiguous_anchor_errors(self, tmp_path: Path) -> None:
        from voss.harness.tools import _line_anchor

        (tmp_path / "f.txt").write_text("dup\ndup\n")
        tools = make_toolset(tmp_path)
        out = _run(tools["fs_edit"].invoke(path="f.txt", anchor=_line_anchor("dup"), new="x"))
        assert "ambiguous" in out

    def test_old_still_works(self, tmp_path: Path) -> None:
        (tmp_path / "f.txt").write_text("foo\n")
        tools = make_toolset(tmp_path)
        out = _run(tools["fs_edit"].invoke(path="f.txt", old="foo", new="bar"))
        assert "edited f.txt" in out
        assert (tmp_path / "f.txt").read_text() == "bar\n"

    def test_old_and_anchor_conflict(self, tmp_path: Path) -> None:
        from voss.harness.tools import _line_anchor

        (tmp_path / "f.txt").write_text("alpha\n")
        tools = make_toolset(tmp_path)
        out = _run(
            tools["fs_edit"].invoke(
                path="f.txt", old="alpha", anchor=_line_anchor("alpha"), new="x"
            )
        )
        assert "not both" in out


class TestFsGlob:
    def test_lists_matching_files(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["fs_glob"].invoke(pattern="**/*.py"))
        assert "src/a.py" in out

    def test_no_match(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["fs_glob"].invoke(pattern="*.nonexistent"))
        assert "no matches" in out


class TestShellRun:
    def test_allowlisted_command_runs(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["shell_run"].invoke(cmd="ls"))
        assert "src" in out
        assert "README.md" in out

    def test_denied_command_blocked(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["shell_run"].invoke(cmd="rm -rf ."))
        assert "denied" in out

    def test_unknown_binary_blocked(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["shell_run"].invoke(cmd="evilbinary --pwn"))
        assert "denied" in out


class TestToolEntryClassification:
    def test_registry_values_are_tool_entries(self, tmp_path: Path) -> None:
        tools = make_toolset(tmp_path)
        for name, entry in tools.items():
            assert isinstance(entry, ToolEntry), name
            assert entry.descriptor.name == name
            assert isinstance(entry.is_mutating, bool)

    def test_read_only_tools_are_non_mutating(self, tmp_path: Path) -> None:
        tools = make_toolset(tmp_path)
        for name in (
            "fs_read",
            "fs_glob",
            "fs_grep",
            "shell_monitor",
            "git_status",
            "git_diff",
            "voss_check",
            "voss_probable_inspect",
            "voss_budget_trace",
            "voss_py_diff",
            "fs_watch",
            "fs_watch_poll",
        ):
            assert tools[name].is_mutating is False, name

    def test_mutating_tools_flagged(self, tmp_path: Path) -> None:
        tools = make_toolset(tmp_path)
        for name in (
            "fs_write",
            "fs_edit",
            "shell_run",
            "shell_run_background",
            "shell_signal",
        ):
            assert tools[name].is_mutating is True, name

    def test_descriptor_invoke_still_works(self, project: Path) -> None:
        tools = make_toolset(project)
        out = _run(tools["fs_read"].descriptor.invoke(path="src/a.py"))
        assert "hello" in out

    def test_mutating_count(self, tmp_path: Path) -> None:
        tools = make_toolset(tmp_path)
        # T2-05 added fs_read_many; T3 added web_fetch + web_search.
        # T5 adds shell_run_background + shell_monitor + shell_signal.
        assert sum(1 for e in tools.values() if e.is_mutating) == 7
        # M10-04 added 4 read-only code tools (code_search, find_definition, find_references, code_refresh).
        # M11-02 adds voss_probable_inspect + voss_budget_trace.
        # M11-04 adds voss_py_diff.
        # M14 adds fs_watch + fs_watch_poll.
        # V19-03 adds code_recall (0aad3907).
        assert sum(1 for e in tools.values() if not e.is_mutating) == 20
