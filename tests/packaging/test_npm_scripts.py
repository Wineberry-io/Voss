"""M6-03 NPM-02: fast unit tests for bump_version.py and prune_pbs.py.

These tests build a synthetic npm/ tree in tmp_path and invoke each
script as a subprocess so the scripts run exactly as they would in
M6-04 CI. The build_platform.py script is NOT covered here — its full
exercise is the [BLOCKING] host build in Task 3 of M6-03 (real PBS
download + pip install). Static AST checks of build_platform.py live
in the plan's verify block, not in this test module.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


from tests.packaging.test_entrypoint import _repo_root


PLATFORMS = ["darwin-arm64", "darwin-x64", "linux-x64", "linux-arm64", "win32-x64"]
BUMP_SCRIPT = _repo_root() / "npm" / "scripts" / "bump_version.py"
PRUNE_SCRIPT = _repo_root() / "npm" / "scripts" / "prune_pbs.py"


# ---------- helpers ----------------------------------------------------------


def _make_fake_repo(tmp_path: Path, version: str) -> Path:
    """Build a tree shaped exactly like the real repo so bump_version.py's
    `parents[2]` resolves to tmp_path. The script is copied in-place."""
    repo = tmp_path / "fake-repo"
    (repo / "npm" / "scripts").mkdir(parents=True)
    (repo / "npm" / "platforms").mkdir()
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        f'[project]\nname = "voss"\nversion = "{version}"\n', encoding="utf-8"
    )
    main_pkg = {
        "name": "@vosslang/cli",
        "version": "0.0.0",
        "optionalDependencies": {f"@vosslang/cli-{t}": "0.0.0" for t in PLATFORMS},
    }
    (repo / "npm" / "package.json").write_text(
        json.dumps(main_pkg, indent=2) + "\n", encoding="utf-8"
    )
    for t in PLATFORMS:
        d = repo / "npm" / "platforms" / t
        d.mkdir()
        (d / "package.json").write_text(
            json.dumps({"name": f"@vosslang/cli-{t}", "version": "0.0.0"}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    shutil.copy(BUMP_SCRIPT, repo / "npm" / "scripts" / "bump_version.py")
    return repo


def _run_bump(repo: Path, *args: str) -> subprocess.CompletedProcess:
    script = repo / "npm" / "scripts" / "bump_version.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _make_unix_tree(root: Path) -> None:
    (root / "python" / "bin").mkdir(parents=True)
    (root / "python" / "bin" / "python3").write_text("#!stub\n")
    (root / "python" / "bin" / "idle3").write_text("idle stub\n")
    (root / "python" / "include").mkdir()
    (root / "python" / "include" / "Python.h").write_text("/* stub */\n")
    libpy = root / "python" / "lib" / "python3.12"
    libpy.mkdir(parents=True)
    (libpy / "idlelib").mkdir()
    (libpy / "idlelib" / "__init__.py").write_text("")
    (libpy / "tkinter").mkdir()
    (libpy / "tkinter" / "Tkinter.py").write_text("")
    sp = libpy / "site-packages"
    sp.mkdir()
    (sp / ".placeholder").write_text("")


def _make_windows_tree(root: Path) -> None:
    py = root / "python"
    py.mkdir(parents=True)
    (py / "python.exe").write_bytes(b"MZstub")
    (py / "pythonw.exe").write_bytes(b"MZstub")
    (py / "Lib").mkdir()
    (py / "Lib" / "idlelib").mkdir()
    (py / "Lib" / "idlelib" / "__init__.py").write_text("")
    (py / "Lib" / "site-packages").mkdir()
    (py / "tcl").mkdir()
    (py / "tcl" / "init.tcl").write_text("")
    (py / "include").mkdir()


def _run_prune(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PRUNE_SCRIPT), str(root), *extra],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------- bump_version tests -----------------------------------------------


def test_bump_all_rewrites_six_files(tmp_path):
    repo = _make_fake_repo(tmp_path, "0.2.3")
    result = _run_bump(repo)
    assert result.returncode == 0, result.stderr
    main = json.loads((repo / "npm" / "package.json").read_text())
    assert main["version"] == "0.2.3"
    for v in main["optionalDependencies"].values():
        assert v == "0.2.3"
    for t in PLATFORMS:
        sub = json.loads((repo / "npm" / "platforms" / t / "package.json").read_text())
        assert sub["version"] == "0.2.3"


def test_bump_main_only_touches_main_pkg(tmp_path):
    repo = _make_fake_repo(tmp_path, "0.3.0")
    result = _run_bump(repo, "main")
    assert result.returncode == 0, result.stderr
    main = json.loads((repo / "npm" / "package.json").read_text())
    assert main["version"] == "0.3.0"
    # Platform files must still be at the original 0.0.0
    for t in PLATFORMS:
        sub = json.loads((repo / "npm" / "platforms" / t / "package.json").read_text())
        assert sub["version"] == "0.0.0", f"{t} should be untouched"


def test_bump_single_triple_only_touches_that_platform(tmp_path):
    repo = _make_fake_repo(tmp_path, "0.4.1")
    result = _run_bump(repo, "darwin-arm64")
    assert result.returncode == 0, result.stderr
    main = json.loads((repo / "npm" / "package.json").read_text())
    assert main["version"] == "0.0.0"
    only = json.loads(
        (repo / "npm" / "platforms" / "darwin-arm64" / "package.json").read_text()
    )
    assert only["version"] == "0.4.1"
    for t in [p for p in PLATFORMS if p != "darwin-arm64"]:
        sub = json.loads((repo / "npm" / "platforms" / t / "package.json").read_text())
        assert sub["version"] == "0.0.0", f"{t} should be untouched"


def test_bump_uses_two_space_indent_and_trailing_newline(tmp_path):
    repo = _make_fake_repo(tmp_path, "0.5.0")
    _run_bump(repo)
    text = (repo / "npm" / "package.json").read_text(encoding="utf-8")
    assert text.endswith("\n"), "missing trailing newline"
    # 2-space indent: the first nested line should start with exactly 2 spaces
    indented = [ln for ln in text.splitlines() if ln.startswith(" ")]
    assert indented, "no indented lines found"
    assert indented[0].startswith("  ") and not indented[0].startswith("    "), (
        f"expected 2-space indent, got: {indented[0]!r}"
    )


def test_bump_rejects_invalid_target(tmp_path):
    repo = _make_fake_repo(tmp_path, "0.6.0")
    result = _run_bump(repo, "not-a-triple")
    assert result.returncode != 0
    assert "unknown target" in result.stderr or "Expected one of" in result.stderr


# ---------- prune_pbs tests --------------------------------------------------


def test_prune_unix_removes_idlelib_tkinter_include_keeps_site_packages(tmp_path):
    _make_unix_tree(tmp_path)
    result = _run_prune(tmp_path)
    assert result.returncode == 0, result.stderr
    py = tmp_path / "python"
    assert not (py / "lib" / "python3.12" / "idlelib").exists()
    assert not (py / "lib" / "python3.12" / "tkinter").exists()
    assert not (py / "include").exists()
    assert not (py / "bin" / "idle3").exists()
    # Preserved:
    assert (py / "lib" / "python3.12" / "site-packages").exists()
    assert (py / "lib" / "python3.12" / "site-packages" / ".placeholder").exists()
    assert (py / "bin" / "python3").exists()


def test_prune_is_idempotent(tmp_path):
    _make_unix_tree(tmp_path)
    first = _run_prune(tmp_path)
    assert first.returncode == 0, first.stderr
    second = _run_prune(tmp_path)
    assert second.returncode == 0, second.stderr
    # Second run should report nothing actively removed; site-packages still present
    assert (tmp_path / "python" / "lib" / "python3.12" / "site-packages").exists()


def test_prune_windows_shape_detected_and_targets_removed(tmp_path):
    _make_windows_tree(tmp_path)
    result = _run_prune(tmp_path)
    assert result.returncode == 0, result.stderr
    py = tmp_path / "python"
    assert not (py / "pythonw.exe").exists()
    assert not (py / "Lib" / "idlelib").exists()
    assert not (py / "tcl").exists()
    assert not (py / "include").exists()
    # Preserved:
    assert (py / "python.exe").exists()
    assert (py / "Lib" / "site-packages").exists()
    assert "shape=windows" in result.stdout
