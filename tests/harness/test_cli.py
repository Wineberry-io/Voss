from pathlib import Path

from click.testing import CliRunner

from voss.harness.cli import main


class TestUnifiedVossCli:
    """Agent verbs must appear under the unified `voss` CLI."""

    def test_voss_help_lists_agent_verbs(self) -> None:
        from voss.cli import main as voss_main

        r = CliRunner().invoke(voss_main, ["--help"])
        assert r.exit_code == 0
        for verb in ("do", "chat", "doctor"):
            assert verb in r.output, f"missing agent verb: {verb}"
        for verb in ("compile", "run", "check", "init", "ast"):
            assert verb in r.output, f"missing compiler verb: {verb}"

    def test_voss_doctor_works(self, monkeypatch) -> None:
        # Force all checks OK so exit code is deterministic in CI without creds.
        from voss.harness import diagnostics as diag

        monkeypatch.setattr(
            diag, "run_all_checks",
            lambda _cwd: [
                diag.Check("python", diag.CheckResult.OK),
                diag.Check("voss import", diag.CheckResult.OK),
                diag.Check("provider auth", diag.CheckResult.OK),
                diag.Check("git", diag.CheckResult.OK),
                diag.Check("cwd writable", diag.CheckResult.OK),
                diag.Check("config dirs", diag.CheckResult.OK),
                diag.Check("project dirs", diag.CheckResult.OK),
            ],
        )

        from voss.cli import main as voss_main

        r = CliRunner().invoke(voss_main, ["doctor"])
        assert r.exit_code == 0
        assert "voss import" in r.output


