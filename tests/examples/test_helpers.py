"""Tests for tests/examples/helpers.py (Phase 6 harness)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.examples.helpers import (
    REPO_ROOT,
    assert_no_repo_cache_artifacts,
    assert_python_parses,
    copy_example,
    deterministic_subprocess_env,
    example_source,
    run_cmd,
)


def test_example_source_returns_existing_path():
    path = example_source("classify")
    assert path.exists()
    assert path.name == "classify.voss"
    assert path.parent == REPO_ROOT / "samples"


def test_example_source_raises_for_missing():
    with pytest.raises(FileNotFoundError, match="canonical sample missing"):
        example_source("nonexistent_example_999")


def test_copy_example_writes_only_under_tmp_path(tmp_path: Path):
    dest = copy_example(tmp_path, "classify")
    assert dest.parent == tmp_path
    assert dest.exists()
    assert dest.name == "classify.voss"
    original = example_source("classify")
    assert dest.read_text() == original.read_text()


def test_run_cmd_captures_stdout_stderr_returncode(tmp_path: Path):
    result = run_cmd(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(42)"],
        cwd=tmp_path,
    )
    assert result.returncode == 42
    assert "out" in result.stdout
    assert "err" in result.stderr


def test_run_cmd_respects_cwd(tmp_path: Path):
    result = run_cmd(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert tmp_path.name in result.stdout


def test_assert_no_repo_cache_artifacts_catches_leaks(tmp_path: Path):
    cache_dir = tmp_path / ".voss-cache"
    cache_dir.mkdir()
    (cache_dir / "bad.idx").write_text("{}")
    with pytest.raises(AssertionError, match="repo-local indexes"):
        assert_no_repo_cache_artifacts(repo_root=tmp_path)


def test_assert_no_repo_cache_artifacts_ignores_pytest_cache(tmp_path: Path):
    cache_dir = tmp_path / ".pytest_cache" / ".voss-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "ok.idx").write_text("{}")
    # Should not raise
    assert_no_repo_cache_artifacts(repo_root=tmp_path)


def test_assert_python_parses_accepts_valid(tmp_path: Path):
    py = tmp_path / "valid.py"
    py.write_text("x = 1\n")
    assert_python_parses(py)


def test_assert_python_parses_rejects_invalid(tmp_path: Path):
    py = tmp_path / "bad.py"
    py.write_text("def (\n")
    with pytest.raises(AssertionError, match="did not parse"):
        assert_python_parses(py)


def test_deterministic_subprocess_env_contains_stub_config(tmp_path: Path):
    env = deterministic_subprocess_env(tmp_path, "test-value")
    assert "PYTHONPATH" in env
    stub_dir = tmp_path / "_voss_stub"
    assert str(stub_dir) in env["PYTHONPATH"]
    site_py = stub_dir / "sitecustomize.py"
    assert site_py.exists()
    content = site_py.read_text()
    assert "StubProvider" in content
    assert "test-value" in content
    assert "VOSS_TEST_STUB_RESPONSE" in env
    assert env["VOSS_TEST_STUB_RESPONSE"] == "test-value"


def test_deterministic_subprocess_env_python_configures_stub(tmp_path: Path):
    env = deterministic_subprocess_env(tmp_path, "hello-from-stub")
    result = run_cmd(
        [
            sys.executable,
            "-c",
            (
                "import voss_runtime;"
                "p = voss_runtime.providers.get('__stub__');"
                "print(p.default_response)"
            ),
        ],
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "hello-from-stub"
