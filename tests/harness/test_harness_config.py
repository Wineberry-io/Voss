"""Round-trip tests for ~/.config/voss/config.toml (D-08, D-09)."""
from __future__ import annotations


import pytest

from voss.harness import config as harness_config


@pytest.fixture
def xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


class TestLoad:
    def test_missing_file_returns_empty(self, xdg):
        assert harness_config.load_harness_config() == {}
        # No file should have been created.
        assert not harness_config.config_path().exists()

    def test_round_trip_preferred_model(self, xdg):
        harness_config.set_preferred_model("claude-sonnet-4")
        cfg = harness_config.load_harness_config()
        assert cfg.get("preferred_model") == "claude-sonnet-4"

    def test_overwrite_existing_harness_section(self, xdg):
        harness_config.set_preferred_model("model-a")
        harness_config.set_preferred_model("model-b")
        assert harness_config.load_harness_config().get("preferred_model") == "model-b"

    def test_routed_persists_both_keys(self, xdg):
        harness_config.set_preferred_routed("gemma3:27b", "ollama-cloud")
        cfg = harness_config.load_harness_config()
        assert cfg.get("preferred_model") == "gemma3:27b"
        assert cfg.get("preferred_provider") == "ollama-cloud"

    def test_legacy_model_clears_routed_provider(self, xdg):
        harness_config.set_preferred_routed("gemma3:27b", "ollama-cloud")
        harness_config.set_preferred_model("claude-sonnet-4-5")
        cfg = harness_config.load_harness_config()
        assert cfg.get("preferred_model") == "claude-sonnet-4-5"
        assert "preferred_provider" not in cfg

    def test_routed_preserves_other_harness_keys(self, xdg):
        p = harness_config.config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('[harness]\npreferred_model = "old"\nsomething = "keep"\n')
        harness_config.set_preferred_routed("gemma3:27b", "ollama-cloud")
        cfg = harness_config.load_harness_config()
        assert cfg.get("something") == "keep"
        assert cfg.get("preferred_provider") == "ollama-cloud"

    def test_invalid_context_profile_values_fall_back(self, xdg):
        p = harness_config.config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "\n".join(
                [
                    "[context]",
                    "recent_full_k = -1",
                    "digest_cutoff_m = 0",
                    "high_water = 0.2",
                    "low_water = 0.8",
                    "",
                ]
            )
        )

        with pytest.warns(RuntimeWarning):
            profile = harness_config.get_packing_profile()

        assert profile.recent_full_k == 8
        assert profile.digest_cutoff_m == 20
        assert profile.high_water == 0.80
        assert profile.low_water == 0.60


class TestPreservesOtherSections:
    def test_keeps_unrelated_section_intact(self, xdg):
        p = harness_config.config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('[other]\nfoo = "bar"\n')
        harness_config.set_preferred_model("x")
        text = p.read_text()
        assert "[other]" in text
        assert 'foo = "bar"' in text
        assert harness_config.load_harness_config().get("preferred_model") == "x"


class TestFilePermissions:
    def test_chmod_600(self, xdg):
        p = harness_config.set_preferred_model("x")
        mode = p.stat().st_mode & 0o777
        assert mode == 0o600


class TestEnvOverride:
    def test_xdg_config_home_respected(self, monkeypatch, tmp_path):
        target = tmp_path / "alt-config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(target))
        p = harness_config.set_preferred_model("x")
        assert str(p).startswith(str(target))
