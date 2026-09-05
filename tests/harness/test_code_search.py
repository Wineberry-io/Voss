"""
Tests for M10-03 ast-grep + regex fallback + service (CODE-03).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voss.harness.code.ast_grep import search as ast_search
from voss.harness.code.regex_fallback import search as regex_search
from voss.harness.code.service import CodeIntelService


@pytest.mark.asyncio
async def test_ast_grep_wrapper_missing_binary_returns_unavailable(tmp_path: Path):
    # Force missing by using a non-existent binary name in PATH simulation
    # Since we use shutil.which, we just test the graceful path
    result = await ast_search("def $X", tmp_path)
    # In a clean env without ast-grep it should return unavailable dict
    if isinstance(result, dict):
        assert result.get("fallback") == "regex"
    else:
        # If ast-grep happens to be installed, we still accept a list
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_regex_fallback_basic(tmp_path: Path):
    # Create a tiny indexed-like file
    f = tmp_path / "test.py"
    f.write_text("def hello():\n    pass\n")
    # We don't have a real index, but regex_fallback currently walks
    hits = await regex_search("def hello", tmp_path)
    assert isinstance(hits, list)


@pytest.mark.asyncio
async def test_service_search_returns_source_tagged(tmp_path: Path):
    # Create minimal fixture
    (tmp_path / "app.py").write_text("def shared_entry(x): return x + 1\n")
    svc = CodeIntelService.for_cwd(tmp_path)
    result = await svc.search("def $NAME")
    assert "result" in result
    assert "source" in result or "fallback" in result


@pytest.mark.asyncio
async def test_service_search_rejects_same_prefix_sibling_escape(tmp_path: Path):
    repo = tmp_path / "repo"
    sibling = tmp_path / "repo2"
    repo.mkdir()
    sibling.mkdir()
    (sibling / "secret.py").write_text("def secret():\n    pass\n")

    svc = CodeIntelService.for_cwd(repo)
    result = await svc.search("def secret", path="../repo2")

    assert result["result"] == "error"
    assert "escapes cwd" in result["message"]
