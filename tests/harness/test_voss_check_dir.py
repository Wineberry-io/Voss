from __future__ import annotations

import sys

from click.testing import CliRunner

from voss.cli import main


def test_check_dir_walks_and_aggregates(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.voss").write_text("let a = 1\n")
    (tmp_path / "nested" / "b.voss").write_text("let b = 2\n")

    result = CliRunner().invoke(main, ["check", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "0 errors, 0 warnings across 2 files" in result.output


def test_check_dir_does_not_load_hf_encoder(tmp_path):
    (tmp_path / "a.voss").write_text("let a = 1\n")

    # Run `voss check` in a CLEAN subprocess and inspect the SUBPROCESS's
    # sys.modules. Asserting on this process is order-dependent — an earlier
    # test in the full suite may have already imported sentence_transformers.
    import json
    import subprocess

    script = (
        "import json, sys\n"
        "from click.testing import CliRunner\n"
        "from voss.cli import main\n"
        f"result = CliRunner().invoke(main, ['check', {str(tmp_path)!r}])\n"
        "assert result.exit_code == 0, result.output\n"
        "print(json.dumps(sorted(k for k in sys.modules if 'sentence_transformers' in k)))\n"
    )
    cp = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr
    offenders = json.loads(cp.stdout.strip().splitlines()[-1])
    assert offenders == []


def test_check_single_file_summary_suppressed(tmp_path):
    source = tmp_path / "a.voss"
    source.write_text("let a = 1\n")

    result = CliRunner().invoke(main, ["check", str(source)])

    assert result.exit_code == 0, result.output
    assert "across" not in result.output


def test_check_dir_aggregates_errors_and_exits_nonzero(tmp_path):
    (tmp_path / "good.voss").write_text("let a = 1\n")
    (tmp_path / "bad.voss").write_text("let x = ?\n")

    result = CliRunner().invoke(main, ["check", str(tmp_path)])

    assert result.exit_code == 1
    assert "bad.voss" in result.output
    assert "1 errors, 0 warnings across 2 files" in result.output
