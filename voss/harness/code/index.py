"""SQLite-backed project index (CODE-01 foundation).

Storage: .voss-cache/code/index.db (rebuildable cache, never durable).

This module performs only filesystem scanning + best-effort symbol extraction
via simple language regexes. No LSP or ast-grep calls are made here.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
import hashlib
from pathlib import Path
from typing import Iterable

from .models import CodeLocation, IndexSummary, SymbolHit

DB_NAME = "index.db"
SCHEMA_VERSION = 1

VENDORED_DIRS = {
    ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    "node_modules", "bower_components",
    "dist", "build", "target", "out",
    ".voss-cache", ".cache",
    "__pycache__", ".mypy_cache", ".ruff_cache",
}

LANGUAGE_EXTS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
}

# Very lightweight symbol extraction — good enough for index + later LSP enrichment
SYMBOL_PATTERNS = {
    "python": re.compile(r"^(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M),
    "javascript": re.compile(r"(?:function\s+|const\s+|let\s+|var\s+)([A-Za-z_][A-Za-z0-9_]*)\s*[=:(]", re.M),
    "typescript": re.compile(r"(?:function\s+|const\s+|let\s+|var\s+|export\s+(?:function|const|let|class)\s+)([A-Za-z_][A-Za-z0-9_]*)", re.M),
    "rust": re.compile(r"(?:pub\s+)?(?:fn|struct|enum|trait|impl)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M),
    "go": re.compile(r"^(?:func|type)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M),
}


def _is_vendored(path: Path) -> bool:
    parts = path.parts
    return any(p in VENDORED_DIRS for p in parts)


def _discover_files(root: Path) -> list[Path]:
    """Prefer git ls-files, fall back to os.walk with pruning."""
    git_dir = root / ".git"
    files: list[Path] = []

    if git_dir.exists():
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                cwd=root,
                text=True,
                timeout=10,
            )
            for line in out.splitlines():
                p = (root / line).resolve()
                if p.is_file() and not _is_vendored(p.relative_to(root)):
                    files.append(p)
            return files
        except Exception:
            pass  # fall through to walk

    # Walk fallback with aggressive pruning
    for dirpath, dirnames, filenames in os.walk(root):
        # prune in place
        dirnames[:] = [d for d in dirnames if d not in VENDORED_DIRS]
        for fname in filenames:
            p = Path(dirpath) / fname
            rel = p.relative_to(root)
            if not _is_vendored(rel):
                files.append(p)
    return files


def _extract_symbols(text: str, language: str) -> list[tuple[str, int]]:
    pattern = SYMBOL_PATTERNS.get(language)
    if not pattern:
        return []
    symbols: list[tuple[str, int]] = []
    for match in pattern.finditer(text):
        name = match.group(1)
        line = text.count("\n", 0, match.start()) + 1
        symbols.append((name, line))
        if len(symbols) >= 200:
            break
    return symbols


def _get_db_path(cwd: Path) -> Path:
    return cwd / ".voss-cache" / "code" / DB_NAME


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            lang TEXT,
            mtime REAL,
            hash TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            kind TEXT,
            line INTEGER,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")

    # Record schema version
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()


def _needs_rebuild(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        conn.close()
        return row is None or int(row[0]) != SCHEMA_VERSION
    except Exception:
        return True


def build_index(cwd: Path) -> Path:
    """Full deterministic rebuild of the project index."""
    cwd = cwd.resolve()
    db_path = _get_db_path(cwd)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if _needs_rebuild(db_path):
        if db_path.exists():
            db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        conn.execute("DELETE FROM symbols")
        conn.execute("DELETE FROM files")

        files = sorted(_discover_files(cwd), key=lambda p: str(p.relative_to(cwd)))

        for f in files:
            try:
                rel = str(f.relative_to(cwd))
                lang = LANGUAGE_EXTS.get(f.suffix.lower(), "unknown")
                mtime = f.stat().st_mtime
                content = f.read_text(encoding="utf-8", errors="ignore")
                digest = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()

                cur = conn.execute(
                    "INSERT OR REPLACE INTO files (path, lang, mtime, hash) VALUES (?, ?, ?, ?)",
                    (rel, lang, mtime, digest),
                )
                file_id = cur.lastrowid

                symbols = _extract_symbols(content, lang)
                for name, line in symbols:
                    conn.execute(
                        "INSERT INTO symbols (file_id, name, kind, line) VALUES (?, ?, ?, ?)",
                        (file_id, name, "symbol", line),
                    )
            except Exception:
                continue  # never let one bad file kill the scan

        conn.commit()
    finally:
        conn.close()

    return db_path


def refresh(cwd: Path, paths: Iterable[str] | None = None) -> Path:
    """Rebuild the index (full rebuild in v0.2; paths param is accepted for future partial support)."""
    # For v0.2 we always do a full deterministic rebuild.
    return build_index(cwd)


def list_files(cwd: Path) -> list[tuple[str, str]]:
    """Return indexed files as (relative path, language), rebuilding if needed."""
    cwd = cwd.resolve()
    db_path = _get_db_path(cwd)
    if not db_path.exists() or _needs_rebuild(db_path):
        build_index(cwd)

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT path, lang FROM files ORDER BY path"
        ).fetchall()
        return [(path, lang) for path, lang in rows]
    finally:
        conn.close()


def find_symbols(cwd: Path, query: str, path: str | None = None, max_results: int = 20) -> list[SymbolHit]:
    """Find indexed symbols by exact or substring match."""
    cwd = cwd.resolve()
    db_path = _get_db_path(cwd)
    if not db_path.exists() or _needs_rebuild(db_path):
        build_index(cwd)

    params: list[object] = [query, f"%{query}%", max_results]
    path_filter = ""
    if path:
        rel_root = (cwd / path).resolve().relative_to(cwd)
        rel_text = str(rel_root)
        path_filter = "AND (files.path = ? OR files.path LIKE ?)"
        params = [query, f"%{query}%", rel_text, f"{rel_text.rstrip('/')}/%", max_results]

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT symbols.name, symbols.kind, symbols.line, files.path, files.lang
            FROM symbols
            JOIN files ON symbols.file_id = files.id
            WHERE (symbols.name = ? OR symbols.name LIKE ?) {path_filter}
            ORDER BY CASE WHEN symbols.name = ? THEN 0 ELSE 1 END, files.path, symbols.line
            LIMIT ?
            """,
            (*params[:-1], query, params[-1]) if not path_filter else (*params[:-1], query, params[-1]),
        ).fetchall()
        return [
            SymbolHit(
                name=name,
                kind=kind or "symbol",
                location=CodeLocation(file=file_path, line=int(line or 1), column=0),
                language=lang or "unknown",
                source="index",
            )
            for name, kind, line, file_path, lang in rows
        ]
    finally:
        conn.close()


