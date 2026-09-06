"""D-07 codegen snapshot coverage for memory.semantic and memory.working."""
from __future__ import annotations

from pathlib import Path


from tests.codegen.test_examples import _compile_example
from tests.codegen.test_snapshots import _assert_readable_snapshot


SNAPSHOTS_COVERAGE = Path(__file__).resolve().parent / "snapshots" / "coverage"
COVERAGE_NAMES = ("memory_semantic", "memory_working")


def _generated_coverage_sources(tmp_path: Path) -> dict[str, str]:
    return {
        name: _compile_example(tmp_path, f"coverage/{name}").source
        for name in COVERAGE_NAMES
    }


def test_generated_coverage_sources_match_snapshots(tmp_path):
    generated = _generated_coverage_sources(tmp_path)
    for name, source in generated.items():
        snapshot = (SNAPSHOTS_COVERAGE / f"{name}.py").read_text()
        assert source == snapshot, f"snapshot drift in coverage/{name}.py"


def test_coverage_snapshots_are_readable_and_parseable():
    for name in COVERAGE_NAMES:
        snapshot = (SNAPSHOTS_COVERAGE / f"{name}.py").read_text()
        _assert_readable_snapshot(name, snapshot)