class TestCli:
    def test_help(self) -> None:
        r = CliRunner().invoke(main, ["--help"])
        assert r.exit_code == 0
        assert "voss" in r.output
        assert "do" in r.output
        assert "chat" in r.output

    def test_doctor(self, monkeypatch) -> None:
        from voss.harness import diagnostics as diag

        monkeypatch.setattr(
            diag, "run_all_checks",
            lambda _cwd: [
                diag.Check("python", diag.CheckResult.OK),
                diag.Check("voss import", diag.CheckResult.OK),
                diag.Check("provider auth", diag.CheckResult.OK),
                diag.Check("git", diag.CheckResult.OK),
                diag.Check("cwd writable", diag.CheckResult.OK),
                diag.Check("config dirs", diag.CheckResult.OK),
                diag.Check("project dirs", diag.CheckResult.OK),
            ],
        )
        r = CliRunner().invoke(main, ["doctor"])
        assert r.exit_code == 0
        assert "voss import" in r.output
        assert "✓" in r.output

    def test_do_with_auth_none_exits_2(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = CliRunner().invoke(main, ["do", "--auth", "none", "anything"])
        assert r.exit_code == 2
        assert "no usable credentials" in r.output

    def test_do_with_auth_api_no_env_exits_2(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = CliRunner().invoke(main, ["do", "--auth", "api", "anything"])
        assert r.exit_code == 2


class TestAnalyzeRouting:
    """/analyze slash + natural-language route both invoke _handle_analyze."""

    def _patch_analyze_skill(self, monkeypatch) -> list[dict]:
        calls: list[dict] = []

        def fake_run(*, cwd, provider, history, record, renderer, tools, gate):
            calls.append({"cwd": cwd, "record_id": record.id})

        import voss.harness.skills.analyze as analyze_mod

        monkeypatch.setattr(analyze_mod, "run", fake_run)
        return calls

    def _drive_repl(self, monkeypatch, tmp_path: Path, input_text: str):
        from voss_runtime import EpisodicMemory

        from voss.harness import session as session_store
        from voss.harness.cli import _run_repl
        from voss.harness.providers import AnthropicOAuthProvider  # noqa: F401

        # Build a no-op provider — analyze.run is stubbed so it's unused.
        class _NoopProvider:
            async def complete(self, **_):
                raise AssertionError("provider.complete should not be called")

            def count_tokens(self, **_):
                return 1

        record = session_store.SessionRecord.new(
            cwd=tmp_path, model="claude-test"
        )
        # Feed lines via monkeypatched input() so the REPL exits after one cmd.
        lines = iter(input_text.splitlines())
        monkeypatch.setattr("builtins.input", lambda *_: next(lines))

        _run_repl(
            cwd=tmp_path,
            json_mode=False,
            mode="plan",
            history=EpisodicMemory(capacity=10),
            record=record,
            provider=_NoopProvider(),
            auth_detail="stub",
        )

    def test_slash_analyze_routes(self, monkeypatch, tmp_path: Path) -> None:
        calls = self._patch_analyze_skill(monkeypatch)
        self._drive_repl(monkeypatch, tmp_path, "/analyze\n/exit\n")
        assert len(calls) == 1
        assert calls[0]["cwd"] == tmp_path

    def test_natural_analyze_routes(self, monkeypatch, tmp_path: Path) -> None:
        calls = self._patch_analyze_skill(monkeypatch)
        self._drive_repl(monkeypatch, tmp_path, "analyze this repo\n/exit\n")
        assert len(calls) == 1


class TestSessionsListing:
    """`voss sessions` is cwd-scoped; --all merges legacy XDG sessions."""

    def _write_session(self, dir_path: Path, sid: str, name: str) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": sid,
            "name": name,
            "cwd": str(dir_path.parent.parent),
            "model": "claude-test",
            "started_at": "2026-05-10T00:00:00+00:00",
            "updated_at": "2026-05-10T00:00:00+00:00",
            "total_cost_usd": 0.0,
            "turns": [],
            "runs": [],
        }
        (dir_path / f"{sid}.json").write_text(__import__("json").dumps(payload))

    def test_sessions_cwd_scoped(self, monkeypatch, tmp_path: Path) -> None:
        legacy_state = tmp_path / "xdg-state"
        monkeypatch.setenv("XDG_STATE_HOME", str(legacy_state))
        self._write_session(tmp_path / ".voss" / "sessions", "abc12345aaaa", "cwd1")
        self._write_session(tmp_path / ".voss" / "sessions", "def67890aaaa", "cwd2")
        self._write_session(legacy_state / "voss" / "sessions", "999aaaaaaaaa", "legacy1")

        monkeypatch.chdir(tmp_path)
        r = CliRunner().invoke(main, ["sessions"])
        assert r.exit_code == 0
        assert "abc12345" in r.output
        assert "def67890" in r.output
        assert "999aaaaa" not in r.output
        assert "[legacy]" not in r.output

    def test_sessions_all_includes_legacy(self, monkeypatch, tmp_path: Path) -> None:
        legacy_state = tmp_path / "xdg-state"
        monkeypatch.setenv("XDG_STATE_HOME", str(legacy_state))
        self._write_session(tmp_path / ".voss" / "sessions", "abc12345aaaa", "cwd1")
        self._write_session(legacy_state / "voss" / "sessions", "999aaaaaaaaa", "legacy1")

        monkeypatch.chdir(tmp_path)
        r = CliRunner().invoke(main, ["sessions", "--all"])
        assert r.exit_code == 0
        assert "abc12345" in r.output
        assert "999aaaaa" in r.output
        assert "[legacy]" in r.output


class TestDoctorCognitionRows:
    def test_doctor_renders_folded_registry_rows(self, monkeypatch, tmp_path: Path) -> None:
        """Cognition/legacy-session/skill rows come from the check registry
        (folded from the old ad-hoc block) and render as glyph table rows."""
        from voss.harness import diagnostics as diag

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        monkeypatch.setattr(
            diag, "check_provider_auth",
            lambda: diag.Check("provider auth", diag.CheckResult.OK, detail="creds"),
        )
        r = CliRunner().invoke(main, ["doctor", "--cwd", str(tmp_path)])
        assert r.exit_code == 0
        assert "cognition" in r.output
        assert "legacy sessions" in r.output
        assert "third-party skills" in r.output
        # Old ad-hoc rendering path is gone.
        assert ".voss/ initialized" not in r.output
        assert "cognition staleness" not in r.output


class TestProjectPolicyLayering:
    def test_project_policy_deny_wins(self) -> None:
        from voss.harness.cognition_schemas import PermissionsConfig, ToolPolicy
        from voss.harness.permissions import PermissionGate

        gate = PermissionGate(
            mode="auto",
            project_policy=PermissionsConfig(
                tool_policy=ToolPolicy(deny=["shell_run"])
            ),
        )
        allowed, reason = gate.check("shell_run", {"cmd": "ls"})
        assert allowed is False
        assert "denied by .voss/permissions.yml" in reason

    def test_project_policy_allow_does_not_expand(self) -> None:
        """Project allow MUST NOT auto-approve a tool that mode would prompt for."""
        from voss.harness.cognition_schemas import PermissionsConfig, ToolPolicy
        from voss.harness.permissions import PermissionGate

        gate = PermissionGate(
            mode="plan",
            project_policy=PermissionsConfig(
                tool_policy=ToolPolicy(allow=["shell_run"])
            ),
        )
        # shell_run is mutating; mode=plan structurally denies all mutating tools
        # regardless of project allow.
        allowed, reason = gate.check("shell_run", {"cmd": "ls"}, is_mutating=True)
        assert allowed is False
        assert reason == "denied by mode plan"

    def test_no_project_policy_unchanged(self) -> None:
        """M1-style behavior preserved when project_policy is None."""
        from voss.harness.permissions import PermissionGate

        gate = PermissionGate(mode="auto", project_policy=None, auto_yes=True)
        allowed, _ = gate.check("shell_run", {"cmd": "ls"})
        assert allowed is True
