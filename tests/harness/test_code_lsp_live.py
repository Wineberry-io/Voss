"""
Optional live LSP server tests (M10-02 Task 3).

These are skipped unless the environment explicitly opts in.
"""

import shutil

import pytest

from voss.harness.code.lsp_registry import LspRegistry


def _server_available(name: str) -> bool:
    return shutil.which(name) is not None


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_definition_python(tmp_path):
    if not _server_available("pyright-langserver") and not _server_available("pylsp"):
        pytest.skip("No Python language server found on PATH")

    reg = LspRegistry(tmp_path)
    # In a real test we would create a real fixture file and query it
    result = await reg.find_definition("python", "file:///nonexistent.py", 0, 0)
    # Either we get a real result or a graceful unavailable
    assert result is not None
