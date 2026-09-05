"""`voss edit` CLI + scope-aware gate behaviors (D-01..D-04, CTRL-08)."""
from __future__ import annotations


from click.testing import CliRunner

from voss.harness.cli import edit_cmd
from voss.harness.edit_scope import EditScope
from voss.harness.permissions import PermissionGate


class TestEditCmdRegistration:
    def test_edit_help_mentions_path_and_scope(self):
        result = CliRunner().invoke(edit_cmd, ["--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output
        assert "scope" in result.output.lower()


class TestScopedGate:
    def test_in_scope_write_does_not_prompt_expand(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        prompted: list[str] = []
        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=lambda t: prompted.append(t) or "n",
        )
        ok, _ = gate.check(
            "fs_write",
            {"path": "a.py", "content": "x = 2\n"},
            is_mutating=True,
        )
        assert ok
        assert not prompted

    def test_out_of_scope_write_denies_on_n(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=lambda t: "n",
        )
        ok, why = gate.check(
            "fs_write",
            {"path": "b.py", "content": "y = 2\n"},
            is_mutating=True,
        )
        assert not ok
        assert "out-of-scope" in why or "denied" in why

    def test_once_allows_single_write_without_persisting(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=lambda t: "y",
        )
        ok, why = gate.check(
            "fs_write",
            {"path": "b.py", "content": "y = 2\n"},
            is_mutating=True,
        )
        assert ok
        assert "once" in why
        # Not persisted: b.py still not in scope.
        assert not scope.allows_write("b.py")

    def test_always_expands_scope_for_session(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=lambda t: "always",
        )
        ok, _ = gate.check(
            "fs_write",
            {"path": "b.py", "content": "y = 2\n"},
            is_mutating=True,
        )
        assert ok
        assert scope.allows_write("b.py")


class TestDiffPreview:
    def test_diff_preview_rendered_for_fs_write_scoped(self, tmp_path, capsys):
        (tmp_path / "a.py").write_text("x = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=lambda t: "n",
        )
        gate.check(
            "fs_write",
            {"path": "a.py", "content": "x = 2\n"},
            is_mutating=True,
        )
        captured = capsys.readouterr()
        assert "diff preview" in captured.err
        assert "x = 1" in captured.err
        assert "x = 2" in captured.err

    def test_diff_preview_rendered_for_fs_edit(self, tmp_path, capsys):
        (tmp_path / "a.py").write_text("hello world\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=lambda t: "n",
        )
        gate.check(
            "fs_edit",
            {"path": "a.py", "old": "hello", "new": "goodbye"},
            is_mutating=True,
        )
        captured = capsys.readouterr()
        assert "diff preview" in captured.err

    def test_diff_preview_rendered_without_edit_scope(self, tmp_path, capsys, monkeypatch):
        """W1: diff preview must render for `voss do --mode=edit` / `voss chat --mode=edit`.

        These flows have no EditScope attached, but CTRL-08 still requires the
        preview. Prior to W1 the diff was nested under `if self.edit_scope`,
        so unscoped writes had NO preview.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("x = 1\n")
        gate = PermissionGate(mode="edit", auto_yes=True, edit_scope=None)
        gate.check(
            "fs_write",
            {"path": "a.py", "content": "x = 2\n"},
            is_mutating=True,
        )
        captured = capsys.readouterr()
        assert "diff preview" in captured.err, (
            "diff preview must render even without an EditScope (CTRL-08, W1)"
        )

    def test_diff_renders_before_expand_prompt(self, tmp_path, capsys):
        """W4: out-of-scope writes render the diff BEFORE the expand prompt fires."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")

        def recording_prompt(target: str) -> str:
            import sys as _s
            _s.stderr.write("PROMPT_FIRED\n")
            return "n"

        gate = PermissionGate(
            mode="edit",
            auto_yes=True,
            edit_scope=scope,
            scope_prompt_fn=recording_prompt,
        )
        gate.check(
            "fs_write",
            {"path": "b.py", "content": "y = 2\n"},
            is_mutating=True,
        )
        captured = capsys.readouterr()
        assert "diff preview" in captured.err
        assert "PROMPT_FIRED" in captured.err
        assert captured.err.index("diff preview") < captured.err.index("PROMPT_FIRED"), (
            "diff preview must render before the expand-scope prompt fires (W4)"
        )


class TestVossDoEditModeDiff:
    """W1 end-to-end mirror: confirm the do/chat-shaped gate construction gets the preview."""

    def test_do_mode_edit_renders_diff(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "foo.py").write_text("a = 1\n")
        gate = PermissionGate(mode="edit", auto_yes=True, edit_scope=None)
        ok, _ = gate.check(
            "fs_write",
            {"path": "foo.py", "content": "a = 2\n"},
            is_mutating=True,
        )
        assert ok
        captured = capsys.readouterr()
        assert "diff preview" in captured.err
