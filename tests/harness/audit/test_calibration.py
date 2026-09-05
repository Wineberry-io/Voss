"""V9 RED scaffolds for reviewer calibration (VAUD-CAL).

Pins ``voss.harness.audit.calibration.compute_calibration`` and the
``CalibrationReport`` model. Expected RED until V9-05 lands. Uses tmp_path;
never writes to the real ``.voss/``. No xfail masking.

Calibration pairs from the fixture sidecars:
  - node_misroute1: A=pass / B=fail  -> false-pass pair
  - node_ab_block1: A=pass / B=block -> false-pass + slop-rejection
  - node_done_0001: A=pass / B=pass  -> clean
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.harness.audit.test_o6_fixtures import build_fixture_tree


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    build_fixture_tree(tmp_path)
    return tmp_path / ".voss" / "sessions"


class TestCalibration:
    def test_false_pass_rate(self, sessions_dir: Path):
        from voss.harness.audit.calibration import compute_calibration

        report = compute_calibration(sessions_dir)
        assert report.false_pass_count >= 1
        assert 0.0 <= report.false_pass_rate <= 1.0

    def test_slop_rejection_rate(self, sessions_dir: Path):
        from voss.harness.audit.calibration import compute_calibration

        report = compute_calibration(sessions_dir)
        # node_ab_block1 B=block contributes to slop rejection.
        assert report.slop_rejection_count >= 1
        assert 0.0 <= report.slop_rejection_rate <= 1.0

    def test_spot_audit_hook_deterministic(self, sessions_dir: Path):
        from voss.harness.audit.calibration import compute_calibration

        r1 = compute_calibration(sessions_dir, spot_k=2, seed=7)
        r2 = compute_calibration(sessions_dir, spot_k=2, seed=7)
        assert r1.spot_audit_paths == r2.spot_audit_paths

    def test_zero_pairs_no_div_by_zero(self, tmp_path: Path):
        from voss.harness.audit.calibration import compute_calibration

        empty = tmp_path / "sessions"
        empty.mkdir()
        report = compute_calibration(empty)
        assert report.false_pass_rate == 0.0
        assert report.slop_rejection_rate == 0.0
        assert report.total_pairs == 0


class TestCalibrationModel:
    def test_calibration_report_fields(self):
        from voss.harness.audit.model import CalibrationReport

        report = CalibrationReport(
            total_pairs=0,
            false_pass_count=0,
            slop_rejection_count=0,
            false_pass_rate=0.0,
            slop_rejection_rate=0.0,
            spot_audit_paths=(),
        )
        assert report.total_pairs == 0
        assert report.spot_audit_paths == ()
