"""Unit tests for voss/harness/diagnostics.py and the doctor CLI.

Covers D-11 (check set + display order), D-12 (glyphs), D-13 (diagnose-only),
and D-14 (exit code semantics including WARN-only stderr nuance).
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from voss.harness import auth as auth_mod
from voss.harness import diagnostics as diag
from voss.harness.cli import doctor_cmd


# ---------------------------------------------------------------------------
# Pure-check tests
# ---------------------------------------------------------------------------


class TestCheckPythonVersion:
    def test_ok_on_current_runtime(self):
        c = diag.check_python_version()
        assert c.result is diag.CheckResult.OK
        assert c.name == "python"

    def test_fail_when_too_old(self, monkeypatch):
        class FakeVI(tuple):
            major = 3
            minor = 9
            micro = 0

        monkeypatch.setattr(diag.sys, "version_info", FakeVI((3, 9, 0, "final", 0)))
        c = diag.check_python_version()
        assert c.result is diag.CheckResult.FAIL
        assert "3.10" in c.detail
        assert c.fix


class TestCheckVossImport:
    def test_ok(self):
        c = diag.check_voss_import()
        assert c.result is diag.CheckResult.OK


class TestCheckGitOnPath:
    def test_ok_when_found(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, "which", lambda _name: "/usr/bin/git")
        c = diag.check_git_on_path()
        assert c.result is diag.CheckResult.OK
        assert c.detail == "/usr/bin/git"

    def test_fail_when_missing(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, "which", lambda _name: None)
        c = diag.check_git_on_path()
        assert c.result is diag.CheckResult.FAIL
        assert c.fix


class TestCheckCwdWritable:
    def test_ok_on_tmp(self, tmp_path: Path):
        c = diag.check_cwd_writable(tmp_path)
        assert c.result is diag.CheckResult.OK
        assert str(tmp_path) in c.detail

    def test_fail_on_readonly(self, tmp_path: Path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            c = diag.check_cwd_writable(ro)
            assert c.result is diag.CheckResult.FAIL
            assert c.fix
        finally:
            ro.chmod(0o700)


class TestCheckConfigDirsCreatable:
    def test_ok_with_xdg_override(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        c = diag.check_config_dirs_creatable()
        assert c.result is diag.CheckResult.OK

    def test_fail_when_unwritable(self, monkeypatch, tmp_path: Path):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")  # exists as a file → mkdir under it fails
        monkeypatch.setenv("XDG_CONFIG_HOME", str(blocker))
        monkeypatch.setenv("XDG_STATE_HOME", str(blocker))
        c = diag.check_config_dirs_creatable()
        assert c.result is diag.CheckResult.FAIL


class TestCheckProjectDirs:
    def test_ok(self, tmp_path: Path):
        c = diag.check_project_dirs(tmp_path)
        assert c.result is diag.CheckResult.OK

    def test_warn_not_fail_on_failure(self, tmp_path: Path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            c = diag.check_project_dirs(ro)
            assert c.result in (diag.CheckResult.OK, diag.CheckResult.WARN)
            assert c.result is not diag.CheckResult.FAIL
        finally:
            ro.chmod(0o700)


class TestCheckProviderAuth:
    def test_ok_when_anthropic_oauth_fresh(self, monkeypatch):
        fake = auth_mod.AnthropicOAuthCreds(
            access_token="a",
            refresh_token="r",
            expires_at_ms=10**15,
            subscription_type="pro",
        )
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: fake)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        c = diag.check_provider_auth()
        assert c.result is diag.CheckResult.OK
        assert "Claude" in c.detail

    def test_warn_when_anthropic_expired(self, monkeypatch):
        fake = auth_mod.AnthropicOAuthCreds(
            access_token="a", refresh_token="r", expires_at_ms=0, subscription_type="pro"
        )
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: fake)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        c = diag.check_provider_auth()
        assert c.result is diag.CheckResult.WARN

    def test_warn_when_only_codex(self, monkeypatch):
        codex = auth_mod.CodexCreds(
            api_key="sk-x",
            access_token=None,
            refresh_token=None,
            account_id=None,
            auth_mode="ApiKey",
        )
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: None)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: codex)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        c = diag.check_provider_auth()
        assert c.result is diag.CheckResult.WARN

    def test_fail_when_nothing(self, monkeypatch):
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: None)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        c = diag.check_provider_auth()
        assert c.result is diag.CheckResult.FAIL
        assert c.fix


class TestCheckCognition:
    def test_ok_when_not_initialized(self, tmp_path: Path):
        c = diag.check_cognition(tmp_path)
        assert c.result is diag.CheckResult.OK
        assert "not initialized" in c.detail


class TestCheckLegacySessions:
    def test_ok_with_count(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        legacy = tmp_path / "voss" / "sessions"
        legacy.mkdir(parents=True)
        (legacy / "a.json").write_text("{}")
        c = diag.check_legacy_sessions()
        assert c.result is diag.CheckResult.OK
        assert "1" in c.detail

    def test_ok_when_none(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        c = diag.check_legacy_sessions()
        assert c.result is diag.CheckResult.OK
        assert c.detail == "none"


class TestCheckThirdPartySkills:
    def test_ok_when_empty(self, monkeypatch, tmp_path: Path):
        from voss.harness import plugins as plugins_mod

        monkeypatch.setattr(plugins_mod, "user_plugin_dir", lambda: tmp_path / "nope")
        c = diag.check_third_party_skills(tmp_path)
        assert c.result is diag.CheckResult.OK
        assert c.detail == "none"


class TestRegistry:
    def test_ids_unique(self):
        ids = [s.id for s in diag.REGISTRY]
        assert len(ids) == len(set(ids))

    def test_results_stamped_with_id_and_category(self, tmp_path: Path):
        results = diag.run_all_checks(tmp_path)
        for c in results:
            assert c.id, f"check {c.name!r} missing id"
            assert c.category is not None, f"check {c.name!r} missing category"

    def test_registry_late_binds_check_functions(self, monkeypatch, tmp_path: Path):
        # Monkeypatching a module-level check fn must affect REGISTRY runs.
        monkeypatch.setattr(
            diag, "check_python_version",
            lambda: diag.Check("python", diag.CheckResult.FAIL, detail="patched"),
        )
        results = diag.run_all_checks(tmp_path)
        python = next(c for c in results if c.name == "python")
        assert python.detail == "patched"


class TestRunAllChecks:
    def test_returns_checks_in_display_order(self, tmp_path: Path):
        results = diag.run_all_checks(tmp_path)
        assert len(results) == 16
        names = [c.name for c in results]
        assert names == [
            "python",
            "voss import",
            "provider auth",
            "keyring",
            "codex auth",
            "git",
            "cwd writable",
            "config dirs",
            "model prefs",
            "project dirs",
            "harness cache",
            "cognition",
            "session store",
            "legacy sessions",
            "third-party skills",
            "toolchain",
        ]


class TestCheckKeyring:
    def test_warn_when_not_importable(self, monkeypatch):
        from voss.harness import auth as auth_mod

        monkeypatch.setattr(auth_mod, "_keyring_module", lambda: None)
        c = diag.check_keyring()
        assert c.result is diag.CheckResult.WARN
        assert "env vars still work" in c.detail

    def test_warn_when_no_backend(self, monkeypatch):
        from voss.harness import auth as auth_mod

        monkeypatch.setattr(auth_mod, "_keyring_module", lambda: object())
        monkeypatch.setattr(auth_mod, "_keyring_available", lambda: False)
        c = diag.check_keyring()
        assert c.result is diag.CheckResult.WARN


class TestCheckCodexAuth:
    def test_ok_when_absent(self, monkeypatch):
        from voss.harness import auth as auth_mod

        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        c = diag.check_codex_auth()
        assert c.result is diag.CheckResult.OK
        assert c.detail == "not configured"

    def test_warn_when_unusable(self, monkeypatch):
        from voss.harness import auth as auth_mod

        creds = auth_mod.CodexCreds(
            api_key=None, access_token=None, refresh_token=None,
            account_id=None, auth_mode="ChatGPT",
        )
        monkeypatch.setattr(auth_mod, "load_codex", lambda: creds)
        c = diag.check_codex_auth()
        assert c.result is diag.CheckResult.WARN
        assert c.fix == "codex login"


class TestCheckModelPrefs:
    def _write_prefs(self, tmp_path: Path, monkeypatch, pairs):
        import json as json_mod

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        from voss.harness import model_prefs

        p = model_prefs.prefs_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_mod.dumps({"recent": pairs, "favorites": []}))

    def test_ok_when_no_prefs(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        c = diag.check_model_prefs()
        assert c.result is diag.CheckResult.OK
        assert c.detail == "none recorded"

    def test_ok_without_catalog_cache(self, monkeypatch, tmp_path: Path):
        from voss.harness import model_catalog

        self._write_prefs(tmp_path, monkeypatch, [["prov", "model-x"]])
        monkeypatch.setattr(
            model_catalog, "cache_path", lambda: tmp_path / "no-cache.json"
        )
        c = diag.check_model_prefs()
        assert c.result is diag.CheckResult.OK
        assert "no catalog cache" in c.detail

    def test_warn_on_dangling_with_confirm_repair(self, monkeypatch, tmp_path: Path):
        from voss.harness import model_catalog, model_router

        self._write_prefs(tmp_path, monkeypatch, [["prov", "gone-model"]])
        monkeypatch.setattr(
            model_catalog, "_read_cache", lambda _p: ({"some": "data"}, 1.0)
        )
        monkeypatch.setattr(model_catalog, "parse_catalog", lambda _d: [])
        monkeypatch.setattr(model_router, "find_entry", lambda _g, _p, _m: None)
        c = diag.check_model_prefs()
        assert c.result is diag.CheckResult.WARN
        assert "prov/gone-model" in c.detail
        assert c.tier is diag.RepairTier.CONFIRM
        assert c.repair is not None


class TestCheckSessionStore:
    def test_ok_when_empty(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        c = diag.check_session_store(tmp_path)
        assert c.result is diag.CheckResult.OK

    def test_warn_on_corrupt_and_repair_quarantines(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        sessions = tmp_path / ".voss" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "good.json").write_text("{}")
        bad = sessions / "bad.json"
        bad.write_text("{not json")
        c = diag.check_session_store(tmp_path)
        assert c.result is diag.CheckResult.WARN
        assert "1 corrupt of 2" in c.detail
        assert c.tier is diag.RepairTier.CONFIRM
        res = c.repair()
        assert res.ok
        assert not bad.exists()
        assert (sessions / "bad.json.corrupt").exists()
        # re-check now passes
        c2 = diag.check_session_store(tmp_path)
        assert c2.result is diag.CheckResult.OK


class TestCheckToolchain:
    def test_always_ok(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, "which", lambda _n: None)
        c = diag.check_toolchain()
        assert c.result is diag.CheckResult.OK
        assert "missing: node, pnpm, cargo" in c.detail


class TestAggregateExitCode:
    def test_all_ok(self):
        rs = [diag.Check("a", diag.CheckResult.OK), diag.Check("b", diag.CheckResult.OK)]
        assert diag.aggregate_exit_code(rs) == 0

    def test_with_warn(self):
        rs = [diag.Check("a", diag.CheckResult.OK), diag.Check("b", diag.CheckResult.WARN)]
        assert diag.aggregate_exit_code(rs) == 0

    def test_with_fail(self):
        rs = [diag.Check("a", diag.CheckResult.OK), diag.Check("b", diag.CheckResult.FAIL)]
        assert diag.aggregate_exit_code(rs) == 1


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def _patch_all_ok(monkeypatch):
    monkeypatch.setattr(
        diag, "check_python_version",
        lambda: diag.Check("python", diag.CheckResult.OK, detail="3.13"),
    )
    monkeypatch.setattr(
        diag, "check_voss_import",
        lambda: diag.Check("voss import", diag.CheckResult.OK, detail="ok"),
    )
    monkeypatch.setattr(
        diag, "check_provider_auth",
        lambda: diag.Check("provider auth", diag.CheckResult.OK, detail="creds"),
    )
    monkeypatch.setattr(
        diag, "check_git_on_path",
        lambda: diag.Check("git", diag.CheckResult.OK, detail="/usr/bin/git"),
    )
    monkeypatch.setattr(
        diag, "check_cwd_writable",
        lambda _cwd: diag.Check("cwd writable", diag.CheckResult.OK, detail="ok"),
    )
    monkeypatch.setattr(
        diag, "check_config_dirs_creatable",
        lambda: diag.Check("config dirs", diag.CheckResult.OK, detail="ok"),
    )
    monkeypatch.setattr(
        diag, "check_project_dirs",
        lambda _cwd: diag.Check("project dirs", diag.CheckResult.OK, detail="ok"),
    )
    monkeypatch.setattr(
        diag, "check_harness_cache",
        lambda _cwd: diag.Check("harness cache", diag.CheckResult.OK, detail="ok"),
    )
    monkeypatch.setattr(
        diag, "check_cognition",
        lambda _cwd: diag.Check("cognition", diag.CheckResult.OK, detail="not initialized"),
    )
    monkeypatch.setattr(
        diag, "check_legacy_sessions",
        lambda: diag.Check("legacy sessions", diag.CheckResult.OK, detail="none"),
    )
    monkeypatch.setattr(
        diag, "check_third_party_skills",
        lambda _cwd: diag.Check("third-party skills", diag.CheckResult.OK, detail="none"),
    )
    monkeypatch.setattr(
        diag, "check_keyring",
        lambda: diag.Check("keyring", diag.CheckResult.OK, detail="ok"),
    )
    monkeypatch.setattr(
        diag, "check_codex_auth",
        lambda: diag.Check("codex auth", diag.CheckResult.OK, detail="not configured"),
    )
    monkeypatch.setattr(
        diag, "check_model_prefs",
        lambda: diag.Check("model prefs", diag.CheckResult.OK, detail="none recorded"),
    )
    monkeypatch.setattr(
        diag, "check_session_store",
        lambda _cwd: diag.Check("session store", diag.CheckResult.OK, detail="0"),
    )
    monkeypatch.setattr(
        diag, "check_toolchain",
        lambda: diag.Check("toolchain", diag.CheckResult.OK, detail="found: all"),
    )


class TestDoctorCmd:
    def test_exits_zero_in_healthy_env(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        result = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 0

    def test_exits_one_on_fail(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_provider_auth",
            lambda: diag.Check(
                "provider auth", diag.CheckResult.FAIL,
                detail="no creds", fix="claude /login",
            ),
        )
        result = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 1
        assert "claude /login" in result.output

    def test_only_warn_exits_zero(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_provider_auth",
            lambda: diag.Check(
                "provider auth", diag.CheckResult.WARN, detail="only codex",
            ),
        )
        result = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 0

    def test_warn_only_surfaces_stderr_summary(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_provider_auth",
            lambda: diag.Check(
                "provider auth", diag.CheckResult.WARN, detail="only codex",
            ),
        )
        runner = CliRunner()
        result = runner.invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 0
        assert "warning" in result.stderr.lower(), (
            f"WARN-only doctor must surface a stderr summary (D-14); got stderr: {result.stderr!r}"
        )
        assert "provider auth" in result.stderr.lower()

    def test_all_ok_no_stderr_summary(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        runner = CliRunner()
        result = runner.invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 0
        assert result.stderr.strip() == "", (
            f"all-OK doctor must NOT emit stderr; got: {result.stderr!r}"
        )

    def test_output_contains_glyphs(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        result = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert any(g in result.output for g in ("✓", "⚠", "✗"))

    def test_fix_text_shown_on_fail(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_git_on_path",
            lambda: diag.Check(
                "git", diag.CheckResult.FAIL,
                detail="missing", fix="brew install git",
            ),
        )
        result = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path)])
        assert result.exit_code == 1
        assert "brew install git" in result.output


# ---------------------------------------------------------------------------
# Filtering (--only / --category) and JSON output
# ---------------------------------------------------------------------------


class TestRunChecksFiltering:
    def test_filter_by_id(self, monkeypatch, tmp_path: Path):
        _patch_all_ok(monkeypatch)
        results = diag.run_checks(tmp_path, ids={"python", "git"})
        assert [c.id for c in results] == ["python", "git"]

    def test_filter_by_category(self, monkeypatch, tmp_path: Path):
        _patch_all_ok(monkeypatch)
        results = diag.run_checks(tmp_path, categories={diag.Category.AUTH})
        assert [c.id for c in results] == ["provider-auth", "keyring", "codex-auth"]

    def test_filter_intersection(self, monkeypatch, tmp_path: Path):
        _patch_all_ok(monkeypatch)
        results = diag.run_checks(
            tmp_path, ids={"python", "provider-auth"}, categories={diag.Category.ENV}
        )
        assert [c.id for c in results] == ["python"]

    def test_no_filters_runs_all(self, monkeypatch, tmp_path: Path):
        _patch_all_ok(monkeypatch)
        assert len(diag.run_checks(tmp_path)) == len(diag.REGISTRY)


class TestDoctorCmdFilters:
    def test_only_runs_named_check(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--only", "python"])
        assert r.exit_code == 0
        assert "python" in r.output
        assert "provider auth" not in r.output

    def test_unknown_only_id_is_usage_error(self, tmp_path):
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--only", "nope"])
        assert r.exit_code == 2
        assert "unknown check id" in r.output
        assert "valid ids" in r.output

    def test_category_filters(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        r = CliRunner().invoke(
            doctor_cmd, ["--cwd", str(tmp_path), "--category", "auth"]
        )
        assert r.exit_code == 0
        assert "provider auth" in r.output
        assert "git" not in r.output

    def test_cli_category_choices_match_enum(self):
        from voss.harness.cli import _DOCTOR_CATEGORIES

        assert set(_DOCTOR_CATEGORIES) == {c.value for c in diag.Category}

    def test_exit_code_aggregates_filtered_set_only(self, monkeypatch, tmp_path):
        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_git_on_path",
            lambda: diag.Check("git", diag.CheckResult.FAIL, detail="missing"),
        )
        # git excluded by filter -> failure invisible -> exit 0
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--only", "python"])
        assert r.exit_code == 0


class TestDoctorCmdJson:
    def test_json_shape(self, monkeypatch, tmp_path):
        import json

        _patch_all_ok(monkeypatch)
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--json"])
        assert r.exit_code == 0
        payload = json.loads(r.output)
        assert payload["v"] == 1
        assert payload["exit_code"] == 0
        assert len(payload["checks"]) == len(diag.REGISTRY)
        first = payload["checks"][0]
        assert set(first) == {"id", "name", "category", "status", "detail", "fix"}
        assert "repairs" not in payload

    def test_json_no_stderr_chrome_on_warn(self, monkeypatch, tmp_path):
        import json

        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_provider_auth",
            lambda: diag.Check("provider auth", diag.CheckResult.WARN, detail="meh"),
        )
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--json"])
        assert r.exit_code == 0
        json.loads(r.output)  # pure JSON on stdout
        assert r.stderr.strip() == ""

    def test_json_exit_one_on_fail(self, monkeypatch, tmp_path):
        import json

        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_git_on_path",
            lambda: diag.Check("git", diag.CheckResult.FAIL, detail="missing"),
        )
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--json"])
        assert r.exit_code == 1
        assert json.loads(r.output)["exit_code"] == 1

    def test_json_fix_requires_yes(self, tmp_path):
        r = CliRunner().invoke(doctor_cmd, ["--cwd", str(tmp_path), "--json", "--fix"])
        assert r.exit_code == 2
        assert "requires --yes" in r.output

    def test_json_fix_yes_includes_repairs(self, monkeypatch, tmp_path):
        import json

        _patch_all_ok(monkeypatch)
        monkeypatch.setattr(
            diag, "check_harness_cache",
            lambda _cwd: diag.Check(
                "harness cache", diag.CheckResult.WARN, detail="stale",
                tier=diag.RepairTier.SAFE,
                repair=lambda: diag.RepairResult(ok=True, detail="rebuilt"),
            ),
        )
        r = CliRunner().invoke(
            doctor_cmd, ["--cwd", str(tmp_path), "--json", "--fix", "--yes"]
        )
        payload = json.loads(r.output)
        assert "repairs" in payload
        [rep] = payload["repairs"]
        assert rep["executed"] is True
        assert rep["ok"] is True
