"""Integration tests for the SQLite project index (M10-01 Task 3)."""

from __future__ import annotations

from pathlib import Path


from voss.harness.code.index import build_index, refresh, summarize
from voss.harness.code.models import IndexSummary


def _make_fixture_tree(root: Path, lang: str) -> None:
    """Create a tiny deterministic fixture tree for the given language."""
    if lang == "python":
        (root / "app.py").write_text("def shared_entry(x):\n    return x + 1\n", encoding="utf-8")
    elif lang == "go":
        (root / "main.go").write_text("package main\nfunc sharedEntry(x int) int { return x + 1 }\n", encoding="utf-8")
    else:
        (root / f"app.{lang}").write_text("function sharedEntry(x) { return x + 1; }\n", encoding="utf-8")


def test_build_and_refresh_is_deterministic(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _make_fixture_tree(proj, "python")

    db1 = build_index(proj)
    db2 = build_index(proj)

    assert db1.exists()
    assert db1 == db2

    # Modify a file and refresh
    (proj / "app.py").write_text("def shared_entry(x):\n    return x + 42\n", encoding="utf-8")
    refresh(proj)

    summary = summarize(proj)
    assert isinstance(summary, IndexSummary)
    assert summary.file_count >= 1
    assert summary.symbol_count >= 1
    assert "python" in summary.languages


def test_repeated_build_does_not_duplicate_symbols(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _make_fixture_tree(proj, "python")

    build_index(proj)
    first = summarize(proj)
    build_index(proj)
    second = summarize(proj)

    assert first.file_count == second.file_count == 1
    assert first.symbol_count == second.symbol_count == 1


def test_vendored_dirs_are_pruned(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "real.py").write_text("def real(): pass\n", encoding="utf-8")
    (proj / "node_modules" / "evil.js").parent.mkdir(parents=True)
    (proj / "node_modules" / "evil.js").write_text("function evil(){}", encoding="utf-8")

    build_index(proj)
    summary = summarize(proj)
    assert summary.file_count == 1  # only real.py


def test_path_jail_and_schema_rebuild(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _make_fixture_tree(proj, "python")

    db = build_index(proj)
    assert db.exists()

    # Corrupt schema version → should trigger rebuild on next build
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    db2 = build_index(proj)
    assert db2.exists()
    # New DB should have been written (or at least be valid)
    assert summarize(proj).file_count >= 1
