"""End-to-end validation for ``research.voss`` (PRD §7.3, EX-03).

Tests are deterministic: a ``StubProvider`` returns ``"STUB SUMMARY"`` for every
ask call, and the timeout-fallback test forces ``run_with_budget`` to raise
``BudgetExceededError`` rather than relying on real wall-clock latency.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path


from tests.examples.helpers import (
    assert_no_repo_cache_artifacts,
    assert_python_parses,
    copy_example,
    deterministic_subprocess_env,
    register_stub,
    run_cmd,
    run_voss,
)


STUB_SUMMARY = "STUB SUMMARY"


# Sitecustomize fragment that supplies a `webSearch` ToolDescriptor in builtins
# so generated research code can resolve the bare name.
RESEARCH_SUBPROCESS_SITECUSTOMIZE = """
import builtins as _builtins
from voss_runtime import tool as _voss_tool


@_voss_tool
def webSearch(query: str, max_results: int = 5) -> list:
    return [f"result-{i} for {query}" for i in range(max_results)]


_builtins.webSearch = webSearch
"""


def _import_generated_module(path: Path, *, name: str) -> object:
    """Import a generated module with a ``webSearch`` ToolDescriptor in scope.

    The generated research module references ``webSearch`` at module load time
    (``tools = (webSearch,)``), so we seed the module dict before execution.
    """
    from examples.raw_python.research import web_search

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    module.__dict__["webSearch"] = web_search
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _compile_research_in_process(tmp_path: Path) -> Path:
    """Compile ``research.voss`` via the in-process API and return generated path."""
    from voss import analyze, generate_python, parse

    src_path = tmp_path / "research.voss"
    if not src_path.exists():
        copy_example(tmp_path, "research")
    program = parse(src_path.read_text(), file=str(src_path))
    analysis = analyze(
        program,
        source_path=str(src_path),
        project_root=tmp_path,
        cache_dir=Path(".voss-cache"),
        emit_indexes=True,
    )
    assert not analysis.errors
    result = generate_python(
        program,
        source_path=str(src_path),
        analysis=analysis,
        project_root=tmp_path,
        cache_dir=Path(".voss-cache"),
    )
    out_path = tmp_path / "out" / "research.py"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.source)
    assert_python_parses(out_path)
    return out_path


def _inject_research_helpers(module) -> None:
    """Provide a ``webSearch`` ToolDescriptor to the generated research module."""
    from examples.raw_python.research import web_search

    module.webSearch = web_search


def test_research_check_has_no_errors(tmp_path: Path):
    copy_example(tmp_path, "research")

    result = run_voss(["check", "research.voss"], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "error" not in result.stderr.lower()
    assert not (tmp_path / "research.py").exists()
    assert not (tmp_path / ".voss-cache").exists()
    assert_no_repo_cache_artifacts()


def test_research_compile_python_happy_path_matches_raw(tmp_path: Path):
    out_path = _compile_research_in_process(tmp_path)
    source = out_path.read_text()
    # Must not import compiler-only modules.
    assert "from voss " not in source
    assert "import voss\n" not in source
    assert "voss.analyzer" not in source
    assert "voss.codegen" not in source

    module = _import_generated_module(out_path, name="voss_generated_research_happy")
    _inject_research_helpers(module)

    from examples.raw_python.research import run_research as raw_run_research

    with register_stub(STUB_SUMMARY):
        generated_value = asyncio.run(module.runResearch("Anthropic"))
        raw_value = asyncio.run(raw_run_research("Anthropic"))

    assert generated_value, "generated runResearch must produce non-empty output"
    assert raw_value, "raw run_research must produce non-empty output"
    assert generated_value == STUB_SUMMARY
    assert raw_value == STUB_SUMMARY
    assert generated_value == raw_value


def test_research_timeout_fallback_matches_raw(tmp_path: Path, monkeypatch):
    out_path = _compile_research_in_process(tmp_path)
    module = _import_generated_module(out_path, name="voss_generated_research_fallback")
    _inject_research_helpers(module)

    import examples.raw_python.research as raw_module
    from voss_runtime.exceptions import BudgetExceededError

    async def _force_budget_exceeded(*args, **kwargs):
        raise BudgetExceededError(
            reason="latency",
            limit=kwargs.get("latency_ms"),
            observed=10**9,
            scope=kwargs.get("name", ""),
        )

    monkeypatch.setattr(module, "run_with_budget", _force_budget_exceeded)
    monkeypatch.setattr(raw_module, "run_with_budget", _force_budget_exceeded)

    expected = "\n---\n".join([STUB_SUMMARY] * 4)

    with register_stub(STUB_SUMMARY):
        generated_value = asyncio.run(module.runResearch("Anthropic"))
        raw_value = asyncio.run(raw_module.run_research("Anthropic"))

    assert generated_value == expected
    assert raw_value == expected
    assert generated_value == raw_value


def test_research_generated_contains_use_and_try_catch_lowerings(tmp_path: Path):
    """D-06: generated Python contains the use lowering AND try/except + fallback string."""
    out_path = _compile_research_in_process(tmp_path)
    generated_source = out_path.read_text()

    assert "from voss_runtime.tools import tool" in generated_source, generated_source[:500]
    assert "try:" in generated_source
    assert "except" in generated_source
    assert "web search unavailable" in generated_source


def test_research_voss_run_matches_compile_python(tmp_path: Path):
    copy_example(tmp_path, "research")

    env = deterministic_subprocess_env(
        tmp_path,
        default_response=STUB_SUMMARY,
        extra_sitecustomize=RESEARCH_SUBPROCESS_SITECUSTOMIZE,
    )

    out_path = tmp_path / "out" / "research.py"
    compile_result = run_voss(
        ["compile", "research.voss", "-o", str(out_path)],
        cwd=tmp_path,
        env=env,
    )
    assert compile_result.returncode == 0, compile_result.stderr
    assert out_path.exists()
    assert_python_parses(out_path)

    py_run = run_cmd(
        [sys.executable, str(out_path)],
        cwd=tmp_path,
        env=env,
        timeout=120.0,
    )
    assert py_run.returncode == 0, py_run.stderr
    assert "Traceback" not in py_run.stderr

    voss_run = run_voss(["run", "research.voss"], cwd=tmp_path, env=env, timeout=120.0)
    assert voss_run.returncode == 0, voss_run.stderr
    assert "Traceback" not in voss_run.stderr

    assert voss_run.stdout == py_run.stdout
    assert STUB_SUMMARY in voss_run.stdout
    assert_no_repo_cache_artifacts()
