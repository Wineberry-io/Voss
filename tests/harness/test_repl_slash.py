"""Tests for REPL slash command helpers extracted from _run_repl.

Strategy: test the slash helpers directly with monkeypatched auth + config,
rather than driving the full REPL loop (covered by Plan 07 e2e).
"""
from __future__ import annotations

import pytest

from voss.harness import auth as auth_mod
from voss.harness import config as harness_config
from voss.harness.auth import AnthropicOAuthCreds
from voss.harness.cli import _handle_login, _print_slash_help


@pytest.fixture
def isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


class TestLoginHandler:
    def test_no_creds_prints_upstream_command(self, monkeypatch, capsys):
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: None)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        _handle_login("anthropic")
        captured = capsys.readouterr()
        assert "claude /login" in captured.out

    def test_existing_fresh_creds_no_refresh(self, monkeypatch, capsys):
        creds = AnthropicOAuthCreds(
            access_token="t",
            refresh_token="r",
            expires_at_ms=10**15,  # far future
            subscription_type="max",
        )
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: creds)
        refresh_called: list = []
        monkeypatch.setattr(
            auth_mod, "refresh_anthropic",
            lambda c, **kw: refresh_called.append(c) or c,
        )
        _handle_login("anthropic")
        captured = capsys.readouterr()
        assert "OK" in captured.out
        assert not refresh_called

    def test_expired_creds_triggers_refresh(self, monkeypatch, capsys):
        creds = AnthropicOAuthCreds(
            access_token="t",
            refresh_token="r",
            expires_at_ms=0,  # expired
            subscription_type="max",
        )
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: creds)
        refresh_called: list = []
        monkeypatch.setattr(
            auth_mod, "refresh_anthropic",
            lambda c, **kw: refresh_called.append(c) or c,
        )
        _handle_login("anthropic")
        captured = capsys.readouterr()
        assert "refreshed" in captured.out.lower()
        assert refresh_called

    def test_no_provider_arg_lists_both(self, monkeypatch, capsys):
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: None)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        _handle_login(None)
        captured = capsys.readouterr()
        assert "Claude" in captured.out
        assert "Codex" in captured.out

    def test_unknown_provider_warns(self, monkeypatch, capsys):
        monkeypatch.setattr(auth_mod, "load_anthropic_oauth", lambda: None)
        monkeypatch.setattr(auth_mod, "load_codex", lambda: None)
        _handle_login("xenon")
        captured = capsys.readouterr()
        assert "unknown provider" in captured.err


class TestSlashHelp:
    def test_help_lists_new_commands(self, capsys):
        _print_slash_help()
        captured = capsys.readouterr()
        for token in ("/login", "/model", "/mode", "--confirm"):
            assert token in captured.out, f"missing slash token: {token}"

    def test_grouped_help_renders_headers_and_all_slashes(self, capsys):
        """T6-02: grouped renderer produces the four named headers and does not drop slashes."""
        _print_slash_help()
        captured = capsys.readouterr()
        for header in ("Editing", "Session", "Insight", "Control"):
            assert header in captured.out, f"missing group header: {header}"
        for token in ("/diff", "/resume", "/why"):
            assert token in captured.out, f"missing slash token: {token}"


class TestModeEscalationParsing:
    """Parse-level checks for /mode auto vs /mode auto --confirm."""

    def test_mode_auto_without_confirm_detected(self):
        parts = "/mode auto".split()
        assert parts[1] == "auto"
        assert "--confirm" not in parts

    def test_mode_auto_with_confirm_detected(self):
        parts = "/mode auto --confirm".split()
        assert parts[1] == "auto"
        assert "--confirm" in parts


class TestModelPersistence:
    def test_set_preferred_model_round_trip(self, isolate_config):
        harness_config.set_preferred_model("claude-sonnet-4-20250514")
        cfg = harness_config.load_harness_config()
        assert cfg.get("preferred_model") == "claude-sonnet-4-20250514"


def test_memory_commands_registered() -> None:
    from voss.harness.cli import _build_slash_registry

    registry = _build_slash_registry()
    for name in ("/recall", "/forget", "/memory", "/save", "/save-session"):
        assert registry.lookup(name) is not None, f"slash {name} not registered"


