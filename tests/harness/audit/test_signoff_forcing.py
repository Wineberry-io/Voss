"""V9 RED scaffolds for sign-off risk forcing (VAUD-SIGNOFF).

Pins ``voss.harness.cli._write_signoff_ack`` (the .signoff-ack.json writer)
and the team_run_cmd acknowledgement gate. Expected RED until V9-06 lands.
Uses tmp_path; never writes to the real ``.voss/``. No xfail masking.
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from tests.harness.audit.test_o6_fixtures import build_fixture_tree


class TestAckWriter:
    def test_ack_writer_creates_sidecar(self, tmp_path: Path):
        from voss.harness.cli import _write_signoff_ack

        path = _write_signoff_ack(
            tmp_path, "rootX", killed_count=1, misroute_count=2
        )
        assert path == tmp_path / ".voss" / "sessions" / "rootX" / ".signoff-ack.json"
        data = json.loads(path.read_text())
        assert data["killed_count"] == 1
        assert data["misroute_count"] == 2
        assert "ack_ts" in data
        # 0o600 file mode (owner-only), mirroring _persist_run_final.
        assert (path.stat().st_mode & 0o777) == 0o600

    def test_ack_is_new_file_not_mutation(self, tmp_path: Path):
        from voss.harness.cli import _write_signoff_ack

        # Seed a run-final.json + a node file; the ack write must not touch them.
        build_fixture_tree(tmp_path)
        run_dir = tmp_path / ".voss" / "sessions" / "root_aabbcc0001"
        rf_before = (run_dir / "run-final.json").read_text()
        node_before = (run_dir / "node_done_0001.json").read_text()

        _write_signoff_ack(
            tmp_path, "root_aabbcc0001", killed_count=1, misroute_count=0
        )

        assert (run_dir / "run-final.json").read_text() == rf_before
        assert (run_dir / "node_done_0001.json").read_text() == node_before


def _gate_harness():
    """A throwaway click command exercising the sign-off ack gate.

    The gate lives inline in team_run_cmd, but the deterministic `team run`
    produces a CLEAN run (0 killed, 0 misroute) so the risk path can't be driven
    end-to-end. Test the extracted gate helper directly through a minimal
    command so click.prompt input can be simulated.
    """
    import click

    from voss.harness.cli import _enforce_signoff_ack

    @click.command()
    @click.option("--cwd", "cwd_str")
    @click.option("--killed", type=int)
    @click.option("--misroute", type=int)
    def cmd(cwd_str: str, killed: int, misroute: int) -> None:
        _enforce_signoff_ack(
            Path(cwd_str), "rootX", killed_count=killed, misroute_count=misroute
        )
        click.echo("approve/reject reached")

    return cmd


class TestAckGate:
    def test_approve_refused_without_ack(self, tmp_path: Path):
        # Risks present + a non-"yes" ack → abort non-zero with an
        # acknowledgement message; the approve/reject prompt is never reached.
        result = CliRunner().invoke(
            _gate_harness(),
            ["--cwd", str(tmp_path), "--killed", "1", "--misroute", "2"],
            input="no\n",
        )
        assert result.exit_code != 0
        assert "acknowledg" in result.output.lower()
        assert "approve/reject reached" not in result.output

    def test_yes_ack_writes_sidecar_and_proceeds(self, tmp_path: Path):
        result = CliRunner().invoke(
            _gate_harness(),
            ["--cwd", str(tmp_path), "--killed", "1", "--misroute", "0"],
            input="yes\n",
        )
        assert result.exit_code == 0
        assert "approve/reject reached" in result.output
        ack = tmp_path / ".voss" / "sessions" / "rootX" / ".signoff-ack.json"
        assert ack.exists()
        assert json.loads(ack.read_text())["killed_count"] == 1

    def test_clean_run_skips_gate(self, tmp_path: Path):
        # Pitfall 5: zero killed + zero misroute → no prompt, gate falls through.
        result = CliRunner().invoke(
            _gate_harness(),
            ["--cwd", str(tmp_path), "--killed", "0", "--misroute", "0"],
            input="",
        )
        assert result.exit_code == 0
        assert "approve/reject reached" in result.output
        assert "acknowledg" not in result.output.lower()


class TestAuditApproveReadback:
    def test_approve_refused_when_risks_and_no_ack(self, tmp_path: Path):
        from voss.harness.cli import audit_cmd

        # Fixture has node_killed_01 (a killed card) and NO .signoff-ack.json.
        build_fixture_tree(tmp_path)
        result = CliRunner().invoke(
            audit_cmd, ["--cwd", str(tmp_path), "--approve"]
        )
        assert result.exit_code != 0
        assert "acknowledg" in result.output.lower()

    def test_approve_permitted_with_ack(self, tmp_path: Path):
        from voss.harness.cli import _write_signoff_ack, audit_cmd

        build_fixture_tree(tmp_path)
        _write_signoff_ack(
            tmp_path, "root_aabbcc0001", killed_count=1, misroute_count=1
        )
        result = CliRunner().invoke(
            audit_cmd, ["--cwd", str(tmp_path), "--approve"]
        )
        assert result.exit_code == 0
        assert "permitted" in result.output.lower()
