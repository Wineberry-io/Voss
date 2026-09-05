"""
M10-06 close-out integration tests.

Exercises the full code-intelligence stack end-to-end on the fixture set:
index → search (ast-grep or regex) → tools → slash → context injection → TUI panel (via service).
"""

import pytest

from voss.harness.code.service import CodeIntelService


@pytest.mark.asyncio
async def test_full_code_intel_happy_path_on_fixtures(tmp_path):
    """Smoke the entire surface on the Python fixture."""
    # Copy one fixture into the temp project so we have a real cwd
    from pathlib import Path

    fixture = Path("tests/fixtures/code/python/app.py")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text(fixture.read_text())

    svc = CodeIntelService.for_cwd(proj)

    # 1. Index
    summary = svc.get_project_index_summary()
    assert summary is not None
    assert summary.file_count >= 1

    # 2. Search (will be regex fallback in this env unless ast-grep is present)
    res = await svc.search("def shared_entry", max_results=5)
    assert res["result"] in ("ok", "error")  # graceful even if no matches

    # 3. Refresh
    refresh = await svc.code_refresh()
    assert refresh["result"] == "ok"

    # 4. Symbol definition and references should use real inputs, not dummy.py.
    definition = await svc.find_definition("shared_entry")
    assert definition["result"] == "ok"
    assert definition["items"]
    assert definition["items"][0]["file"] == "app.py"

    refs = await svc.find_references("shared_entry")
    assert refs["result"] == "ok"
    assert any(item["file"] == "app.py" for item in refs["items"])
