"""
CodeIntelService – high level orchestration for search (M10-03 Task 3).

This is the facade that later tools and slash commands will call.
For now it only implements the search path (ast-grep + regex fallback).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from . import ast_grep, regex_fallback
from .index import build_index, find_symbols, list_files
from .lsp_registry import LspRegistry
from .models import CodeLocation, IndexSummary, SearchHit, SymbolHit


class CodeIntelService:
    def __init__(self, cwd: Path, session_id: str | None = None):
        self.cwd = cwd.resolve()
        self.session_id = session_id

    @classmethod
    def for_cwd(cls, cwd: Path, session_id: str | None = None, renderer: Any = None) -> "CodeIntelService":
        # Ensure index exists (cheap if already built)
        try:
            build_index(cwd)
        except Exception:
            pass
        return cls(cwd, session_id)

    async def search(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """
        Structural / text search.
        Tries ast-grep first, falls back to regex.
        Returns a source-tagged envelope.
        """
        try:
            search_root = self._resolve_inside_cwd(path)
        except ValueError:
            return {"result": "error", "message": "path escapes cwd"}

        # Try ast-grep
        ast_result = await ast_grep.search(pattern, search_root, max_results=max_results)

        if isinstance(ast_result, list):
            return {
                "result": "ok",
                "source": "ast-grep",
                "hits": [self._hit_to_dict(h) for h in ast_result],
                "truncated": len(ast_result) >= max_results,
            }

        # Fallback to regex
        regex_result = await regex_fallback.search(pattern, search_root, max_results=max_results)

        if isinstance(regex_result, list):
            return {
                "result": "ok",
                "source": "regex",
                "fallback": "code_search.fallback=regex",
                "hits": [self._hit_to_dict(h) for h in regex_result],
                "truncated": len(regex_result) >= max_results,
            }

        return regex_result or {"result": "error", "message": "search failed"}

    def _hit_to_dict(self, hit: SearchHit) -> dict:
        return {
            "file": hit.location.file,
            "line": hit.location.line,
            "text": hit.matched_text,
            "language": hit.language,
            "source": hit.source,
        }

    def _resolve_inside_cwd(self, path: str | None = ".") -> Path:
        target = (self.cwd / (path or ".")).resolve()
        target.relative_to(self.cwd)
        return target

    def _location_to_dict(self, location: CodeLocation, *, source: str, language: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "file": location.file,
            "line": location.line,
            "column": location.column,
            "source": source,
        }
        if language:
            out["language"] = language
        if location.end_line is not None:
            out["end_line"] = location.end_line
        if location.end_column is not None:
            out["end_column"] = location.end_column
        return out

    def _symbol_to_dict(self, hit: SymbolHit) -> dict[str, Any]:
        return {
            "name": hit.name,
            "kind": hit.kind,
            "file": hit.location.file,
            "line": hit.location.line,
            "column": hit.location.column,
            "language": hit.language,
            "source": hit.source,
            "score": hit.score,
        }

    # --- Lazy registries for semantic operations (M10-04) ---
    def _get_registry(self) -> LspRegistry:
        if not hasattr(self, "_registry") or self._registry is None:
            self._registry = LspRegistry(self.cwd, self.session_id or "default")
        return self._registry

    # --- Lazy semantic code index (V19-03) ---
    def _get_code_index_service(self):
        """Only construction site for CodeIndexService — never eager in
        __init__/for_cwd (the embedding cold-load must stay off the session
        thread; the service's build runs on its own daemon thread)."""
        if not hasattr(self, "_code_index_service") or self._code_index_service is None:
            from .semantic_index import CodeIndexService

            self._code_index_service = CodeIndexService(self.cwd, session_id=self.session_id)
            self._code_index_service.ensure_background_build()
        return self._code_index_service

    async def find_definition(
        self, symbol: str, path: str | None = None
    ) -> dict[str, Any]:
        """Best-effort definition lookup using the index, with optional LSP enrichment."""
        try:
            if path:
                self._resolve_inside_cwd(path)
            candidates = find_symbols(self.cwd, symbol, path=path, max_results=20)
        except ValueError:
            return {"result": "error", "message": "path escapes cwd"}

        lsp_meta: dict[str, Any] | None = None
        lsp_items: list[dict[str, Any]] = []
        if candidates:
            first = candidates[0]
            target = (self.cwd / first.location.file).resolve()
            try:
                target.relative_to(self.cwd)
                reg = self._get_registry()
                lsp_result = await reg.find_definition(
                    first.language,
                    target.as_uri(),
                    max(first.location.line - 1, 0),
                    first.location.column,
                )
                if isinstance(lsp_result, list) and lsp_result:
                    lsp_items = [
                        self._location_to_dict(loc, source="lsp", language=first.language)
                        for loc in lsp_result
                    ]
                elif isinstance(lsp_result, dict):
                    lsp_meta = lsp_result
            except Exception as exc:
                lsp_meta = {"result": "lsp_unavailable", "reason": str(exc), "fallback": "index"}

        items = lsp_items or [self._symbol_to_dict(hit) for hit in candidates]
        return {
            "result": "ok" if items else "not_found",
            "symbol": symbol,
            "source": "lsp" if lsp_items else "index",
            "items": items,
            "lsp": lsp_meta,
        }

    async def find_references(
        self, symbol: str, path: str | None = None, max_results: int = 50
    ) -> dict[str, Any]:
        try:
            search_root = self._resolve_inside_cwd(path)
        except ValueError:
            return {"result": "error", "message": "path escapes cwd"}

        lsp_meta: dict[str, Any] | None = None
        candidates = find_symbols(self.cwd, symbol, path=path, max_results=1)
        if candidates:
            first = candidates[0]
            target = (self.cwd / first.location.file).resolve()
            try:
                target.relative_to(self.cwd)
                reg = self._get_registry()
                lsp_result = await reg.find_references(
                    first.language,
                    target.as_uri(),
                    max(first.location.line - 1, 0),
                    first.location.column,
                )
                if isinstance(lsp_result, list) and lsp_result:
                    return {
                        "result": "ok",
                        "symbol": symbol,
                        "source": "lsp",
                        "items": [
                            self._location_to_dict(hit.location, source=hit.source, language=hit.language)
                            | ({"context": hit.context} if hit.context else {})
                            for hit in lsp_result[:max_results]
                        ],
                        "truncated": len(lsp_result) > max_results,
                    }
                if isinstance(lsp_result, dict):
                    lsp_meta = lsp_result
            except Exception as exc:
                lsp_meta = {"result": "lsp_unavailable", "reason": str(exc), "fallback": "regex"}

        items = self._regex_references(symbol, search_root, max_results=max_results)
        return {
            "result": "ok" if items else "not_found",
            "symbol": symbol,
            "source": "regex",
            "fallback": "find_references.fallback=regex",
            "items": items,
            "truncated": len(items) >= max_results,
            "lsp": lsp_meta,
        }

    def find_symbols(self, symbol: str, path: str | None = None, max_results: int = 10) -> dict[str, Any]:
        try:
            if path:
                self._resolve_inside_cwd(path)
            hits = find_symbols(self.cwd, symbol, path=path, max_results=max_results)
        except ValueError:
            return {"result": "error", "message": "path escapes cwd"}
        return {
            "result": "ok" if hits else "not_found",
            "symbol": symbol,
            "source": "index",
            "items": [self._symbol_to_dict(hit) for hit in hits],
            "truncated": len(hits) >= max_results,
        }

    def _regex_references(self, symbol: str, root: Path, *, max_results: int) -> list[dict[str, Any]]:
        pattern = re.compile(rf"\b{re.escape(symbol)}\b")
        root = root.resolve()
        files = list_files(self.cwd)
        hits: list[dict[str, Any]] = []
        for rel, lang in files:
            full = (self.cwd / rel).resolve()
            try:
                full.relative_to(root)
            except ValueError:
                continue
            if not full.is_file():
                continue
            try:
                lines = full.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, 1):
                if pattern.search(line):
                    hits.append({
                        "file": rel,
                        "line": line_no,
                        "column": 0,
                        "language": lang,
                        "source": "regex",
                        "context": line[:120],
                    })
                    if len(hits) >= max_results:
                        return hits
        return hits

    async def code_refresh(self, paths: list[str] | None = None) -> dict[str, Any]:
        """Rebuild the project index (cache only)."""
        try:
            from .index import build_index
            build_index(self.cwd)
            return {"result": "ok", "action": "refreshed", "path": str(self.cwd / ".voss-cache/code/index.db")}
        except Exception as e:
            return {"result": "error", "message": str(e)}

    def get_project_index_summary(self, max_modules: int = 20) -> "IndexSummary | None":
        """Return the current index summary for context injection (M10-05)."""
        try:
            from .index import summarize as _summarize
            return _summarize(self.cwd, max_modules=max_modules)
        except Exception:
            return None