def summarize(cwd: Path, max_modules: int = 20) -> IndexSummary:
    """Return a compact, snippet-free summary suitable for system context."""
    cwd = cwd.resolve()
    db_path = _get_db_path(cwd)
    if not db_path.exists() or _needs_rebuild(db_path):
        build_index(cwd)

    conn = sqlite3.connect(db_path)
    try:
        file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbol_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]

        lang_rows = conn.execute(
            "SELECT lang, COUNT(*) FROM files GROUP BY lang ORDER BY COUNT(*) DESC"
        ).fetchall()
        languages = {lang: cnt for lang, cnt in lang_rows}

        module_rows = conn.execute(
            """
            SELECT path, COUNT(*) as cnt
            FROM symbols
            JOIN files ON symbols.file_id = files.id
            GROUP BY path
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (max_modules,),
        ).fetchall()
        top_modules = [(path, cnt) for path, cnt in module_rows]

        # Very crude entry point detection
        entry_points: list[str] = []
        for row in conn.execute("SELECT path FROM files WHERE path LIKE '%main%' OR path LIKE '%app%' LIMIT 5"):
            entry_points.append(row[0])

        return IndexSummary(
            file_count=file_count,
            symbol_count=symbol_count,
            languages=languages,
            top_modules=top_modules,
            entry_points=entry_points,
            scanned_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            partial=False,
        )
    finally:
        conn.close()
