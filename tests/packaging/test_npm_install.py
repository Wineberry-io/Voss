"""M6 NPM-04: pack @vosslang/cli, install via npm, smoke CLI surface via vendored Python.

Marked @pytest.mark.slow; mirrors tests/packaging/test_wheel_install.py for
the npm distribution surface. The whole module skips cleanly when any
prerequisite is missing (node, npm, host triple unsupported, or the host
platform subpackage's `python/` tree has not been built by
`npm/scripts/build_platform.py`). This keeps the test useful for both
contributors on a vanilla checkout and the M6-04 CI runners that
materialize `python/` as part of the release workflow.

Scope substitution: the M6 plans reference `@voss/cli` but M6-01 D-1
swapped to `@vosslang/cli` because the `voss` npm org was taken.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.packaging.test_entrypoint import _repo_root


SUPPORTED_TRIPLES = {
    "darwin-arm64",
    "darwin-x64",
    "linux-x64",
    "linux-arm64",
    "win32-x64",
}


def _host_triple() -> str | None:
    sys_map = {"darwin": "darwin", "linux": "linux", "windows": "win32"}
    mach_map = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "amd64": "x64",
    }
    s = sys_map.get(platform.system().lower())
    m = mach_map.get(platform.machine().lower())
    if not s or not m:
        return None
    triple = f"{s}-{m}"
    return triple if triple in SUPPORTED_TRIPLES else None


def _platform_python_built(triple: str) -> Path | None:
    p = _repo_root() / "npm" / "platforms" / triple / "python"
    return p if p.exists() else None


def _node_available() -> bool:
    return shutil.which("node") is not None


def _npm_available() -> bool:
    return shutil.which("npm") is not None


def _npm_pack(src_dir: Path, out_dir: Path) -> Path:
    """Run `npm pack <src_dir>` with cwd=out_dir; return the produced .tgz."""
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npm", "pack", str(src_dir)],
        cwd=str(out_dir),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    tarballs = list(out_dir.glob("*.tgz"))
    assert len(tarballs) >= 1, f"no .tgz in {out_dir}"
    # Return the most recently created tarball
    tarballs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return tarballs[0]


_TRIPLE = _host_triple()
_SKIP_REASONS = []
if not _node_available():
    _SKIP_REASONS.append("node not on PATH")
if not _npm_available():
    _SKIP_REASONS.append("npm not on PATH")
if _TRIPLE is None:
    _SKIP_REASONS.append("host triple not in supported set")
elif _platform_python_built(_TRIPLE) is None:
    _SKIP_REASONS.append(
        f"npm/platforms/{_TRIPLE}/python/ not built "
        f"(run: python3 npm/scripts/build_platform.py {_TRIPLE} "
        f"--out npm/platforms/{_TRIPLE}/python)"
    )

pytestmark = pytest.mark.skipif(
    bool(_SKIP_REASONS),
    reason="; ".join(_SKIP_REASONS) if _SKIP_REASONS else "",
)


@pytest.mark.slow
def test_npm_pack_main(tmp_path):
    """`npm pack npm/` produces exactly one .tgz starting with vosslang-cli-."""
    out_dir = tmp_path / "packs"
    tarball = _npm_pack(_repo_root() / "npm", out_dir)
    assert tarball.name.startswith("vosslang-cli-"), (
        f"expected vosslang-cli-*.tgz, got {tarball.name}"
    )


@pytest.mark.slow
def test_npm_install_and_help(tmp_path):
    """Pack main + host platform, install both into a fresh Node project,
    invoke `node node_modules/@vosslang/cli/bin/voss.js --help` and assert
    exit 0 with help text in stdout."""
    triple = _TRIPLE
    out_dir = tmp_path / "packs"
    main_tgz = _npm_pack(_repo_root() / "npm", out_dir)
    plat_tgz = _npm_pack(
        _repo_root() / "npm" / "platforms" / triple, out_dir
    )

    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(
        ["npm", "init", "-y"],
        cwd=str(proj),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["npm", "install", str(main_tgz), str(plat_tgz)],
        cwd=str(proj),
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )

    voss_js = proj / "node_modules" / "@vosslang" / "cli" / "bin" / "voss.js"
    assert voss_js.is_file(), f"shim missing at {voss_js}"

    r = subprocess.run(
        ["node", str(voss_js), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    combined = (r.stdout + r.stderr).lower()
    assert "usage" in combined or "voss" in combined, (
        f"help output looks wrong:\n{r.stdout}\n---stderr---\n{r.stderr}"
    )


@pytest.mark.slow
def test_npm_smoke_full(tmp_path):
    """Full post-install smoke: doctor + check + compile + vendored
    `import voss_runtime`. Asserts the M6 NPM-04 contract end-to-end."""
    triple = _TRIPLE
    out_dir = tmp_path / "packs"
    main_tgz = _npm_pack(_repo_root() / "npm", out_dir)
    plat_tgz = _npm_pack(
        _repo_root() / "npm" / "platforms" / triple, out_dir
    )

    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(
        ["npm", "init", "-y"],
        cwd=str(proj),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["npm", "install", str(main_tgz), str(plat_tgz)],
        cwd=str(proj),
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )

    voss_js = proj / "node_modules" / "@vosslang" / "cli" / "bin" / "voss.js"

    # voss doctor — exit ∈ {0, 1} per M1 D-13 (1 in a clean env without provider
    # creds; 0 if creds happen to be set on the host).
    r = subprocess.run(
        ["node", str(voss_js), "doctor"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode in {0, 1}, (
        f"voss doctor crashed: rc={r.returncode}\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}"
    )
    combined = (r.stdout + r.stderr).lower()
    assert "python" in combined or "provider" in combined, (
        f"doctor output missing expected tokens:\n{r.stdout}\n{r.stderr}"
    )

    # Inline .voss fixture (the wheel does not ship samples/). Minimal
    # valid Voss program: a no-op function. The grammar requires
    # parenthesized fn declarations; bare-block agent syntax mentioned in
    # RESEARCH §9 was an early draft that did not survive M2 grammar
    # finalization.
    smoke = tmp_path / "smoke.voss"
    smoke.write_text('fn smoke() -> string { return "ok" }\n', encoding="utf-8")

    # voss check <smoke.voss>
    r = subprocess.run(
        ["node", str(voss_js), "check", str(smoke)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr

    # voss compile <smoke.voss> -o <smoke.py>
    out_py = tmp_path / "smoke.py"
    r = subprocess.run(
        ["node", str(voss_js), "compile", str(smoke), "-o", str(out_py)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert out_py.is_file(), f"compile did not produce {out_py}"

    # Cross-confirm via the vendored python directly: import voss_runtime.
    if sys.platform == "win32":
        vendored = (
            proj
            / "node_modules"
            / "@vosslang"
            / f"cli-{triple}"
            / "python"
            / "python.exe"
        )
    else:
        # Fallback python3 → python3.12 (npm publish drops symlinks; only
        # python3.12 survives the tarball).
        plat_dir = proj / "node_modules" / "@vosslang" / f"cli-{triple}" / "python" / "bin"
        for name in ("python3", "python3.12"):
            candidate = plat_dir / name
            if candidate.exists():
                vendored = candidate
                break
        else:  # pragma: no cover — defensive
            raise AssertionError(f"no python interpreter under {plat_dir}")

    r = subprocess.run(
        [str(vendored), "-c", "import voss_runtime"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