def test_t6_prd_slash_commands_registered() -> None:
    """T6 — PRD §2.4 slash debt. All SLASH-01..07 must register."""
    from voss.harness.cli import _build_slash_registry

    registry = _build_slash_registry()
    for name in ("/diff", "/apply", "/discard", "/budget", "/resume", "/why", "/cost"):
        assert registry.lookup(name) is not None, f"slash {name} not registered"


def test_m11_probable_budget_trace_slash_commands_registered() -> None:
    from voss.harness.cli import _build_slash_registry

    registry = _build_slash_registry()
    for name in ("/probable", "/btrace", "/budget"):
        assert registry.lookup(name) is not None, f"slash {name} not registered"


def test_m11_voss_diff_slash_command_registered() -> None:
    from voss.harness.cli import _build_slash_registry

    registry = _build_slash_registry()
    assert registry.lookup("/vdiff") is not None, "slash /vdiff not registered"


def test_doctor_slash_command_registered() -> None:
    from voss.harness.cli import _build_slash_registry

    registry = _build_slash_registry()
    assert registry.lookup("/doctor") is not None, "slash /doctor not registered"


def test_doctor_slash_command_executes(monkeypatch, tmp_path, capsys) -> None:
    from types import SimpleNamespace

    from voss.harness import diagnostics as diag
    from voss.harness.cli import _build_slash_registry

    monkeypatch.setattr(
        diag, "run_all_checks",
        lambda _cwd: [
            diag.Check("python", diag.CheckResult.OK, detail="3.13", id="python"),
            diag.Check(
                "harness cache", diag.CheckResult.WARN, detail="stale",
                fix="voss compile voss/harness/agent/", id="harness-cache",
                tier=diag.RepairTier.SAFE,
                repair=lambda: diag.RepairResult(ok=True),
            ),
        ],
    )
    ctx = SimpleNamespace(cwd=tmp_path)
    reg = _build_slash_registry()
    assert reg.dispatch(ctx, "/doctor")
    out = capsys.readouterr().out
    assert "python" in out
    assert "✓" in out and "⚠" in out
    assert "voss compile voss/harness/agent/" in out
    # repairable finding present -> pointer to the CLI repair path
    assert "voss doctor --fix" in out


def test_m10_code_slash_commands_execute(tmp_path, capsys) -> None:
    from types import SimpleNamespace
    from voss.harness.cli import _build_slash_registry

    # _render_project_index_text only renders inside a project root
    # (f2cc75d gate) — tmp_path needs a marker file.
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 't'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "def shared_entry(x):\n"
        "    return x\n\n"
        "def caller():\n"
        "    return shared_entry(1)\n",
        encoding="utf-8",
    )
    ctx = SimpleNamespace(
        cwd=tmp_path,
        record=SimpleNamespace(id="sess-test"),
        renderer=None,
        project_index_text="",
    )

    reg = _build_slash_registry()
    assert reg.dispatch(ctx, "/symbol shared_entry")
    out = capsys.readouterr().out
    assert "shared_entry app.py:1" in out

    assert reg.dispatch(ctx, "/refs shared_entry")
    out = capsys.readouterr().out
    assert "app.py:1" in out
    assert "app.py:5" in out

    assert reg.dispatch(ctx, "/refresh")
    out = capsys.readouterr().out
    assert "refreshed code index" in out
    assert "## Project Index" in ctx.project_index_text


