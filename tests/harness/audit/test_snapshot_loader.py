"""O6-02 Task 2: Snapshot loader tests (OAUD-02).

Verifies the loader is read-only, hydrates all audit data from fixtures,
handles malformed input, and does not require live O3-O5 imports.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.harness.audit.test_o6_fixtures import build_fixture_tree
from voss.harness.audit.load import AuditLoadError, load_audit_snapshot
from voss.harness.audit.model import (
    AuditSnapshot,
    KillRecord,
    Leak6Assessment,
    RescopeRecord,
)


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    build_fixture_tree(tmp_path)
    return tmp_path


class TestLoaderBasics:
    def test_loads_fixture_tree(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert isinstance(snap, AuditSnapshot)
        assert snap.root_id != ""

    def test_snapshot_has_nodes(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.nodes) == 8  # root + 7 scenario nodes


class TestAuditDataPresent:
    def test_killed_card_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.kills) >= 1
        kill = snap.kills[0]
        assert isinstance(kill, KillRecord)
        assert kill.rationale_text == "fixture kill rationale"

    def test_rescope_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.rescopes) >= 1
        rescope = snap.rescopes[0]
        assert isinstance(rescope, RescopeRecord)
        assert rescope.predecessor_card_id == "tk_resc"
        assert rescope.successor_card_id == "tk_succ"

    def test_routing_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.routings) >= 1
        has_misroute = any(r.confidence_hint == 0.45 for r in snap.routings)
        assert has_misroute, "expected a low-confidence routing rationale"

    def test_reviewer_verdicts_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.verdicts) >= 2
        sources = {v.source for v in snap.verdicts}
        assert "A" in sources
        assert "B" in sources

    def test_reviewer_b_block_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        b_blocks = [v for v in snap.verdicts if v.source == "B" and v.verdict == "block"]
        assert len(b_blocks) >= 1

    def test_liveness_events_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.liveness) >= 1
        event_types = {e.event_type for e in snap.liveness}
        assert "timeout" in event_types
        assert "terminal" in event_types

    def test_leak6_assessment_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert isinstance(snap.leak6, Leak6Assessment)
        assert snap.leak6.status == "accepted_gap"

    def test_run_final_present(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert snap.run_final is not None
        assert snap.run_final["kind"] == "em.run_final"


class TestReadOnly:
    def test_file_mtimes_unchanged_after_load(self, fixture_root: Path):
        sessions_dir = fixture_root / ".voss" / "sessions"
        # Collect mtimes before load.
        before: dict[str, float] = {}
        for p in sorted(sessions_dir.rglob("*.json")):
            before[str(p)] = os.path.getmtime(p)

        load_audit_snapshot(fixture_root)

        # Verify mtimes unchanged.
        for path_str, mtime in before.items():
            assert os.path.getmtime(path_str) == mtime, (
                f"file modified by loader: {path_str}"
            )

    def test_file_contents_unchanged_after_load(self, fixture_root: Path):
        sessions_dir = fixture_root / ".voss" / "sessions"
        before: dict[str, str] = {}
        for p in sorted(sessions_dir.rglob("*.json")):
            before[str(p)] = p.read_text()

        load_audit_snapshot(fixture_root)

        for path_str, content in before.items():
            assert Path(path_str).read_text() == content, (
                f"file content changed by loader: {path_str}"
            )


class TestMalformedInput:
    def test_invalid_json_raises_with_path(self, tmp_path: Path):
        tree_dir = tmp_path / ".voss" / "sessions" / "badroot"
        tree_dir.mkdir(parents=True)
        bad_file = tree_dir / "bad.json"
        bad_file.write_text("{not valid json")

        with pytest.raises(AuditLoadError) as exc_info:
            load_audit_snapshot(tmp_path)
        assert "bad.json" in str(exc_info.value.path)
        assert "invalid JSON" in exc_info.value.reason

    def test_missing_id_field_raises_with_path(self, tmp_path: Path):
        tree_dir = tmp_path / ".voss" / "sessions" / "noid"
        tree_dir.mkdir(parents=True)
        (tree_dir / "noid.json").write_text(json.dumps({"root_id": "x"}))

        with pytest.raises(AuditLoadError) as exc_info:
            load_audit_snapshot(tmp_path)
        assert "missing required 'id' field" in exc_info.value.reason

    def test_missing_sessions_dir_raises(self, tmp_path: Path):
        with pytest.raises(AuditLoadError, match="sessions directory does not exist"):
            load_audit_snapshot(tmp_path)

    def test_empty_tree_dir_raises(self, tmp_path: Path):
        tree_dir = tmp_path / ".voss" / "sessions" / "empty"
        tree_dir.mkdir(parents=True)
        with pytest.raises(AuditLoadError, match="no node files found"):
            load_audit_snapshot(tmp_path)


class TestDeterminism:
    def test_nodes_sorted_by_id(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        ids = [n.id for n in snap.nodes]
        assert ids == sorted(ids)

    def test_two_loads_produce_identical_snapshots(self, fixture_root: Path):
        snap1 = load_audit_snapshot(fixture_root)
        snap2 = load_audit_snapshot(fixture_root)
        assert snap1.root_id == snap2.root_id
        assert len(snap1.nodes) == len(snap2.nodes)
        assert len(snap1.cards) == len(snap2.cards)
        assert len(snap1.kills) == len(snap2.kills)
        for n1, n2 in zip(snap1.nodes, snap2.nodes):
            assert n1.id == n2.id


class TestNoLiveImports:
    def test_model_module_has_no_board_imports(self):
        import voss.harness.audit.model as m
        src = Path(m.__file__).read_text()
        for forbidden in (
            "from voss.harness.board",
            "import voss.harness.board",
            "from voss.harness.em",
            "import voss.harness.em",
            "from voss.harness.cli",
            "import voss.harness.cli",
        ):
            assert forbidden not in src, f"model.py has forbidden import: {forbidden}"

    def test_load_module_has_no_board_imports(self):
        import voss.harness.audit.load as ld
        src = Path(ld.__file__).read_text()
        for forbidden in (
            "from voss.harness.board",
            "import voss.harness.board",
            "from voss.harness.em",
            "import voss.harness.em",
            "from voss.harness.cli",
            "import voss.harness.cli",
        ):
            assert forbidden not in src, f"load.py has forbidden import: {forbidden}"

    def test_calibration_module_has_no_board_imports(self):
        # RED until V9-05: voss.harness.audit.calibration does not exist yet.
        import voss.harness.audit.calibration as cal  # noqa: F401

        src = Path(cal.__file__).read_text()
        for forbidden in (
            "from voss.harness.board",
            "import voss.harness.board",
            "from voss.harness.em",
            "import voss.harness.em",
            "from voss.harness.cli",
            "import voss.harness.cli",
        ):
            assert forbidden not in src, f"calibration.py has forbidden import: {forbidden}"


# ---------------------------------------------------------------------------
# V9 RED extensions (expected to fail until V9-02 lands)
# ---------------------------------------------------------------------------


class TestLandmineGlobFilter:
    """The node glob must skip run-final.json + *.review.json (V9 landmine)."""

    def test_load_does_not_raise_on_sidecars(self, fixture_root: Path):
        # Fixture now writes run-final.json + *.review.json into the run dir.
        # Loading must not raise AuditLoadError on those non-node files.
        snap = load_audit_snapshot(fixture_root)
        assert isinstance(snap, AuditSnapshot)

    def test_sidecars_excluded_from_node_count(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert len(snap.nodes) == 8  # 8 node files; sidecars/run-final excluded

    def test_run_final_populated(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root)
        assert snap.run_final is not None


class TestRunIdParameter:
    """load_audit_snapshot gains a run_id param + latest-by-mtime fallback."""

    def test_named_run_loads(self, fixture_root: Path):
        snap = load_audit_snapshot(fixture_root, run_id="root_aabbcc0001")
        assert snap.root_id == "root_aabbcc0001"

    def test_unknown_run_raises(self, fixture_root: Path):
        with pytest.raises(AuditLoadError):
            load_audit_snapshot(fixture_root, run_id="does_not_exist")

    def test_none_selects_latest_by_mtime(self, tmp_path: Path):
        # First run dir (older).
        build_fixture_tree(tmp_path)
        sessions = tmp_path / ".voss" / "sessions"
        # Second run dir (newer mtime, alphabetically LATER so it differs from
        # the current sorted()[0] behavior — makes the RED assertion meaningful).
        newer = sessions / "root_zzeeff0002"
        newer.mkdir(parents=True)
        node = newer / "root_zzeeff0002.json"
        node.write_text(json.dumps({"id": "root_zzeeff0002", "root_id": "root_zzeeff0002"}))
        # Force newer mtime explicitly (avoid same-second resolution).
        old_mtime = (sessions / "root_aabbcc0001").stat().st_mtime
        os.utime(newer, (old_mtime + 100, old_mtime + 100))
        snap = load_audit_snapshot(tmp_path, run_id=None)
        assert snap.root_id == "root_zzeeff0002"


class TestSidecarLoad:
    """_load_review_sidecars returns {node_id: sidecar_dict}, graceful on errors."""

    def test_sidecars_keyed_by_node_id(self, fixture_root: Path):
        from voss.harness.audit.load import _load_review_sidecars

        run_dir = fixture_root / ".voss" / "sessions" / "root_aabbcc0001"
        sidecars = _load_review_sidecars(run_dir)
        assert "node_ab_block1" in sidecars
        assert sidecars["node_ab_block1"]["b_verdict"]["verdict"] == "block"

    def test_corrupt_sidecar_maps_to_empty(self, fixture_root: Path):
        from voss.harness.audit.load import _load_review_sidecars

        run_dir = fixture_root / ".voss" / "sessions" / "root_aabbcc0001"
        bad = run_dir / "node_bad.review.json"
        bad.write_text("{not valid json")
        sidecars = _load_review_sidecars(run_dir)
        assert sidecars["node_bad"] == {}


class TestRunFinalSeparateRead:
    """_load_run_final_file reads the separate run-final.json file."""

    def test_reads_run_final(self, fixture_root: Path):
        from voss.harness.audit.load import _load_run_final_file

        run_dir = fixture_root / ".voss" / "sessions" / "root_aabbcc0001"
        rf = _load_run_final_file(run_dir)
        assert rf is not None
        assert rf["idea"] == "fixture idea"
        assert "sign_off" in rf

    def test_absent_run_final_returns_none(self, tmp_path: Path):
        from voss.harness.audit.load import _load_run_final_file

        empty = tmp_path / "run_dir"
        empty.mkdir()
        assert _load_run_final_file(empty) is None
