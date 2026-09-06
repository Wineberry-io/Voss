"""EditScope sibling-mirror + write-gating tests (D-01..D-04)."""
from __future__ import annotations

from pathlib import Path


from voss.harness.edit_scope import EditScope


class TestResolve:
    def test_file_with_tests_dir_sibling(self, tmp_path: Path):
        (tmp_path / "src" / "foo").mkdir(parents=True)
        (tmp_path / "src" / "foo" / "bar.py").write_text("x = 1\n")
        (tmp_path / "tests" / "foo").mkdir(parents=True)
        (tmp_path / "tests" / "foo" / "test_bar.py").write_text("# test\n")

        scope = EditScope.resolve(tmp_path, "src/foo/bar.py")
        assert scope.allows_write("src/foo/bar.py")
        assert scope.allows_write("tests/foo/test_bar.py")
        assert not scope.allows_write("src/foo/baz.py")

    def test_file_no_sibling(self, tmp_path: Path):
        (tmp_path / "src" / "foo").mkdir(parents=True)
        (tmp_path / "src" / "foo" / "bar.py").write_text("x = 1\n")

        scope = EditScope.resolve(tmp_path, "src/foo/bar.py")
        assert scope.allows_write("src/foo/bar.py")
        assert not scope.allows_write("src/foo/baz.py")
        assert not scope.allows_write("tests/foo/test_bar.py")

    def test_directory_with_tests_mirror(self, tmp_path: Path):
        (tmp_path / "src" / "foo").mkdir(parents=True)
        (tmp_path / "src" / "foo" / "a.py").write_text("a = 1\n")
        (tmp_path / "src" / "foo" / "b.py").write_text("b = 1\n")
        (tmp_path / "tests" / "foo").mkdir(parents=True)
        (tmp_path / "tests" / "foo" / "test_a.py").write_text("# t\n")

        scope = EditScope.resolve(tmp_path, "src/foo")
        assert scope.allows_write("src/foo/a.py")
        assert scope.allows_write("src/foo/b.py")
        assert scope.allows_write("tests/foo/test_a.py")
        assert not scope.allows_write("tests/bar/test_x.py")

    def test_pytest_style_sibling_in_same_dir(self, tmp_path: Path):
        (tmp_path / "src" / "foo").mkdir(parents=True)
        (tmp_path / "src" / "foo" / "bar.py").write_text("x = 1\n")
        (tmp_path / "src" / "foo" / "bar_test.py").write_text("# t\n")

        scope = EditScope.resolve(tmp_path, "src/foo/bar.py")
        assert scope.allows_write("src/foo/bar.py")
        assert scope.allows_write("src/foo/bar_test.py")

    def test_top_level_test_prefix_sibling(self, tmp_path: Path):
        (tmp_path / "bar.py").write_text("x = 1\n")
        (tmp_path / "test_bar.py").write_text("# t\n")

        scope = EditScope.resolve(tmp_path, "bar.py")
        assert scope.allows_write("bar.py")
        assert scope.allows_write("test_bar.py")


class TestExpand:
    def test_expand_adds_file_to_scope(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        assert not scope.allows_write("b.py")
        scope.expand(tmp_path / "b.py")
        assert scope.allows_write("b.py")


class TestSummary:
    def test_summary_returns_sorted_relpaths(self, tmp_path: Path):
        (tmp_path / "src" / "foo").mkdir(parents=True)
        (tmp_path / "src" / "foo" / "bar.py").write_text("x = 1\n")
        (tmp_path / "tests" / "foo").mkdir(parents=True)
        (tmp_path / "tests" / "foo" / "test_bar.py").write_text("# t\n")

        scope = EditScope.resolve(tmp_path, "src/foo/bar.py")
        out = scope.summary()
        assert out == sorted(out)
        assert "src/foo/bar.py" in out
        assert "tests/foo/test_bar.py" in out


class TestCwdJail:
    def test_path_outside_cwd_denied(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1\n")
        scope = EditScope.resolve(tmp_path, "a.py")
        assert not scope.allows_write("/etc/passwd")