class TestT6Behaviors:
    """T6 — Verify /why /budget /cost --by-model and /discard dry-run paths
    against a fake ReplContext. Heavier integrations (live /resume, /diff
    against a real repo) covered by Plan 07 e2e."""

    @pytest.fixture
    def fake_ctx(self, tmp_path):
        from types import SimpleNamespace

        # Stub Plan-like for /why.
        plan = SimpleNamespace(
            rationale="picked the read-only path first",
            confidence=0.82,
            steps=[
                SimpleNamespace(name="fs_grep", why="locate symbol"),
                SimpleNamespace(name="fs_read", why="confirm context"),
            ],
            open_question=None,
            final_when_done="symbol mapped",
        )
        record = SimpleNamespace(
            id="abc123",
            name="fake-session",
            cwd=str(tmp_path),
            model="claude-sonnet-4-7",
            total_cost_usd=0.0,
            turns=[],
            # runs[-1] is the most recent; /discard reverts its changed list.
            runs=[
                {"cost_usd": 0.008, "changed": []},
                {"cost_usd": 0.012, "changed": ["voss/harness/cli.py"]},
            ],
        )
        return SimpleNamespace(
            cwd=tmp_path,
            record=record,
            history=None,
            last_plan=plan,
            total_cost=0.020,
            budget_usd=None,
            prior_context=None,
        )

    def test_why_renders_rationale_and_steps(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/why").handler(fake_ctx, [], "/why")
        out = capsys.readouterr().out
        assert "picked the read-only path first" in out
        assert "0.82" in out
        assert "fs_grep" in out and "fs_read" in out

    def test_why_no_plan_errors_cleanly(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        fake_ctx.last_plan = None
        reg = _build_slash_registry()
        reg.lookup("/why").handler(fake_ctx, [], "/why")
        err = capsys.readouterr().err
        assert "no plan yet" in err

    def test_budget_set_and_show(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/budget").handler(fake_ctx, ["5.00"], "/budget 5.00")
        assert fake_ctx.budget_usd == 5.00
        reg.lookup("/budget").handler(fake_ctx, [], "/budget")
        out = capsys.readouterr().out
        assert "$5.00" in out and "0.0200" in out

    def test_budget_zero_clears(self, fake_ctx):
        from voss.harness.cli import _build_slash_registry

        fake_ctx.budget_usd = 5.0
        reg = _build_slash_registry()
        reg.lookup("/budget").handler(fake_ctx, ["0"], "/budget 0")
        assert fake_ctx.budget_usd is None

    def test_budget_rejects_bad_input(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/budget").handler(fake_ctx, ["abc"], "/budget abc")
        err = capsys.readouterr().err
        assert "usage" in err.lower()

    def test_cost_by_model_groups_by_session_model(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/cost").handler(fake_ctx, ["--by-model"], "/cost --by-model")
        out = capsys.readouterr().out
        assert "claude-sonnet-4-7" in out
        assert "$0.0200" in out  # 0.012 + 0.008

    def test_cost_by_tool_is_honest_stub(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/cost").handler(fake_ctx, ["--by-tool"], "/cost --by-tool")
        out = capsys.readouterr().out
        assert "T6" in out  # T6 SLASH-07: per-tool cost tracking destination (post-T4 update)

    def test_discard_dry_run_lists_files(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/discard").handler(fake_ctx, [], "/discard")
        out = capsys.readouterr().out
        assert "voss/harness/cli.py" in out
        assert "--confirm" in out

    def test_discard_no_runs_is_no_op(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        fake_ctx.record.runs = []
        reg = _build_slash_registry()
        reg.lookup("/discard").handler(fake_ctx, [], "/discard")
        out = capsys.readouterr().out
        assert "no runs" in out

    def test_apply_explains_v01_semantics(self, fake_ctx, capsys):
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/apply").handler(fake_ctx, [], "/apply")
        out = capsys.readouterr().out
        assert "immediately" in out.lower()

    def test_diff_happy_path(self, fake_ctx, capsys, monkeypatch):
        """SLASH-01: /diff happy-path via subprocess monkeypatch (git diff against working tree)."""
        from voss.harness.cli import _build_slash_registry
        from types import SimpleNamespace

        fake_diff = "diff --git a/foo b/foo\nindex 123..456 100644\n--- a/foo\n+++ b/foo\n@@ -1 +1 @@\n-old\n+new"

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0, stdout=fake_diff, stderr="")

        monkeypatch.setattr("voss.harness.cli.subprocess.run", fake_run)

        reg = _build_slash_registry()
        reg.lookup("/diff").handler(fake_ctx, [], "/diff")
        out = capsys.readouterr().out
        assert "diff --git a/foo" in out
        assert "+new" in out

    def test_why_d07_audit_sc2(self, fake_ctx, capsys):
        """SLASH-06 / D-07 audit: current _why already satisfies PRD Ticket 7 (SC#2).

        D-07 RESOLUTION: PRD Ticket 7 (.vscode/voss_v_0_1_scope_lock.md:1213-1221) is
        satisfied by the existing single `confidence:.2f` float + rationale + per-step why.
        `ProbableValue` (:712) is a runtime-layer type, NOT a /why output-format mandate.
        Therefore T6 makes NO /why code change — test + documented rationale only.
        """
        from voss.harness.cli import _build_slash_registry

        reg = _build_slash_registry()
        reg.lookup("/why").handler(fake_ctx, [], "/why")
        out = capsys.readouterr().out

        # SC#2 assertions — rendered from ctx.last_plan only (no provider call by construction)
        assert "picked the read-only path first" in out
        assert "0.82" in out
        assert "fs_grep" in out and "fs_read" in out
        assert "symbol mapped" in out

    def test_resume_id_prefix_arm(self, fake_ctx, capsys, monkeypatch):
        """SLASH-05: /resume <id-prefix> routes through session_store.load and swaps ctx."""
        from voss.harness.cli import _build_slash_registry
        from types import SimpleNamespace

        def fake_load(target, cwd=None):
            # The test documents that we pass whatever the user typed as `target`
            # and the real session.py:222 OR predicate decides (no ordering imposed here).
            assert target == "abc12" or target.startswith("abc12")
            record = SimpleNamespace(
                id="abc123", name="fake-session", cwd=str(fake_ctx.cwd),
                total_cost_usd=0.123, turns=[1, 2], runs=[]
            )
            return record, ["history"]

        monkeypatch.setattr("voss.harness.cli.session_store.load", fake_load)

        reg = _build_slash_registry()
        reg.lookup("/resume").handler(fake_ctx, ["abc12"], "/resume abc12")
        out = capsys.readouterr().out
        assert "resumed: fake-session" in out
        assert fake_ctx.record.id == "abc123"

    def test_resume_exact_name_arm(self, fake_ctx, capsys, monkeypatch):
        """SLASH-05: /resume <exact-name> also routes through the single load(target) call."""
        from voss.harness.cli import _build_slash_registry
        from types import SimpleNamespace

        def fake_load(target, cwd=None):
            # Same load(target) — real resolution (session.py:222) is a single OR
            # with no id-first / name-second ordering. We only test that the handler
            # accepts either shape and lets the loader decide.
            assert target == "fake-session"
            record = SimpleNamespace(
                id="abc123", name="fake-session", cwd=str(fake_ctx.cwd),
                total_cost_usd=0.050, turns=[], runs=[]
            )
            return record, None

        monkeypatch.setattr("voss.harness.cli.session_store.load", fake_load)

        reg = _build_slash_registry()
        reg.lookup("/resume").handler(fake_ctx, ["fake-session"], "/resume fake-session")
        out = capsys.readouterr().out
        assert "resumed: fake-session" in out

    def test_resume_cross_cwd_warns_and_stays(self, fake_ctx, capsys, monkeypatch):
        """SLASH-05 / D-03: cross-cwd resume prints warning to err and does NOT change cwd."""
        from voss.harness.cli import _build_slash_registry
        from types import SimpleNamespace

        other_cwd = "/tmp/other-project"

        def fake_load(target, cwd=None):
            record = SimpleNamespace(
                id="xyz999", name="other-session", cwd=other_cwd,
                total_cost_usd=0.0, turns=[], runs=[]
            )
            return record, None

        monkeypatch.setattr("voss.harness.cli.session_store.load", fake_load)

        original_cwd = fake_ctx.cwd
        reg = _build_slash_registry()
        reg.lookup("/resume").handler(fake_ctx, ["xyz"], "/resume xyz")
        err = capsys.readouterr().err
        assert "warning: session cwd is" in err
        assert "staying in" in err
        # D-03: we stay in the current cwd (no rebind)
        assert fake_ctx.cwd == original_cwd
