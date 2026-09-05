"""Agent commands for the unified `voss` CLI.

Defines `do_cmd`, `chat_cmd`, `doctor_cmd` as standalone click Commands.
- `voss.cli` imports them and adds them to the compiler's `main` group.
- `python -m voss.harness` builds a small standalone group for testing.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace

import click
import psutil

from voss_runtime import EpisodicMemory, configure, get_config
from voss_runtime.providers.base import ModelProvider, ProviderResponse

from . import auth as auth_mod
from . import cognition as cognition_mod
from . import conventions
from . import session as session_store
from . import voss_md
from .memory_cli import memory_group
from .memory_store import MemoryStore, make_global_store
from .agent import Plan
from .claims import claims_group
from .net import NetSession
from .permissions import PermissionGate, PermissionStore
from .plugins import load_plugins, set_plugin_enabled
from .claude_agent_provider import ClaudeAgentProvider
from .providers import OpenAIOAuthProvider
from .render import make_renderer
from .sandbox import SandboxError, jail_path
from .multiagent import DEFAULT_PARENT_RESERVE, attach_multiagent_tools
from .session_tree import SessionTreeManager, SessionTreeNode, finalize_node
from .skill_registry import SkillRegistry, default_skill_registry
from .slash import SlashCommand, SlashRegistry
from .subagents import (
    SubagentRegistry,
    attach_subagent_tool,
    default_subagent_registry,
    run_subagent,
)
from .tools import CAPABILITY_GROUPS, attach_memory_tools, make_toolset
from .voss_inspect import (
    load_run,
    render_budget_timeline,
    render_decision_sequence,
)


def _bootstrap_runtime_config() -> None:
    """Wire on-disk [agent] config into the RuntimeConfig singleton.

    Runs once at module import. Pulls max_iterations (T1-04) and
    max_parallel_reads (T2-02 / PAR-05) from ~/.config/voss/config.toml
    and pushes them into the runtime via a single configure() call.
    Out-of-range / malformed values fall back to the dataclass defaults
    with a RuntimeWarning (see voss.harness.config getters).
    """
    from .config import get_allow_net, get_max_iterations, get_max_parallel_reads

    configure(
        max_iterations=get_max_iterations(),
        max_parallel_reads=get_max_parallel_reads(),
        allow_net=get_allow_net(),
    )


_NET_SESSION: NetSession | None = None


def _get_net_session() -> NetSession:
    """Lazily construct the process-wide NetSession.

    Lazy so test-import never allocates an httpx client and the boot
    configure() stays construct-free (matches T1-04/T2-02 pattern).
    NetSession.__init__ registers itself with lifecycle for reap.
    """
    global _NET_SESSION
    if _NET_SESSION is None:
        from .config import get_net_rate_limits

        _NET_SESSION = NetSession(rate_overrides=get_net_rate_limits())
    return _NET_SESSION


_bootstrap_runtime_config()


_INTENT_ALLOWLIST = frozenset(
    {
        "analyze repo",
        "analyze this repo",
        "analyze this project",
        "update project memory",
        "refresh cognition",
        "rebuild cognition",
    }
)


def _classify_intent(line: str) -> str | None:
    """Literal-match natural-language router. No LLM. Returns intent name or None."""
    return "analyze" if line.lower().strip() in _INTENT_ALLOWLIST else None


_AMBIENT_SYSTEM = """You are the ambient assistant inside the Voss shell.
Answer directly and concisely. You may use the provided harness state and
project summary, but you do not have tool access in this phase. If the user
asks for code changes, tests, shell execution, multi-agent work, or any durable
repo operation, say that the request should be handled as a Voss run instead of
pretending to do it. Do not identify yourself as Voss; Voss is the harness that
can promote this conversation into a structured run."""

_WORK_INTENT_PREFIXES = (
    "add ",
    "build ",
    "change ",
    "create ",
    "debug ",
    "fix ",
    "implement ",
    "make ",
    "modify ",
    "patch ",
    "refactor ",
    "remove ",
    "repair ",
    "run ",
    "update ",
    "write ",
)
_WORK_INTENT_TERMS = (
    " add test",
    " add tests",
    " change ",
    " edit ",
    " fix ",
    " implement ",
    " refactor ",
    " run tests",
    " update ",
    " write ",
)
_STATUS_QUESTION_TERMS = (
    "what model",
    "which model",
    "model are you",
    "model is active",
    "what auth",
    "which auth",
    "auth path",
    "credential source",
    "who are you",
    "what are you",
    "status",
)


def _ambient_route(line: str) -> str:
    """Route a REPL turn before entering the structured Voss Plan loop."""
    normalized = " ".join(line.lower().strip().split())
    if not normalized:
        return "ambient"
    if normalized.startswith(_WORK_INTENT_PREFIXES):
        return "voss_run"
    padded = f" {normalized} "
    if any(term in padded for term in _WORK_INTENT_TERMS):
        return "voss_run"
    if any(term in normalized for term in _STATUS_QUESTION_TERMS):
        return "local"
    return "ambient"


def _ambient_status_answer(ctx: object, *, auth_detail: str = "") -> str:
    provider_label = _provider_label_for_runtime(
        getattr(ctx, "provider", None),
        fallback=_provider_label(auth_detail),
    )
    model = get_config().default_model
    mode = getattr(getattr(ctx, "gate", None), "mode", "")
    parts = [
        f"Provider: {provider_label or 'unknown'}",
        f"Model: {model}",
        "Phase: ambient",
    ]
    if mode:
        parts.append(f"Permission mode: {mode}")
    return "\n".join(parts)


async def _run_ambient_provider_turn(line: str, ctx: ReplContext) -> ProviderResponse:
    model = get_config().default_model
    if ctx.project_index_text:
        project_context = f"\n\nProject summary:\n{ctx.project_index_text}"
    else:
        project_context = ""
    status = _ambient_status_answer(ctx)
    messages = [
        {
            "role": "system",
            "content": (
                f"{_AMBIENT_SYSTEM}\n\nHarness state:\n{status}\n"
                f"Working directory: {ctx.cwd}{project_context}"
            ),
        },
        {"role": "user", "content": line},
    ]
    ctx.history.add(line, role="user")
    response = await ctx.provider.complete(
        messages=messages,
        model=model,
        temperature=0.2,
        max_tokens=1200,
    )
    ctx.history.add(response.text, role="assistant")
    return response


def _handle_analyze(
    *,
    cwd: Path,
    provider: ModelProvider,
    history: EpisodicMemory,
    record: session_store.SessionRecord,
    renderer,
    tools,
    gate: PermissionGate,
) -> None:
    from .skills.analyze import run as analyze_run

    analyze_run(
        cwd=cwd,
        provider=provider,
        history=history,
        record=record,
        renderer=renderer,
        tools=tools,
        gate=gate,
    )


def _handle_save_plan(
    *,
    cwd: Path,
    last_plan: "Plan | None",
    record: session_store.SessionRecord,
    line: str,
) -> None:
    if last_plan is None:
        click.echo("no plan to save yet — run a turn first", err=True)
        return
    remainder = line[len("/save-plan") :].strip()
    title = remainder or None
    try:
        path = cognition_mod.write_plan_md(
            cwd,
            last_plan,
            session_id=record.id,
            model=record.model,
            title=title,
        )
        try:
            shown = path.relative_to(cwd)
        except ValueError:
            shown = path
        click.echo(f"plan saved: {shown}")
    except OSError as exc:
        click.echo(f"warning: failed to save plan: {exc}", err=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


AUTH_CHOICES = ("auto", "claude", "codex", "api", "none")
_SUBSCRIPTION_AUTH_SOURCES = frozenset({"claude-agent", "codex-oauth"})


@dataclass
class ReplContext:
    cwd: Path
    renderer: object
    tools: dict
    gate: PermissionGate
    history: EpisodicMemory
    record: session_store.SessionRecord
    provider: ModelProvider
    skill_registry: SkillRegistry
    subagent_registry: SubagentRegistry
    slash_registry: SlashRegistry
    cognition: object | None = None
    prior_context: dict | None = None
    last_plan: Plan | None = None
    total_cost: float = 0.0
    should_exit: bool = False
    voss_md_text: str | None = None
    memory_store: object | None = None
    model: str | None = None
    persist_conventions_selection: str | None = None
    # T6 / SLASH-04 — session-scoped USD ceiling. None = unbounded.
    budget_usd: float | None = None
    project_index_text: str = ""
    # Git-backed undo/redo (OpenCode-leverage port): each /undo snapshots the
    # agent's content for the reverted files so /redo can restore them.
    redo_stack: list = field(default_factory=list)


def _resolve_default_model(user_explicit: str | None) -> None:
    """Resolve the global default model per D-09.

       1. user_explicit (--model flag) wins
       2. else ~/.config/voss/config.toml [harness] preferred_model
       3. else leave the existing get_config().default_model untouched.

    Side effect: calls configure(default_model=...) when (1) or (2) applies.
    Must be called BEFORE SessionRecord.new(...) so the record carries the
    resolved model on disk.
    """
    from . import config as harness_config

    if user_explicit:
        configure(default_model=user_explicit)
        return
    persisted = harness_config.load_harness_config().get("preferred_model")
    if persisted:
        configure(default_model=persisted)


def _is_codex_model(model: str) -> bool:
    return model.startswith("gpt-5.")


def _codex_default_model() -> str:
    model = auth_mod.load_codex_default_model()
    if model and _is_codex_model(model):
        return model
    from .subscription_models import SUBSCRIPTION_MODELS

    return SUBSCRIPTION_MODELS["codex"][0].id


def _openai_default_model() -> str:
    from .subscription_models import SUBSCRIPTION_MODELS

    return SUBSCRIPTION_MODELS["codex"][0].id


def _provider_label_for_runtime(provider: object, *, fallback: str = "") -> str:
    label = getattr(provider, "voss_provider_label", None)
    if isinstance(label, str) and label:
        return label
    if isinstance(provider, ClaudeAgentProvider):
        return "Anthropic"
    if isinstance(provider, OpenAIOAuthProvider):
        return "Codex"
    return fallback


def _provider_label_for_auth(res: auth_mod.Resolution, provider: object) -> str:
    if res.source in ("codex", "codex-oauth"):
        return "Codex"
    if res.source in ("claude-agent", "env-anthropic", "voss-anthropic"):
        return "Anthropic"
    if res.source in ("env-openai", "voss-openai"):
        return "OpenAI"
    return _provider_label_for_runtime(
        provider,
        fallback=_provider_label(f"{res.source} — {res.detail}"),
    )


def _sync_model_selection(
    ctx: object,
    *,
    model: str,
    provider: ModelProvider | None = None,
    provider_label: str | None = None,
    toast: str | None = None,
) -> None:
    if provider is not None:
        setattr(ctx, "provider", provider)
    setattr(ctx, "model", model)
    app = getattr(getattr(ctx, "renderer", None), "app", None)
    if app is None or app.__class__.__name__ != "VossTUIApp":
        return
    app.model = model
    if provider_label is not None:
        app.provider = provider_label
    try:
        from .tui.widgets.status_line import StatusLine

        kwargs: dict[str, str] = {"model": model}
        if provider_label is not None:
            kwargs["provider"] = provider_label
        if toast is not None:
            kwargs["toast"] = toast
        app.query_one("#status", StatusLine).set_status(**kwargs)
    except Exception:  # noqa: BLE001 — status widget absent in tests
        pass


def _apply_role_chain(provider, role: str, *, user_explicit: str | None = None):
    """Wrap the live provider in `role`'s fallback chain when one is configured
    (`[harness.roles.<role>]`). 429/quota on the primary then cascades to the
    next candidate within a turn. Returns the (possibly wrapped) provider and
    points `default_model` at the chain's primary. `--model` (user_explicit)
    wins and skips the override. Never raises — a missing chain or offline
    catalog leaves the provider untouched.
    """
    if user_explicit:
        return provider
    from . import roles

    try:
        built = roles.build_role_provider(role)
    except Exception:  # noqa: BLE001 — boot must never crash on catalog issues
        built = None
    if built is None:
        return provider
    new_provider, primary = built
    configure(default_model=primary)
    return new_provider


def _apply_boot_model(
    provider,
    *,
    user_explicit: str | None,
    auth_source: str | None = None,
):
    """Honor a persisted catalog-routed selection (/models) + default role chain.

    When `[harness] preferred_provider` is set and the model resolves in the
    cached catalog, rebuild the live provider for it and configure the routed
    model string (e.g. ``openai/gemma3:27b``). Then, if a `[harness.roles.default]`
    chain is configured, wrap the result in its fallback cascade. `--model` wins
    and skips both overrides. Never raises — an offline/missing catalog leaves
    the auth-resolved provider in place.
    """
    if user_explicit:
        return provider
    if auth_source in _SUBSCRIPTION_AUTH_SOURCES:
        return provider
    from . import model_router

    try:
        routed = model_router.boot_routed_provider()
    except Exception:  # noqa: BLE001 — boot must never crash on catalog issues
        routed = None
    if routed is not None:
        new_provider, model_string = routed
        configure(default_model=model_string)
        provider = new_provider
    return _apply_role_chain(provider, "default")


def _resolve_run_turn(cwd: Path | None = None):
    from . import config as harness_config

    backend = os.environ.get("VOSS_HARNESS")
    if backend is None:
        backend = harness_config.load_harness_config().get("backend")
    backend = backend or "python"

    if backend not in ("python", "compiled"):
        raise click.ClickException(
            f"invalid VOSS_HARNESS={backend!r}: expected 'python' or 'compiled'"
        )

    if backend == "python":
        from .agent import run_turn

        return run_turn

    from . import cache as harness_cache

    project_root = (cwd or Path.cwd()).resolve()
    harness_cache.assert_fresh(project_root)

    import importlib.util

    loop_py = project_root / harness_cache.CACHE_HARNESS_DIR / "loop.py"
    spec = importlib.util.spec_from_file_location(
        "voss_compiled_harness_loop",
        loop_py,
    )
    if spec is None or spec.loader is None:
        raise click.ClickException(f"failed to load compiled harness: {loop_py}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_turn


def _run_turn_cancellable(coro, *, renderer):
    """Run an agent-turn coroutine with cancel-on-Ctrl-C semantics (T1-06).

    Replaces `asyncio.run(coro)` everywhere. Steps:
      1. Create a new event loop and a Task wrapping the coro.
      2. If `renderer.app` exists (TextualRenderer only — see
         voss/harness/tui/renderer.py:47), register the Task on that app so
         VossTUIApp.action_interrupt can cancel it.
      3. Install a SIGINT handler so Ctrl-C in the headless path also
         cancels the Task. On platforms where add_signal_handler raises
         NotImplementedError (Windows) or RuntimeError (non-main thread),
         fall back without raising.
      4. Run the loop until the Task completes.
      5. Return the result. Re-raise CancelledError as click.Abort so the
         CLI exits with a non-zero status on user-initiated cancel.
    """
    import signal as _signal

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(coro)

    app = getattr(renderer, "app", None)
    if app is not None and hasattr(app, "register_turn_task"):
        app.register_turn_task(task)

    handler_installed = False
    try:
        try:
            loop.add_signal_handler(_signal.SIGINT, task.cancel)
            handler_installed = True
        except (NotImplementedError, RuntimeError):
            # Windows / non-main-thread fallback; KeyboardInterrupt still
            # reaches the loop via the default handler.
            pass
        try:
            return loop.run_until_complete(task)
        except asyncio.CancelledError:
            raise click.Abort()
    finally:
        if handler_installed:
            try:
                loop.remove_signal_handler(_signal.SIGINT)
            except Exception:  # noqa: BLE001
                pass
        loop.close()
        asyncio.set_event_loop(None)


async def _run_turn_with_teardown(turn_coro, teardown):
    """Await one chat-turn coroutine, then ALWAYS run the M13 orphan-teardown.

    M13-06 / T-M13-02: child sub-agents are detached `asyncio.create_task`
    coroutines on the SAME event loop that runs the parent turn. The plain
    path's `_run_turn_cancellable` closes that loop after the turn, so the
    defensive `_teardown_orphans` (cancel + release + collapse un-gathered
    children) MUST run on this loop, in this coroutine's `finally`, before the
    loop is torn down — otherwise an un-gathered or cancelled turn would leak
    orphan child tasks/panels into the next turn. The teardown is itself
    idempotent (a clean turn that called `subagent_gather` leaves nothing to
    do), so running it unconditionally per turn is safe.
    """
    try:
        return await turn_coro
    finally:
        if teardown is not None:
            try:
                await teardown()
            except Exception:  # noqa: BLE001 — teardown must never mask the turn
                pass


def _emit_harness_boot_telemetry(cwd: Path, model: str | None) -> None:
    """Emit session lifecycle when agent commands start (only if VOSS_LOG is enabled)."""
    from . import config as harness_config
    from . import telemetry as tel_mod

    if not tel_mod.enabled():
        return
    backend = os.environ.get("VOSS_HARNESS")
    if backend is None:
        backend = harness_config.load_harness_config().get("backend")
    backend_str = str(backend or "python").strip()
    tel_mod.ensure_trace_id()
    tel_mod.emit_harness_start(backend=backend_str, cwd=str(cwd.resolve()), model=model)


def _handle_login_status(provider: str | None) -> None:
    """Status + refresh for existing creds; for missing, print upstream commands.

    M1 contract: re-auth flows go through the upstream CLI (`claude /login`,
    `codex login`); this function only refreshes EXISTING tokens and prints
    upstream commands for MISSING tokens. The interactive `voss login`
    wizard (Phase 4) is the user-facing entry point for first-run setup.
    """
    if provider in (None, "anthropic"):
        claude = auth_mod.load_anthropic_oauth()
        if claude is None:
            click.echo("  Claude: no creds found. Run: claude /login")
        elif claude.expired:
            click.echo("  Claude: tokens expired, refreshing...")
            try:
                auth_mod.refresh_anthropic(claude)
                click.echo("  Claude: refreshed")
            except Exception as e:  # noqa: BLE001
                click.echo(
                    f"  Claude: refresh failed ({e}). Run: claude /login",
                    err=True,
                )
        else:
            click.echo(
                f"  Claude: OK (expires in {claude.expires_in_seconds}s, "
                f"{claude.subscription_type})"
            )
    if provider in (None, "openai", "codex"):
        codex = auth_mod.load_codex()
        if codex is None:
            click.echo("  Codex:  no creds found. Run: codex login")
        else:
            bits: list[str] = []
            if codex.api_key:
                bits.append("OPENAI_API_KEY")
            if codex.has_oauth:
                bits.append("OAuth tokens")
            click.echo(
                f"  Codex:  OK ({codex.auth_mode}; {', '.join(bits) or 'empty'})"
            )
    if provider is not None and provider not in ("anthropic", "openai", "codex"):
        click.echo(
            f"unknown provider: {provider}. use anthropic | openai",
            err=True,
        )


_handle_login = _handle_login_status  # backward-compat alias for older callers


def _run_textual_app(app) -> None:
    """Run a Textual app via its synchronous entry point.

    Textual owns signal handling and terminal teardown in `App.run()`. Wrapping
    `run_async()` in `asyncio.run()` leaks internal focus/unmount trace lines
    after Ctrl-C restores the terminal.
    """
    app.run()


def _build_provider_for_auth(
    res: auth_mod.Resolution,
    *,
    announce: bool = True,
) -> ModelProvider:
    if res.source == "claude-agent":
        if announce:
            click.echo(
                "  [claude-agent: using your Claude subscription via the Agent SDK "
                "(claude -p); API-billing env vars are shadowed for this "
                "subprocess.]",
                err=True,
            )
        provider: ModelProvider = ClaudeAgentProvider(cli_path=res.cli_path)
        cfg = get_config()
        # The Agent SDK only serves claude-* models. Snap any non-claude
        # default to the current baseline; leave an explicit claude-* alone.
        if not cfg.default_model.startswith("claude"):
            configure(default_model="claude-sonnet-4-5")
    elif res.source == "codex-oauth":
        if announce:
            click.echo(
                "  [codex-oauth: using your ChatGPT subscription via "
                "chatgpt.com/backend-api/codex (unofficial endpoint; $0 per-token "
                "but ToS-gray and may change without notice).]",
                err=True,
            )
        provider = OpenAIOAuthProvider(res.codex_oauth)  # type: ignore[arg-type]
        cfg = get_config()
        # The ChatGPT-account Codex backend only accepts gpt-5.x model ids
        # (gpt-5/gpt-5-codex/gpt-4o are rejected). Snap any non-codex default
        # to Codex CLI's own default when set; leave a compatible choice alone.
        if not _is_codex_model(cfg.default_model):
            configure(default_model=_codex_default_model())
    elif res.source in ("env-anthropic", "voss-anthropic"):
        # `resolve()` already injected ANTHROPIC_API_KEY into env for the
        # voss-anthropic case, so LiteLLM picks it up the same as env-anthropic.
        provider = _new_litellm_provider()
    elif res.source in ("env-openai", "voss-openai", "codex"):
        if res.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", res.openai_api_key)
        cfg = get_config()
        if cfg.default_model.startswith("claude"):
            configure(default_model=_openai_default_model())
        provider = _new_litellm_provider()
        if res.source == "codex":
            setattr(provider, "voss_provider_label", "Codex")
    else:
        provider = _new_litellm_provider()
    return provider


def _resolve_auth_or_die(
    preference: str,
    *,
    announce: bool = True,
) -> tuple[auth_mod.Resolution, ModelProvider]:
    """Pick an auth path, build a provider for it, or exit 2.

    First-run UX: on a TTY with no creds, launch the interactive login wizard
    instead of failing out. Non-TTY callers (CI, pipes, `voss do < script`)
    still get the original exit-2 error so scripted invocations stay
    deterministic.
    """
    # Honor a persisted default (`[harness] auth`) when the caller didn't force
    # a specific source. Lets `voss chat` always use e.g. codex even when
    # OPENAI_API_KEY is exported in the shell. Explicit --auth=<x> still wins.
    if preference == "auto":
        from . import config as _hc

        saved = _hc.load_harness_config().get("auth")
        if saved in AUTH_CHOICES and saved != "auto":
            preference = saved

    res = auth_mod.resolve(preference)
    if res.source == "none":
        from . import login_wizard

        if login_wizard.stdin_is_interactive():
            new_res = login_wizard.run_login_wizard(
                reason=f"no credentials found ({res.detail})"
            )
            if new_res is not None:
                res = new_res
        if res.source == "none":
            click.echo(
                f"no usable credentials ({res.detail}). try one of:\n"
                "  • run `voss login` to launch the interactive setup wizard\n"
                "  • export ANTHROPIC_API_KEY=... (or OPENAI_API_KEY)\n"
                "  • run `claude /login` (Claude Code, macOS Keychain)\n"
                "  • run `codex login` (~/.codex/auth.json)\n"
                "  • voss --auth=<auto|claude|codex|api>",
                err=True,
            )
            sys.exit(2)

    return res, _build_provider_for_auth(res, announce=announce)


def _git_status(cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "not a git repo"
    if out.returncode != 0:
        return "not a git repo"
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    if not lines:
        return "clean"
    plus = sum(1 for ln in lines if ln.startswith(("A", "?")))
    minus = sum(1 for ln in lines if ln.startswith("D"))
    mod = sum(1 for ln in lines if ln.startswith(" M") or ln.startswith("M"))
    return f"+{plus} ~{mod} -{minus}"


def _print_plugins(ctx: ReplContext) -> None:
    plugins = load_plugins(
        ctx.cwd,
        command_ids=ctx.slash_registry.ids(),
        skill_ids=ctx.skill_registry.ids(),
        agent_ids=ctx.subagent_registry.ids(),
    )
    if not plugins:
        click.echo("(no plugins)")
        return
    for plugin in plugins:
        status = "enabled" if plugin.enabled else "disabled"
        click.echo(f"  {plugin.id:<20} {status:<8} {plugin.name}")
        for warning in plugin.warnings:
            click.echo(f"    warning: {warning}", err=True)


def _print_skills(ctx: ReplContext) -> None:
    for entry in ctx.skill_registry.entries():
        mut = "mut" if entry.mutating else "read"
        click.echo(f"  {entry.id:<16} {mut:<4} {entry.description}")


def _print_agents(ctx: ReplContext) -> None:
    for spec in ctx.subagent_registry.entries():
        click.echo(f"  {spec.id:<16} {spec.description}")


def _render_probable_inspect(
    cwd: Path, session_id_or_name: str, decision_index: int | None
) -> str:
    run = load_run(cwd, session_id_or_name)
    return render_decision_sequence(run, decision_index=decision_index)


def _render_budget_inspect(cwd: Path, session_id_or_name: str) -> str:
    run = load_run(cwd, session_id_or_name)
    return render_budget_timeline(run)


def _render_voss_py_diff(cwd: Path, source: str) -> str:
    source = source.strip()
    if not source:
        raise ValueError("missing source: expected .voss file")
    try:
        path = jail_path(cwd, source)
    except SandboxError as exc:
        raise ValueError(f"path outside cwd: {source}") from exc
    if not path.exists():
        raise FileNotFoundError(f"not found: {source}")
    if path.is_dir():
        raise ValueError(f"expected .voss file, got directory: {source}")
    if path.suffix != ".voss":
        raise ValueError(f"expected .voss source file, got {source}")
    try:
        from .voss_diff import render_voss_py_diff
    except ModuleNotFoundError as exc:
        if exc.name == "voss.harness.voss_diff":
            raise ValueError("voss diff core unavailable") from exc
        raise
    try:
        return render_voss_py_diff(path, cwd=cwd)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(str(exc)) from exc


_RECALL_USAGE = "usage: /recall <query> [--top N] [--source turn|decision|convention|ledger|note]"


def _pop_flag_value(args: list[str], flag: str) -> tuple[list[str], str | None]:
    """Return (args_without_flag, flag_value or None)."""
    if flag not in args:
        return args, None
    idx = args.index(flag)
    if idx + 1 >= len(args):
        return args[:idx], None
    value = args[idx + 1]
    return args[:idx] + args[idx + 2 :], value


def _recall(ctx, args: list[str], _line: str) -> None:
    if not args:
        click.echo(_RECALL_USAGE, err=True)
        return
    args, top_raw = _pop_flag_value(list(args), "--top")
    args, source = _pop_flag_value(args, "--source")
    try:
        top_k = int(top_raw) if top_raw is not None else 5
    except ValueError:
        click.echo(_RECALL_USAGE, err=True)
        return
    query = " ".join(args).strip()
    if not query:
        click.echo(_RECALL_USAGE, err=True)
        return
    store = getattr(ctx, "memory_store", None)
    if store is None:
        click.echo("/recall unavailable: memory store not bound", err=True)
        return
    hits = store.recall(query, top_k=top_k, source=source)
    if not hits:
        click.echo("(no hits)")
        return
    for h in hits:
        click.echo(f"[{h.source}] {h.locator}  (score {h.score:.2f})")
        excerpt = (h.excerpt or "").replace("\n", " ")[:160]
        if excerpt:
            click.echo(f"  {excerpt}")


def _forget(ctx, args: list[str], _line: str) -> None:
    if not args:
        click.echo("usage: /forget <pattern> [--yes]", err=True)
        return
    pattern = args[0]
    confirm = "--yes" in args[1:]
    non_interactive = not sys.stdin.isatty()
    if non_interactive and not confirm:
        click.echo("/forget requires --yes in non-interactive mode", err=True)
        return
    store = getattr(ctx, "memory_store", None)
    if store is None:
        click.echo("/forget unavailable: memory store not bound", err=True)
        return
    n = store.forget(pattern, confirm=confirm)
    click.echo(f"tombstoned: {n} entries")


def _memory(ctx, args: list[str], _line: str) -> None:
    args, source = _pop_flag_value(list(args), "--source")
    store = getattr(ctx, "memory_store", None)
    if store is None:
        click.echo("/memory unavailable: memory store not bound", err=True)
        return
    click.echo(store.summary(source=source))


def _save_note(ctx, args: list[str], _line: str) -> None:
    # Pitfall 1 invariant: do NOT mutate ctx.record.name — that is /save-session's job.
    text = " ".join(args).strip()
    if not text:
        click.echo("usage: /save <note text>", err=True)
        return
    store = getattr(ctx, "memory_store", None)
    if store is None:
        click.echo("/save unavailable: memory store not bound", err=True)
        return
    try:
        path = store.write_note(text, session_id=ctx.record.id)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"failed: {exc}", err=True)
        return
    cwd = getattr(ctx, "cwd", None)
    try:
        display = path.relative_to(cwd) if cwd else path
    except ValueError:
        display = path
    click.echo(f"note saved: {display}")


def _run_async_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[object] = []
    error: list[BaseException] = []

    def _runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0] if result else None


def _get_code_service(cwd: Path, session_id: str | None = None):
    from voss.harness.code.service import CodeIntelService

    return CodeIntelService.for_cwd(cwd, session_id=session_id)


def _looks_like_project_root(cwd: Path) -> bool:
    try:
        if cwd.resolve() == Path.home().resolve():
            return False
    except OSError:
        pass
    markers = (
        ".git",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "deno.json",
        "pnpm-workspace.yaml",
    )
    return any((cwd / marker).exists() for marker in markers)


def _render_project_index_text(cwd: Path, session_id: str | None = None) -> str:
    if not _looks_like_project_root(cwd):
        return ""
    try:
        from voss.harness.code.context import render_project_index_section

        svc = _get_code_service(cwd, session_id=session_id)
        return render_project_index_section(svc.get_project_index_summary()) or ""
    except Exception:
        return ""


# --- V19-05 VSEM-06: code-recall auto-injection -----------------------------

# One CodeIndexService (one Chroma client) per cwd for the injection path —
# a fresh service per render would re-spawn builds and never reach ready.
_CODE_RECALL_SERVICES: dict[str, object] = {}

_CODE_RECALL_TOKEN_CAP = 1000  # VSEM-06 hard cap, measured by the V18 counter


def _get_code_recall_service(cwd: Path, session_id: str | None = None):
    key = str(cwd.resolve())
    svc = _CODE_RECALL_SERVICES.get(key)
    if svc is None:
        from voss.harness.code.semantic_index import CodeIndexService

        svc = CodeIndexService(cwd, session_id=session_id)
        svc.ensure_background_build()
        _CODE_RECALL_SERVICES[key] = svc
    return svc


def _render_code_recall_text(cwd: Path, task_text: str, session_id: str | None = None) -> str:
    """Render the `## Code Recall` system section for the current task.

    Returns "" (zero injection bytes) when: inject=false (VSEM-06 off-switch),
    the index is not ready (D-07 — skip entirely, no blocking, no placeholder),
    or there are no hits. Capped <=1000 tokens by the V18 counter — the section
    rides the V18 variable region, no second budget system.
    """
    if not task_text or not task_text.strip():
        return ""
    try:
        from voss.harness.config import get_code_recall_config

        if not get_code_recall_config().get("inject", True):
            return ""
        svc = _get_code_recall_service(Path(cwd), session_id=session_id)
        if not svc.is_ready():
            return ""
        hits = svc.query(task_text.strip(), top_k=5)
        if not hits:
            return ""

        from voss.harness.agent import _default_token_count

        model = get_config().default_model
        section = "## Code Recall\nTask-relevant code (semantic index):"
        for h in hits:
            parts = h.locator.split(":")
            path = ":".join(parts[1:-1]) if len(parts) >= 3 else h.locator
            anchor = f"{path}:{h.line_start}" if h.line_start else path
            excerpt = (h.excerpt or "").replace("\n", " ")[:160]
            block = f"\n- {anchor} (score {h.score:.2f})\n  {excerpt}"
            if _default_token_count(section + block, model=model) > _CODE_RECALL_TOKEN_CAP:
                break  # hard cap (VSEM-06)
            section += block
        return section
    except Exception:  # noqa: BLE001 — injection is additive; failures render nothing
        return ""


def _code_recall_kwargs(run_turn_fn, cwd: Path, task_text: str, session_id: str | None = None) -> dict:
    """kwargs-splat guard: compiled loop.voss run_turn variants may predate
    the code_recall_text param (same hazard as packing_enabled in V18) —
    render + pass only when the resolved run_turn accepts it."""
    try:
        import inspect as _inspect

        if "code_recall_text" not in _inspect.signature(run_turn_fn).parameters:
            return {}
    except (TypeError, ValueError):
        return {}
    text = _render_code_recall_text(cwd, task_text, session_id=session_id)
    return {"code_recall_text": text} if text else {}


def _pinned_memory_kwargs(run_turn_fn, cwd: Path, *, model: str) -> dict:
    """kwargs-splat guard for VRNK-06 pinned-memory injection.

    Returns {} when the resolved run_turn predates `pinned_memory_text` (compiled
    loop.voss compat — same hazard as packing_enabled/code_recall_text), else
    renders the always-injected pinned block and passes it only when non-empty.
    Pins do NOT go through recall, so no telemetry is recorded here.
    """
    try:
        import inspect as _inspect

        if "pinned_memory_text" not in _inspect.signature(run_turn_fn).parameters:
            return {}
    except (TypeError, ValueError):
        return {}
    try:
        text = MemoryStore(cwd).render_pinned_memory_text(model=model)
    except Exception:  # noqa: BLE001 — injection is additive; failures render nothing
        return {}
    return {"pinned_memory_text": text} if text else {}


def _show_code_intel_results(ctx: ReplContext, query: str, items: list[dict]) -> None:
    renderer = getattr(ctx, "renderer", None)
    show = getattr(renderer, "show_code_intel_results", None)
    if callable(show):
        try:
            show(query, items)
        except Exception:
            pass


def _symbol(ctx: ReplContext, args: list[str], _line: str) -> None:
    if not args or args[0] in ("--help", "-h"):
        click.echo("usage: /symbol <name>   (M10 code intelligence — index)")
        return
    symbol = args[0]
    svc = _get_code_service(ctx.cwd, session_id=ctx.record.id)
    res = svc.find_symbols(symbol, max_results=10)
    items = res.get("items", [])
    if not items:
        click.echo(f"no symbols found for {symbol}")
        _show_code_intel_results(ctx, f"/symbol {symbol}", [])
        return
    for item in items:
        click.echo(
            f"{item['name']} {item['file']}:{item['line']} "
            f"[{item.get('language', 'unknown')} {item.get('source', 'index')}]"
        )
    _show_code_intel_results(ctx, f"/symbol {symbol}", items)


def _refs(ctx: ReplContext, args: list[str], _line: str) -> None:
    if not args or args[0] in ("--help", "-h"):
        click.echo("usage: /refs <symbol>   (M10 code intelligence — index + LSP)")
        return
    symbol = args[0]
    svc = _get_code_service(ctx.cwd, session_id=ctx.record.id)
    res = _run_async_sync(svc.find_references(symbol, max_results=10))
    items = res.get("items", []) if isinstance(res, dict) else []
    if not items:
        click.echo(f"no references found for {symbol}")
        _show_code_intel_results(ctx, f"/refs {symbol}", [])
        return
    for item in items:
        click.echo(
            f"{item['file']}:{item['line']} "
            f"[{item.get('language', 'unknown')} {item.get('source', 'regex')}] "
            f"{item.get('context', '')}"
        )
    _show_code_intel_results(ctx, f"/refs {symbol}", items)


def _refresh(ctx: ReplContext, args: list[str], _line: str) -> None:
    if args and args[0] in ("--help", "-h"):
        click.echo("usage: /refresh   rebuild code index under .voss-cache/code/")
        return
    svc = _get_code_service(ctx.cwd, session_id=ctx.record.id)
    res = _run_async_sync(svc.code_refresh())
    if isinstance(res, dict) and res.get("result") == "ok":
        ctx.project_index_text = _render_project_index_text(ctx.cwd, session_id=ctx.record.id)
        summary = svc.get_project_index_summary()
        if summary is not None:
            click.echo(
                f"refreshed code index: {summary.file_count} files, "
                f"{summary.symbol_count} symbols"
            )
        else:
            click.echo("refreshed code index")
        renderer = getattr(ctx, "renderer", None)
        show = getattr(renderer, "show_code_intel_tree", None)
        if callable(show) and summary is not None:
            try:
                show([
                    {"label": path, "count": count}
                    for path, count in summary.top_modules
                ])
            except Exception:
                pass
        return
    click.echo(f"refresh failed: {res}", err=True)


def _doctor(ctx: ReplContext, args: list[str], _line: str) -> None:
    if args and args[0] in ("--help", "-h"):
        click.echo("usage: /doctor   run health checks (repairs: `voss doctor --fix` in shell)")
        return
    from . import diagnostics as diag
    from . import repair as repair_mod

    results = diag.run_all_checks(ctx.cwd)
    _render_doctor_table(results)
    if repair_mod.repair_candidates(results):
        click.echo("  machine-repairable issues found — run: voss doctor --fix")


def _build_slash_registry() -> SlashRegistry:
    registry = SlashRegistry()

    def _exit(ctx: ReplContext, _args: list[str], _line: str) -> None:
        ctx.should_exit = True

    def _help(ctx: ReplContext, _args: list[str], _line: str) -> None:
        _print_slash_help(ctx.slash_registry)

    def _clear(ctx: ReplContext, _args: list[str], _line: str) -> None:
        ctx.history = EpisodicMemory(capacity=40)
        click.echo("episodic memory cleared.")

    def _cost(ctx: ReplContext, args: list[str], _line: str) -> None:
        # T6 / SLASH-07: support --by-model and --by-tool flags.
        flags = {a.lstrip("-") for a in args}
        if "by-tool" in flags:
            click.echo(
                "  /cost --by-tool: per-tool cost tracking lands with T6 SLASH-07. "
                "Recorder doesn't yet attribute provider cost to individual tool calls."
            )
            return
        if "by-model" in flags:
            # SessionRecord pins one model per session today. Group by
            # record.model from each run; falls back to "unknown".
            by_model: dict[str, float] = {}
            for run in ctx.record.runs:
                m = (
                    ctx.record.model
                    or get_config().default_model
                    or "unknown"
                )
                by_model[m] = by_model.get(m, 0.0) + float(run.get("cost_usd", 0.0))
            if not by_model:
                click.echo(f"session cost: ${ctx.total_cost:.4f} (no runs yet)")
                return
            width = max(len(m) for m in by_model)
            click.echo(f"session cost: ${ctx.total_cost:.4f}")
            for m, c in sorted(by_model.items(), key=lambda kv: -kv[1]):
                click.echo(f"  {m:<{width}}  ${c:.4f}")
            return
        # Default: flat total (existing behavior).
        budget = ctx.budget_usd
        if budget is not None:
            pct = (ctx.total_cost / budget * 100.0) if budget > 0 else 0.0
            click.echo(
                f"session cost: ${ctx.total_cost:.4f} / ${budget:.2f} "
                f"({pct:.1f}%)"
            )
        else:
            click.echo(f"session cost: ${ctx.total_cost:.4f}")
        # V18 VOPT-05 (D-01/D-03): one labeled savings line from the session
        # ledger. Silent when no ledger (short runs / --no-pack feels like
        # nothing changed); a malformed ledger never breaks /cost.
        try:
            from voss.harness.session import _sessions_dir

            ledger = (
                _sessions_dir(Path(getattr(ctx, "cwd", None) or ctx.record.cwd))
                / str(ctx.record.id)
                / "token-savings.jsonl"
            )
            if ledger.is_file():
                rows = [
                    json.loads(line)
                    for line in ledger.read_text().splitlines()
                    if line.strip()
                ]
                original = sum(int(r.get("original_tokens_est", 0)) for r in rows)
                packed = sum(int(r.get("packed_tokens_est", 0)) for r in rows)
                if rows and original > 0:
                    save_pct = round((1 - packed / original) * 100)
                    usd_vals = [r.get("saved_usd_est") for r in rows]
                    line = (
                        f"context packed: ~{original:,}→~{packed:,} tokens "
                        f"(−{save_pct}%)"
                    )
                    if any(isinstance(v, (int, float)) for v in usd_vals):
                        usd = sum(
                            v for v in usd_vals if isinstance(v, (int, float))
                        )
                        line += f"  ~${usd:.4f} saved"
                    click.echo(line)
        except Exception:  # noqa: BLE001 — estimates line is best-effort
            pass

    def _budget(ctx: ReplContext, args: list[str], _line: str) -> None:
        # T6 / SLASH-04. No args → show current. One arg → set USD ceiling.
        if not args:
            if ctx.budget_usd is None:
                click.echo("  budget: unbounded")
            else:
                click.echo(
                    f"  budget: ${ctx.budget_usd:.2f} "
                    f"(used ${ctx.total_cost:.4f})"
                )
            return
        try:
            new_budget = float(args[0].lstrip("$"))
        except ValueError:
            click.echo("usage: /budget <usd>  (e.g. /budget 5.00)", err=True)
            return
        if new_budget < 0:
            click.echo("budget must be non-negative", err=True)
            return
        ctx.budget_usd = new_budget
        if new_budget == 0:
            click.echo("  budget: cleared (unbounded)")
            ctx.budget_usd = None
            return
        warn = (
            "  ⚠ already over budget"
            if ctx.total_cost > new_budget
            else ""
        )
        click.echo(
            f"  budget: ${new_budget:.2f} (used ${ctx.total_cost:.4f}){warn}"
        )

    def _probable(ctx: ReplContext, args: list[str], _line: str) -> None:
        raw_args = list(args)
        args, decision_raw = _pop_flag_value(raw_args, "--decision")
        if "--decision" in raw_args and decision_raw is None:
            click.echo(
                "usage: /probable <session-id-or-name> [--decision N]",
                err=True,
            )
            return
        if len(args) > 1:
            click.echo(
                "usage: /probable <session-id-or-name> [--decision N]",
                err=True,
            )
            return
        try:
            decision_index = (
                int(decision_raw) if decision_raw is not None else None
            )
        except ValueError:
            click.echo("--decision must be an integer", err=True)
            return
        target = args[0] if args else ctx.record.id
        try:
            text = _render_probable_inspect(ctx.cwd, target, decision_index)
        except (FileNotFoundError, ValueError, IndexError) as exc:
            click.echo(f"/probable failed: {exc}", err=True)
            return
        show = getattr(getattr(ctx, "renderer", None), "show_probable_inspector", None)
        if callable(show):
            show(text)
        else:
            click.echo(text)

    def _btrace(ctx: ReplContext, args: list[str], _line: str) -> None:
        if len(args) > 1:
            click.echo("usage: /btrace <session-id-or-name>", err=True)
            return
        target = args[0] if args else ctx.record.id
        try:
            text = _render_budget_inspect(ctx.cwd, target)
        except (FileNotFoundError, ValueError, IndexError) as exc:
            click.echo(f"/btrace failed: {exc}", err=True)
            return
        show = getattr(getattr(ctx, "renderer", None), "show_budget_trace", None)
        if callable(show):
            show(text)
        else:
            click.echo(text)

    def _vdiff(ctx: ReplContext, args: list[str], _line: str) -> None:
        if len(args) != 1:
            click.echo("usage: /vdiff <file.voss>", err=True)
            return
        try:
            text = _render_voss_py_diff(ctx.cwd, args[0])
        except (FileNotFoundError, ValueError) as exc:
            click.echo(f"/vdiff failed: {exc}", err=True)
            return
        show = getattr(getattr(ctx, "renderer", None), "show_voss_py_diff", None)
        if callable(show):
            show(text)
        else:
            click.echo(text)

    def _why(ctx: ReplContext, _args: list[str], _line: str) -> None:
        # T6 / SLASH-06. Render last plan's rationale + per-step why +
        # confidence. No provider call — reads ctx.last_plan only.
        plan = ctx.last_plan
        if plan is None:
            click.echo("no plan yet — run a turn first", err=True)
            return
        click.echo(f"  rationale: {plan.rationale}")
        click.echo(f"  confidence: {plan.confidence:.2f}")
        if plan.steps:
            click.echo("  steps:")
            for i, step in enumerate(plan.steps, 1):
                why = (step.why or "").strip()
                tag = f" — {why}" if why else ""
                click.echo(f"    {i}. {step.name}{tag}")
        if plan.open_question:
            click.echo(f"  open question: {plan.open_question}")
        if plan.final_when_done:
            click.echo(f"  final-when-done: {plan.final_when_done}")

    def _diff(ctx: ReplContext, args: list[str], _line: str) -> None:
        # T6 / SLASH-01. v0.1 applies edits immediately (no queued-diff
        # store yet — that lands with T1 iteration loop). Surface honest
        # diff against the working tree via `git diff`.
        cmd = ["git", "diff"]
        if args and args[0] in ("--staged", "--cached"):
            cmd.append("--cached")
            args = args[1:]
        cmd.extend(args)  # optional path filter
        try:
            out = subprocess.run(
                cmd,
                cwd=str(ctx.cwd),
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            click.echo(f"/diff failed: {exc}", err=True)
            return
        if out.returncode != 0 and out.stderr:
            click.echo(out.stderr.rstrip(), err=True)
            return
        body = out.stdout.rstrip()
        if not body:
            click.echo("  (no changes)")
            return
        click.echo(body)

    def _apply(_ctx: ReplContext, _args: list[str], _line: str) -> None:
        # T6 / SLASH-02. Honest stub: v0.1 has no pending-edit queue. Edits
        # commit immediately under PermissionGate. Real queued-apply lands
        # with T1 iteration loop (per ROADMAP). Surface this rather than
        # silently no-op.
        click.echo(
            "  /apply: v0.1 applies edits immediately under PermissionGate. "
            "Pending-edit queue + per-hunk approval lands with T1 + M9-05. "
            "Use /mode plan to dry-run, then /mode edit to commit."
        )

    def _discard(ctx: ReplContext, args: list[str], _line: str) -> None:
        # T6 / SLASH-03. v0.1 has no pending-edit queue; the meaningful
        # action is reverting files the agent changed in the most recent
        # run. Requires --confirm flag; lists files otherwise.
        if not ctx.record.runs:
            click.echo("  no runs yet — nothing to discard.")
            return
        last_run = ctx.record.runs[-1]
        changed = list(last_run.get("changed") or [])
        if not changed:
            click.echo("  last run changed no files — nothing to discard.")
            return
        if "--confirm" not in args:
            click.echo(
                "  /discard would `git checkout --` against the last run's "
                "changed files:"
            )
            for path in changed:
                click.echo(f"    {path}")
            click.echo("  re-run with --confirm to revert.")
            return
        try:
            out = subprocess.run(
                ["git", "checkout", "--", *changed],
                cwd=str(ctx.cwd),
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            click.echo(f"/discard failed: {exc}", err=True)
            return
        if out.returncode != 0:
            click.echo(
                (out.stderr or "git checkout failed").rstrip(), err=True
            )
            return
        click.echo(f"  reverted {len(changed)} file(s) via git checkout.")

    def _undo(ctx: ReplContext, _args: list[str], _line: str) -> None:
        # OpenCode-leverage port of /undo (ctrl+x u): git-backed revert of the
        # last run's file changes, but reversible — snapshot the agent's content
        # first so /redo can put it back. Unlike /discard, no --confirm (it's
        # undoable) and it records a redo entry.
        if not ctx.record.runs:
            click.echo("  no runs yet — nothing to undo.")
            return
        changed = list(ctx.record.runs[-1].get("changed") or [])
        if not changed:
            click.echo("  last run changed no files — nothing to undo.")
            return
        snapshot: dict[str, bytes | None] = {}
        for rel in changed:
            p = ctx.cwd / rel
            try:
                snapshot[rel] = p.read_bytes() if p.exists() else None
            except OSError:
                snapshot[rel] = None
        reverted: list[str] = []
        failed: list[str] = []
        for rel in changed:
            try:
                out = subprocess.run(
                    ["git", "checkout", "--", rel],
                    cwd=str(ctx.cwd),
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                click.echo(f"/undo failed: {exc}", err=True)
                return
            (reverted if out.returncode == 0 else failed).append(rel)
        if reverted:
            ctx.redo_stack.append(
                {"reverted": reverted, "snapshot": snapshot}
            )
            click.echo(
                f"  undid {len(reverted)} file change(s) via git. /redo to restore."
            )
        if failed:
            click.echo(
                "  could not revert (untracked or not in git): "
                + ", ".join(failed),
                err=True,
            )

    def _redo(ctx: ReplContext, _args: list[str], _line: str) -> None:
        # Restore the agent's content captured by the most recent /undo.
        if not ctx.redo_stack:
            click.echo("  nothing to redo.")
            return
        entry = ctx.redo_stack.pop()
        snapshot = entry.get("snapshot", {})
        restored = 0
        for rel in entry.get("reverted", []):
            content = snapshot.get(rel)
            p = ctx.cwd / rel
            try:
                if content is None:
                    if p.exists():
                        p.unlink()
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(content)
                restored += 1
            except OSError as exc:
                click.echo(f"  /redo: could not restore {rel}: {exc}", err=True)
        click.echo(f"  redid {restored} file change(s).")

    def _resume(ctx: ReplContext, args: list[str], _line: str) -> None:
        # T6 / SLASH-05. Live REPL resume: swap history + record without
        # restarting the process. Gate/cognition/tools stay bound to the
        # live cwd — cross-cwd resume still requires `voss resume <id>`.
        if not args:
            click.echo("usage: /resume <session-id-or-name>", err=True)
            return
        target = args[0]
        try:
            new_record, new_history = session_store.load(target, cwd=ctx.cwd)
        except (FileNotFoundError, ValueError) as exc:
            click.echo(f"/resume failed: {exc}", err=True)
            return
        if Path(new_record.cwd).resolve() != ctx.cwd.resolve():
            click.echo(
                f"  warning: session cwd is {new_record.cwd}; staying in "
                f"{ctx.cwd}. Cross-cwd resume requires `voss resume`.",
                err=True,
            )
        ctx.record = new_record
        ctx.history = new_history
        ctx.total_cost = new_record.total_cost_usd
        ctx.last_plan = None
        ctx.prior_context = new_record.runs[-1] if new_record.runs else None
        click.echo(
            f"  resumed: {new_record.name} "
            f"({len(new_record.turns)} turns, "
            f"${new_record.total_cost_usd:.4f})"
        )

    def _tools(ctx: ReplContext, _args: list[str], _line: str) -> None:
        for name, td in ctx.tools.items():
            click.echo(f"  {name} — {td.description}")

    def _analyze(ctx: ReplContext, _args: list[str], _line: str) -> None:
        skill = ctx.skill_registry.get("analyze")
        if skill is not None:
            skill.handler(ctx, [])

    def _save_plan(ctx: ReplContext, _args: list[str], line: str) -> None:
        _handle_save_plan(
            cwd=ctx.cwd, last_plan=ctx.last_plan, record=ctx.record, line=line
        )

    def _model(ctx: ReplContext, args: list[str], _line: str) -> None:
        """Auth-aware model selector (R8).

        Bare in the TUI: the provider catalog (`/models`) so the obvious
        model picker can move from Codex auth into Anthropic, OpenAI, OpenCode,
        Ollama, etc.
        `/model auth` keeps the curated active-subscription picker for Claude
        Agent SDK / Codex ChatGPT backend. Bare in plain CLI: availability
        lines + the numbered curated list. With args: exact-id → prefix →
        substring match against the curated list; no match falls back to the
        raw set-anything behavior.

        A pick takes effect immediately without a provider rebuild: every
        turn passes get_config().default_model (cli.py turn dispatch) and
        both subscription providers take the model id per stream() call.
        """
        from . import config as harness_config
        from . import subscription_models as sub

        cfg = get_config()
        auth_mode = sub.detect_auth_mode(getattr(ctx, "provider", None))
        models = sub.SUBSCRIPTION_MODELS.get(auth_mode or "", ())
        app = getattr(getattr(ctx, "renderer", None), "app", None)
        in_tui = app is not None and app.__class__.__name__ == "VossTUIApp"

        def _apply(m) -> None:
            configure(default_model=m.id)
            harness_config.set_preferred_model(m.id)
            _sync_model_selection(
                ctx,
                model=m.id,
                toast=f"model: {m.label} · {m.id} (persisted)",
            )
            click.echo(f"  model: {m.id} (persisted)")

        def _open_auth_picker() -> bool:
            if not in_tui or not models:
                return False
            from .tui.widgets.auth_model_picker_modal import (
                AuthModelPickerModal,
            )

            label = "Claude" if auth_mode == "claude" else "Codex"

            def _on_pick(m) -> None:
                if m is not None:
                    _apply(m)

            app.push_screen(
                AuthModelPickerModal(
                    models,
                    cfg.default_model,
                    subtitle=(
                        f"Switch between {label} models. Your pick "
                        "becomes the default for new sessions."
                    ),
                ),
                _on_pick,
            )
            return True

        if not args:
            if in_tui:
                _models(ctx, [], "/models")
                return
            claude = auth_mod.load_anthropic_oauth()
            codex = auth_mod.load_codex()
            claude_ok = bool(claude and not claude.expired)
            codex_ok = bool(codex and (codex.api_key or codex.has_oauth))
            click.echo(f"  active: {cfg.default_model}")
            click.echo(f"  Claude: {'available' if claude_ok else 'unavailable'}")
            click.echo(f"  Codex:  {'available' if codex_ok else 'unavailable'}")
            if models:
                from .tui import glyphs

                click.echo(f"\n  {auth_mode} subscription models:")
                for i, m in enumerate(models, 1):
                    here = f" {glyphs.CHECK}" if m.id == cfg.default_model else ""
                    click.echo(f"    {i}. {m.id}{here}  — {m.description}")
                click.echo("\n  select: /model <id>")
            return

        if args[0].strip().lower() in ("auth", "subscription", "subscriptions"):
            if _open_auth_picker():
                return
            if not models:
                click.echo("  no active subscription model picker for this auth mode", err=True)
                return
            args = args[1:]
            if not args:
                click.echo("  select: /model <id>", err=True)
                return

        new_model = " ".join(args).strip()
        if auth_mode is not None:
            matches = sub.match(auth_mode, new_model)
            if len(matches) == 1:
                _apply(matches[0])
                return
            if len(matches) > 1:
                click.echo(
                    f"  '{new_model}' matches {len(matches)} models: "
                    + ", ".join(m.id for m in matches),
                    err=True,
                )
                return
            # 0 matches → raw set-anything fallback below (power users).
        configure(default_model=new_model)
        harness_config.set_preferred_model(new_model)
        _sync_model_selection(ctx, model=new_model)
        click.echo(f"  model: {get_config().default_model} (persisted)")

    def _models(ctx: ReplContext, args: list[str], _line: str) -> None:
        """Catalog-driven model picker (models.dev). CLI: list/filter/select by
        name; the TUI gets the searchable modal in P4."""
        from . import config as harness_config
        from . import model_catalog, model_router

        try:
            groups = model_catalog.load_catalog()
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  models catalog unavailable: {exc}", err=True)
            return
        connected = model_router.connected_providers(groups)
        current = get_config().default_model

        def _apply(entry) -> None:
            provider, model_str, key_present = model_router.prepare_model(entry)
            if not key_present:
                click.echo(
                    f"  {entry.provider_label} needs an API key ({entry.env_key}). "
                    f"Set the env var or connect via the picker (ctrl+a, P5).",
                    err=True,
                )
                return
            configure(default_model=model_str)
            if isinstance(provider, ClaudeAgentProvider) and entry.provider_id == "anthropic":
                harness_config.set_preferred_model(entry.id)
                harness_config.set_preferred_auth("claude")
            else:
                harness_config.set_preferred_routed(entry.id, entry.provider_id)
            from . import model_prefs

            model_prefs.record_recent(entry.provider_id, entry.id)
            _sync_model_selection(
                ctx,
                model=model_str,
                provider=provider,
                provider_label=entry.provider_label,
                toast=f"model: {entry.name} · {entry.provider_label} (persisted)",
            )
            click.echo(f"  model: {entry.name} · {entry.provider_label} (persisted)")

        def _print(entries) -> None:
            last = None
            for m in entries:
                if m.provider_id != last:
                    mark = "" if connected.get(m.provider_id) else "  (needs key)"
                    click.echo(f"\n  {m.provider_label}{mark}")
                    last = m.provider_id
                tag = " · Free" if m.free else ""
                here = "  ←" if (m.id == current or f"openai/{m.id}" == current) else ""
                click.echo(f"    {m.id}{tag}{here}")

        # Bare `/models` in the TUI opens the searchable modal picker, with
        # Favorites + Recent sections pinned on top (models.dev catalog below).
        app = getattr(getattr(ctx, "renderer", None), "app", None)
        if not args and app is not None and app.__class__.__name__ == "VossTUIApp":
            from . import model_prefs
            from .model_catalog import ProviderGroup
            from .tui.widgets.model_picker_modal import ModelPickerModal

            def _resolve(pairs):
                out = []
                for pid, mid in pairs:
                    e = model_router.find_entry(groups, pid, mid)
                    if e is not None:
                        out.append(e)
                return out

            synth, syn_ids, conn2 = [], set(), dict(connected)
            fav = _resolve(model_prefs.favorites())
            if fav:
                synth.append(ProviderGroup("favorites", "Favorites", None, None, tuple(fav)))
                syn_ids.add("favorites")
                conn2["favorites"] = True
            rec = _resolve(model_prefs.recent())
            if rec:
                synth.append(ProviderGroup("recent", "Recent", None, None, tuple(rec)))
                syn_ids.add("recent")
                conn2["recent"] = True

            def _on_pick(entry) -> None:
                if entry is not None:
                    _apply(entry)

            app.push_screen(
                ModelPickerModal(
                    synth + groups, conn2, current, synthetic_ids=frozenset(syn_ids)
                ),
                _on_pick,
            )
            return

        # `/models set <id> [provider]` — non-interactive, works in CLI + TUI.
        if args and args[0] == "set":
            if len(args) < 2:
                click.echo("  usage: /models set <model-id> [provider-id]", err=True)
                return
            model_id = args[1]
            provider_id = args[2] if len(args) > 2 else None
            hits = model_router.find_by_id(groups, model_id, provider_id=provider_id)
            if not hits:
                click.echo(f"  no model '{model_id}'", err=True)
            elif len(hits) > 1:
                click.echo(
                    f"  '{model_id}' exists in {len(hits)} providers; add one of: "
                    + ", ".join(h.provider_id for h in hits),
                    err=True,
                )
            else:
                _apply(hits[0])
            return

        query = " ".join(args).strip()
        if query:
            matches = model_router.match_models(groups, query)
            if len(matches) == 1:
                _apply(matches[0])
            elif not matches:
                click.echo(f"  no models match '{query}'", err=True)
            else:
                click.echo(f"  {len(matches)} match '{query}':")
                _print(matches)
                click.echo("\n  refine, or `/models set <id> [provider]`")
            return

        # No args: full grouped list + hint.
        _print(model_router.flatten(groups))
        click.echo(
            f"\n  active: {current}\n"
            "  select: /models <query>  or  /models set <id> [provider]"
        )

    def _auth(ctx: ReplContext, args: list[str], _line: str) -> None:
        """Show or persist the default credential source (`[harness] auth`).

        `/auth codex` switches the current session immediately and persists it
        so plain `voss chat` keeps using Codex even if OPENAI_API_KEY is
        exported.
        """
        from . import config as harness_config

        if not args:
            saved = harness_config.load_harness_config().get("auth") or "auto"
            click.echo(f"  default auth: {saved}")
            click.echo(f"  choices: {', '.join(AUTH_CHOICES)}")
            return
        pref = args[0].strip().lower()
        if pref not in AUTH_CHOICES:
            click.echo(f"  invalid: {pref}. choices: {', '.join(AUTH_CHOICES)}", err=True)
            return
        if pref == "none":
            harness_config.set_preferred_auth(pref)
            click.echo("  default auth: none (persisted; current session unchanged)")
            return
        res = auth_mod.resolve(pref)
        if res.source == "none":
            click.echo(
                f"  auth switch failed: no usable credentials ({res.detail})",
                err=True,
            )
            return
        try:
            provider = _build_provider_for_auth(res, announce=False)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  auth switch failed: {exc}", err=True)
            return
        harness_config.set_preferred_auth(pref)
        model = get_config().default_model
        provider_label = _provider_label_for_auth(res, provider)
        _sync_model_selection(
            ctx,
            model=model,
            provider=provider,
            provider_label=provider_label,
            toast=f"auth: {pref} · {provider_label}",
        )
        ctx.record.model = model
        click.echo(f"  default auth: {pref} (persisted)")
        click.echo(f"  active auth: {res.source} · {provider_label} / {model}")

    def _mode(ctx: ReplContext, args: list[str], _line: str) -> None:
        if not args:
            click.echo(f"  mode: {ctx.gate.mode}")
            return
        new_mode = args[0].strip()
        if new_mode not in ("plan", "edit", "auto", "observe"):
            click.echo("mode must be plan|edit|auto|observe", err=True)
            return
        if new_mode == "auto" and "--confirm" not in args:
            click.echo(
                "escalating to auto requires --confirm "
                "(e.g. /mode auto --confirm)",
                err=True,
            )
            return
        ctx.gate.mode = new_mode  # type: ignore[assignment]
        click.echo(f"  mode: {new_mode}")

    def _login(_ctx: ReplContext, args: list[str], _line: str) -> None:
        # /login              → interactive wizard (first-run setup)
        # /login status [p]   → status + refresh for existing creds (legacy)
        # /login anthropic|openai|codex → status for a single provider
        if not args:
            from . import login_wizard

            login_wizard.run_login_wizard(reason="re-auth from REPL")
            return
        if args[0] == "status":
            _handle_login_status(args[1] if len(args) > 1 else None)
            return
        _handle_login_status(args[0])

    def _save_session(ctx: ReplContext, args: list[str], _line: str) -> None:
        if args:
            ctx.record.name = " ".join(args).strip()
        ctx.record.total_cost_usd = ctx.total_cost
        ctx.record.model = get_config().default_model
        path = session_store.save(ctx.record, ctx.history)
        click.echo(f"saved: {path}")

    def _plugins(ctx: ReplContext, _args: list[str], _line: str) -> None:
        _print_plugins(ctx)

    def _plugin(ctx: ReplContext, args: list[str], _line: str) -> None:
        if len(args) != 2 or args[0] not in ("enable", "disable"):
            click.echo("usage: /plugin enable|disable <id>", err=True)
            return
        path = set_plugin_enabled(args[1], args[0] == "enable")
        click.echo(f"plugin {args[1]} {'enabled' if args[0] == 'enable' else 'disabled'}: {path}")

    def _skills(ctx: ReplContext, _args: list[str], _line: str) -> None:
        _print_skills(ctx)

    def _skill(ctx: ReplContext, args: list[str], _line: str) -> None:
        if not args:
            click.echo("usage: /skill <id> [args...]", err=True)
            return
        entry = ctx.skill_registry.get(args[0])
        if entry is None:
            click.echo(f"unknown skill: {args[0]}", err=True)
            return
        entry.handler(ctx, args[1:])

    def _agents(ctx: ReplContext, _args: list[str], _line: str) -> None:
        _print_agents(ctx)

    def _agent(ctx: ReplContext, args: list[str], _line: str) -> None:
        if len(args) < 3 or args[0] != "spawn":
            click.echo("usage: /agent spawn <id> <task>", err=True)
            return
        result = asyncio.run(
            run_subagent(
                agent_id=args[1],
                task=" ".join(args[2:]),
                registry=ctx.subagent_registry,
                cwd=ctx.cwd,
                renderer=ctx.renderer,
                provider=ctx.provider,
                model=get_config().default_model,
                gate=ctx.gate,
                cognition=ctx.cognition,
            )
        )
        click.echo(result)

    for command in (
        SlashCommand("/help", "show this list", _help),
        SlashCommand("/exit", "leave the REPL (also Ctrl-D)", _exit, aliases=("/quit",)),
        SlashCommand("/clear", "drop episodic memory", _clear),
        SlashCommand(
            "/cost",
            "session cost so far ([--by-model | --by-tool])",
            _cost,
        ),
        SlashCommand(
            "/budget",
            "show or set session USD ceiling: /budget [<usd>]",
            _budget,
        ),
        SlashCommand(
            "/probable",
            "inspect recorded decisions: /probable [session] [--decision N]",
            _probable,
        ),
        SlashCommand(
            "/btrace",
            "inspect recorded budget timeline: /btrace [session]",
            _btrace,
        ),
        SlashCommand(
            "/vdiff",
            "show source vs generated Python: /vdiff <file.voss>",
            _vdiff,
        ),
        SlashCommand(
            "/why",
            "explain the last plan (rationale, confidence, step why)",
            _why,
        ),
        SlashCommand(
            "/diff",
            "show working-tree diff: /diff [--staged] [<path>]",
            _diff,
        ),
        SlashCommand(
            "/apply",
            "no-op stub — edits commit immediately in v0.1 (T1 will queue)",
            _apply,
        ),
        SlashCommand(
            "/discard",
            "revert last run's changed files via `git checkout` (--confirm)",
            _discard,
            mutating=True,
        ),
        SlashCommand(
            "/undo",
            "git-backed revert of the last run's file changes (reversible via /redo)",
            _undo,
            mutating=True,
        ),
        SlashCommand(
            "/redo",
            "restore the file changes undone by the most recent /undo",
            _redo,
            mutating=True,
        ),
        SlashCommand(
            "/resume",
            "live-resume a saved session by id/name (same cwd only)",
            _resume,
            mutating=True,
        ),
        SlashCommand("/tools", "list registered tools", _tools),
        SlashCommand("/login", "launch sign-in wizard (or `/login status` for cred status)", _login),
        SlashCommand("/model", "pick a model/provider (TUI catalog; `/model auth` for subscription list)", _model),
        SlashCommand("/models", "pick a model from the models.dev catalog (Zen, Ollama Cloud, …)", _models),
        SlashCommand("/auth", "show/set default credential source (auto|claude|codex|api|none)", _auth),
        SlashCommand("/mode", "plan | edit | auto; auto requires --confirm", _mode),
        SlashCommand("/save-session", "persist session snapshot", _save_session, mutating=True),
        SlashCommand("/recall", "search memory (top-N hits across sources)", _recall),
        SlashCommand("/forget", "delete memory entries matching <pattern>", _forget, mutating=True),
        SlashCommand("/memory", "summarize current memory store", _memory),
        SlashCommand("/save", "append a manual note to memory", _save_note, mutating=True),
        SlashCommand("/analyze", "refresh project cognition (.voss/ + .voss-cache/)", _analyze, mutating=True),
        SlashCommand("/save-plan", "persist the most recent plan to .voss/plans/", _save_plan, mutating=True),
        SlashCommand("/plugins", "list plugin manifests", _plugins),
        SlashCommand("/plugin", "enable|disable a plugin manifest", _plugin, mutating=True),
        SlashCommand("/skills", "list registered skills", _skills),
        SlashCommand("/skill", "run a registered skill", _skill, mutating=True),
        SlashCommand("/agents", "list registered subagents", _agents),
        SlashCommand("/agent", "spawn a registered subagent", _agent, mutating=True),
        # M10-04 code intelligence slash surface
        SlashCommand("/symbol", "find symbols matching <name> (uses index + LSP)", _symbol),
        SlashCommand("/refs", "find references to <symbol>", _refs),
        SlashCommand("/refresh", "rebuild code index (and optionally refresh cognition)", _refresh, mutating=False),
        SlashCommand("/doctor", "run health checks (diagnose-only; repairs via `voss doctor --fix`)", _doctor),
    ):
        registry.register(command)
    return registry


# ---------------------------------------------------------------------------
# do — one-shot
# ---------------------------------------------------------------------------


def _apply_no_unicode_env(no_unicode: bool) -> None:
    """Set VOSS_NO_UNICODE=1 BEFORE make_renderer/glyphs import.

    The glyphs module reads the env var at import time and rewires its
    module-level constants to ASCII fallbacks. Tests can also drive the
    same code path by setting `VOSS_NO_UNICODE=1` directly.
    """
    if no_unicode:
        os.environ["VOSS_NO_UNICODE"] = "1"


def _new_litellm_provider() -> ModelProvider:
    from voss_runtime.providers import LiteLLMProvider

    return LiteLLMProvider()


def _repl_prompt() -> str:
    glyph = ">" if os.environ.get("VOSS_NO_UNICODE") == "1" else "❯"
    if os.environ.get("NO_COLOR") == "1" or not sys.stdout.isatty():
        return f"{glyph} "
    return f"\x1b[1;38;2;255;91;31m{glyph}\x1b[0m "


def _provider_label(auth_detail: str) -> str:
    lower = auth_detail.lower()
    if "openai" in lower or "codex" in lower:
        return "OpenAI"
    if "anthropic" in lower or "claude" in lower:
        return "Anthropic"
    return ""


def _wire_tui_permissions_if_textual(gate: PermissionGate, renderer) -> None:
    """If `renderer` is a TextualRenderer, install modal-driven permission prompts.

    Deferred imports keep cli.py decoupled from the Textual import graph on
    the plain / non-TTY paths.
    """
    from .tui.permissions_bridge import install_tui_permissions
    from .tui.renderer import TextualRenderer

    if isinstance(renderer, TextualRenderer):
        install_tui_permissions(gate, renderer.app)


@click.command("do")
@click.argument("task", nargs=-1, required=False)
@click.option("--model", default=None, help="Override default model.")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--json", "json_mode", is_flag=True, help="Emit NDJSON events on stdout.")
@click.option("--plain", "plain", is_flag=True, help="Use line-streamed renderer; bypass TUI.")
@click.option(
    "--no-unicode",
    "no_unicode",
    is_flag=True,
    help="Use ASCII fallback for TUI glyphs (sets VOSS_NO_UNICODE=1).",
)
@click.option(
    "--mode",
    type=click.Choice(["plan", "edit", "auto", "observe"]),
    default="plan",  # D-07: do defaults to plan
    help="Permission tier.",
)
@click.option("--yes", "yes_to_all", is_flag=True, help="Skip permission prompts.")
@click.option(
    "--allow-net/--no-allow-net",
    "allow_net",
    default=None,
    help=(
        "Enable (--allow-net) or disable (--no-allow-net) network tools "
        "(web_fetch, web_search, MCP) for this session. When neither is "
        "passed, falls back to [tools] allow_net in config.toml. NOTE: "
        "SPEC NET-05d criterion `--allow-net=false` is satisfied via the "
        "click-idiomatic `--no-allow-net` form (click flag pairs do not "
        "accept `--flag=value` syntax)."
    ),
)
@click.option(
    "--auth",
    "auth_pref",
    type=click.Choice(AUTH_CHOICES),
    default="auto",
    help="Credential source.",
)
@click.option(
    "--no-pack",
    "no_pack",
    is_flag=True,
    envvar="VOSS_NO_PACK",
    help="Disable context packing; messages byte-identical to pre-V18.",
)
def do_cmd(
    task: tuple[str, ...],
    model: str | None,
    cwd_str: str,
    json_mode: bool,
    plain: bool,
    no_unicode: bool,
    mode: str,
    yes_to_all: bool,
    allow_net: bool | None,
    auth_pref: str,
    no_pack: bool,
) -> None:
    """Run a one-shot agent task and print the final answer.

    Stdin (when piped) is appended to the task as additional context.
    """
    cwd = Path(cwd_str).resolve()
    _apply_no_unicode_env(no_unicode)
    _resolve_default_model(model)
    if allow_net is True:
        configure(allow_net=True)
    elif allow_net is False:
        configure(allow_net=False)
    # else allow_net is None: TOML setting applied at bootstrap wins
    res, provider = _resolve_auth_or_die(auth_pref)
    provider = _apply_boot_model(provider, user_explicit=model, auth_source=res.source)
    cfg = get_config()

    _emit_harness_boot_telemetry(cwd, cfg.default_model)

    parts = list(task)
    if not sys.stdin.isatty():
        parts.append("\n--- piped stdin ---\n")
        parts.append(sys.stdin.read())
    text = " ".join(parts).strip()
    if not text:
        click.echo("no task. usage: voss do \"<task>\"", err=True)
        sys.exit(2)

    renderer = make_renderer(json_mode=json_mode, plain=plain)
    # T5: deliberate _nosession — do_record is defined later; one-shot voss do
    # bg jobs are reaped at process exit, with no voss jobs contract.
    tools = make_toolset(cwd, renderer=renderer, net=_get_net_session())
    voss_md.ensure_migrated(cwd)
    do_bundle = cognition_mod.load(cwd)
    voss_md_text = voss_md.read_and_inject(cwd)
    project_index_text = _render_project_index_text(cwd)
    gate = PermissionGate(
        mode=mode,  # type: ignore[arg-type]
        store=PermissionStore.load(cwd),
        auto_yes=yes_to_all or json_mode,
        project_policy=do_bundle.permissions if do_bundle.initialized else None,
        safety_policy=do_bundle.safety if do_bundle.initialized else None,
    )
    _wire_tui_permissions_if_textual(gate, renderer)
    attach_subagent_tool(
        tools,
        registry=default_subagent_registry(),
        cwd=cwd,
        renderer=renderer,
        provider=provider,
        model=lambda: get_config().default_model,
        gate=gate,
        cognition=do_bundle,
    )

    # Conventions hook locals: do_record/do_history/do_memory_store — pinned by M8-04 plan.
    do_cwd = cwd
    do_provider = provider
    do_model = cfg.default_model
    do_record = session_store.SessionRecord.new(cwd=cwd, model=do_model)
    do_history = EpisodicMemory(capacity=40)
    do_memory_store = MemoryStore(cwd).bind(session_id=do_record.id)
    # V21 (VGMEM-*): wire the cross-project global corpus into agent recall when
    # global memory is enabled. The agent reads global hits but can never write
    # them (memory_remember only ever targets the project store).
    do_global_store = make_global_store()
    attach_memory_tools(
        tools,
        store=do_memory_store,
        session_id=do_record.id,
        global_store=do_global_store,
    )

    renderer.banner(model=cfg.default_model, cwd=cwd, git_status=_git_status(cwd))
    click.echo(f"  [auth: {res.source} — {res.detail}]")
    renderer.show_user(text)

    run_turn = _resolve_run_turn(cwd)
    # V18 VOPT-06: the compiled-harness run_turn (cache loop.py) predates
    # packing — only thread the flag when the resolved surface accepts it.
    import inspect as _inspect

    _rt_kwargs: dict = {}
    try:
        if "packing_enabled" in _inspect.signature(run_turn).parameters:
            _rt_kwargs["packing_enabled"] = not no_pack
    except (TypeError, ValueError):
        pass
    result = _run_turn_cancellable(
        run_turn(
            text,
            tools=tools,
            cwd=cwd,
            renderer=renderer,
            model=do_model,
            provider=do_provider,
            permissions=gate,
            history=do_history,
            session_id=do_record.id,
            voss_md_text=voss_md_text,
            project_index_text=project_index_text,
            **_code_recall_kwargs(run_turn, cwd, text, session_id=do_record.id),
            **_pinned_memory_kwargs(run_turn, cwd, model=do_model),
            **_rt_kwargs,
        ),
        renderer=renderer,
    )
    renderer.show_final(result.final, confidence=result.confidence, cost_usd=result.cost_usd)

    if result.run is not None:
        do_record.runs.append(asdict(result.run))

    do_ctx = SimpleNamespace(
        provider=do_provider,
        model=do_model,
        cwd=do_cwd,
        persist_conventions_selection=None,
    )
    try:
        conventions.run_on_clean_exit(
            do_ctx,
            history=do_history,
            record=do_record,
            memory_store=do_memory_store,
        )
    except Exception as exc:  # noqa: BLE001
        click.echo(f"conventions extraction skipped: {exc}", err=True)


# ---------------------------------------------------------------------------
# chat — REPL
# ---------------------------------------------------------------------------


@click.command("chat")
@click.option("--model", default=None, help="Override default model.")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--json", "json_mode", is_flag=True, help="Emit NDJSON events on stdout.")
@click.option("--plain", "plain", is_flag=True, help="Use line-streamed renderer; bypass TUI.")
@click.option(
    "--no-unicode",
    "no_unicode",
    is_flag=True,
    help="Use ASCII fallback for TUI glyphs (sets VOSS_NO_UNICODE=1).",
)
@click.option(
    "--mode",
    type=click.Choice(["plan", "edit", "auto"]),
    default="plan",  # D-07: chat defaults to plan
    help="Permission tier.",
)
@click.option(
    "--allow-net/--no-allow-net",
    "allow_net",
    default=None,
    help=(
        "Enable (--allow-net) or disable (--no-allow-net) network tools "
        "(web_fetch, web_search, MCP) for this session. When neither is "
        "passed, falls back to [tools] allow_net in config.toml. NOTE: "
        "SPEC NET-05d criterion `--allow-net=false` is satisfied via the "
        "click-idiomatic `--no-allow-net` form (click flag pairs do not "
        "accept `--flag=value` syntax)."
    ),
)
@click.option(
    "--auth",
    "auth_pref",
    type=click.Choice(AUTH_CHOICES),
    default="auto",
    help="Credential source.",
)
@click.option(
    "--keep-logs",
    "keep_logs",
    is_flag=True,
    default=False,
    help="Keep background-job logs/sidecars on session exit (default: reap them).",
)
def chat_cmd(
    model: str | None,
    cwd_str: str,
    json_mode: bool,
    plain: bool,
    no_unicode: bool,
    mode: str,
    allow_net: bool | None,
    auth_pref: str,
    keep_logs: bool,
) -> None:
    """Interactive agent REPL. Ctrl-D or /exit to quit."""
    cwd = Path(cwd_str).resolve()
    _apply_no_unicode_env(no_unicode)
    _resolve_default_model(model)
    if allow_net is True:
        configure(allow_net=True)
    elif allow_net is False:
        configure(allow_net=False)
    # else allow_net is None: TOML setting applied at bootstrap wins
    res, provider = _resolve_auth_or_die(auth_pref, announce=False)
    provider = _apply_boot_model(provider, user_explicit=model, auth_source=res.source)
    cfg = get_config()

    _emit_harness_boot_telemetry(cwd, cfg.default_model)

    _run_repl(
        cwd=cwd,
        json_mode=json_mode,
        plain=plain,
        mode=mode,
        history=EpisodicMemory(capacity=40),
        record=session_store.SessionRecord.new(cwd=cwd, model=cfg.default_model),
        provider=provider,
        auth_detail=f"{res.source} — {res.detail}",
        keep_logs=keep_logs,
    )


@click.command("edit")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--cwd",
    "cwd_str",
    default=".",
    type=click.Path(file_okay=False),
    help="Project root.",
)
@click.option("--model", default=None, help="Override default model.")
@click.option("--json", "json_mode", is_flag=True, help="Emit NDJSON events on stdout.")
@click.option("--plain", "plain", is_flag=True, help="Use line-streamed renderer; bypass TUI.")
@click.option(
    "--no-unicode",
    "no_unicode",
    is_flag=True,
    help="Use ASCII fallback for TUI glyphs (sets VOSS_NO_UNICODE=1).",
)
@click.option(
    "--mode",
    type=click.Choice(["plan", "edit", "auto"]),
    default="edit",
    help="Permission tier (default edit per D-07).",
)
@click.option(
    "--auth",
    "auth_pref",
    type=click.Choice(AUTH_CHOICES),
    default="auto",
    help="Credential source.",
)
def edit_cmd(
    path: str,
    cwd_str: str,
    model: str | None,
    json_mode: bool,
    plain: bool,
    no_unicode: bool,
    mode: str,
    auth_pref: str,
) -> None:
    """Scoped edit REPL. Writes restricted to <PATH> + sibling test mirror (D-02).

    Out-of-scope writes prompt to expand the scope for this session only.
    Reads stay free under the cwd path jail.
    """
    from .edit_scope import EditScope

    cwd = Path(cwd_str).resolve()
    _apply_no_unicode_env(no_unicode)
    _resolve_default_model(model)
    res, provider = _resolve_auth_or_die(auth_pref, announce=False)
    provider = _apply_boot_model(provider, user_explicit=model, auth_source=res.source)
    cfg = get_config()

    _emit_harness_boot_telemetry(cwd, cfg.default_model)

    scope = EditScope.resolve(cwd, path)
    record = session_store.SessionRecord.new(
        cwd=cwd,
        model=cfg.default_model,
        name=f"edit-{Path(path).name}",
    )

    click.echo(f"  edit scope: {', '.join(scope.summary()) or path}")

    _run_repl(
        cwd=cwd,
        json_mode=json_mode,
        plain=plain,
        mode=mode,
        history=EpisodicMemory(capacity=40),
        record=record,
        provider=provider,
        auth_detail=f"{res.source} — {res.detail}",
        edit_scope=scope,
    )


def _run_repl(
    *,
    cwd: Path,
    json_mode: bool,
    mode: str,
    history: EpisodicMemory,
    record: session_store.SessionRecord,
    provider: ModelProvider,
    auth_detail: str = "",
    edit_scope=None,
    prior_context: dict | None = None,
    plain: bool = False,
    keep_logs: bool = False,
) -> None:
    cfg = get_config()
    renderer = make_renderer(json_mode=json_mode, plain=plain)
    from .tui.renderer import TextualRenderer

    tools = make_toolset(
        cwd,
        renderer=renderer,
        net=_get_net_session(),
        session_id=record.id,
    )
    skill_registry = default_skill_registry()
    subagent_registry = default_subagent_registry()
    slash_registry = _build_slash_registry()

    def _tok_count(text: str) -> int:
        litellm = sys.modules.get("litellm")
        if litellm is not None:
            try:
                return int(
                    litellm.token_counter(model=cfg.default_model, text=text)
                )
            except Exception:  # noqa: BLE001
                pass
        return max(len(text) // 4, 1)

    voss_md.ensure_migrated(cwd)
    bundle = cognition_mod.load(cwd, token_count=_tok_count)
    if bundle.load_errors:
        for err in bundle.load_errors:
            click.echo(f"cognition error: {err}", err=True)
    voss_md_text = voss_md.read_and_inject(cwd)
    project_index_text = (
        "" if isinstance(renderer, TextualRenderer)
        else _render_project_index_text(cwd, session_id=record.id)
    )

    gate = PermissionGate(
        mode=mode,  # type: ignore[arg-type]
        store=PermissionStore.load(cwd),
        edit_scope=edit_scope,
        project_policy=bundle.permissions if bundle.initialized else None,
        safety_policy=bundle.safety if bundle.initialized else None,
    )
    _wire_tui_permissions_if_textual(gate, renderer)
    ctx = ReplContext(
        cwd=cwd,
        renderer=renderer,
        tools=tools,
        gate=gate,
        history=history,
        record=record,
        provider=provider,
        skill_registry=skill_registry,
        subagent_registry=subagent_registry,
        slash_registry=slash_registry,
        cognition=bundle,
        prior_context=prior_context,
        total_cost=record.total_cost_usd,
        voss_md_text=voss_md_text,
        memory_store=MemoryStore(cwd).bind(session_id=record.id),
        model=cfg.default_model,
        project_index_text=project_index_text,
    )
    attach_subagent_tool(
        tools,
        registry=subagent_registry,
        cwd=cwd,
        renderer=renderer,
        provider=provider,
        model=lambda: get_config().default_model,
        gate=gate,
        cognition=bundle,
    )
    attach_memory_tools(tools, store=ctx.memory_store, session_id=record.id)
    # M13-06: additively attach the non-blocking multi-agent fan-out toolset
    # (subagent_spawn/steer/status/gather) alongside the unchanged serial
    # subagent_run tool (D-02 back-compat). attach_multiagent_tools returns the
    # defensive _teardown_orphans awaitable (M13-03) — captured here and run in
    # a finally on the per-turn run_turn await below so an un-gathered or
    # cancelled chat turn cannot leak orphan child tasks/panels (T-M13-02).
    # V8 (VMAG-ROOT): create the chat session's V4 root node ONCE per REPL
    # (session-scoped — NOT per-turn, Pitfall 4). 60_000 is the configurable
    # chat-root envelope default (matches agent.py run_turn token_budget); the
    # carved reserve is DEFAULT_PARENT_RESERVE (30_000). The manager is injected
    # as node_manager so every chat spawn allocates a persisted child of it.
    _chat_root = SessionTreeNode.create_root(cwd=cwd, limit=60_000)
    _chat_tree = SessionTreeManager(
        _chat_root, reserve=DEFAULT_PARENT_RESERVE, cwd=cwd
    )
    _multiagent_teardown = attach_multiagent_tools(
        tools,
        registry=subagent_registry,
        cwd=cwd,
        renderer=renderer,
        provider=provider,
        model=lambda: get_config().default_model,
        gate=gate,
        cognition=bundle,
        node_manager=_chat_tree,
    )

    jobs_root = jail_path(cwd, ".voss-cache") / "jobs"
    active_session = jobs_root / ".active-session"
    try:
        jobs_root.mkdir(parents=True, exist_ok=True)
        active_session.write_text(record.id)
    except OSError as exc:
        click.echo(f"active session marker skipped: {exc}", err=True)

    git_status = _git_status(cwd)
    renderer.banner(model=cfg.default_model, cwd=cwd, git_status=git_status)

    if auth_detail and not isinstance(renderer, TextualRenderer):
        click.echo(f"  [auth: {auth_detail}]")
    if record.turns:
        click.echo(f"resumed: {record.name} ({len(record.turns)} prior turns)")

    # D-04: non-blocking drift hint. T-M2-22: wrap in try/except so a
    # malformed frontmatter can never crash REPL boot.
    if bundle.initialized and bundle.architecture_frontmatter:
        try:
            drift = cognition_mod.drift_check(cwd, bundle.architecture_frontmatter)
        except (OSError, ValueError) as exc:
            click.echo(f"drift check failed: {exc}", err=True)
        else:
            if drift.is_stale:
                click.echo(
                    f"  cognition stale ({drift.reason}) — /analyze to refresh"
                )

    try:
        if isinstance(renderer, TextualRenderer):
            renderer.app.history = ctx.history
            renderer.app.cwd = cwd
            renderer.app.record = record
            renderer.app.slash_registry = slash_registry
            renderer.app.model = cfg.default_model
            renderer.app.git_status = git_status
            renderer.app.provider = _provider_label_for_runtime(
                provider,
                fallback=_provider_label(auth_detail),
            )
            renderer.app.mode = mode
            renderer.set_phase("ambient")
            renderer.app.total_cost = ctx.total_cost

            async def _dispatch_tui_turn(line: str):
                if line.startswith("/"):
                    import io
                    old_stdout, old_stderr = sys.stdout, sys.stderr
                    cap_out, cap_err = io.StringIO(), io.StringIO()
                    handled = False
                    try:
                        sys.stdout, sys.stderr = cap_out, cap_err
                        handled = slash_registry.dispatch(ctx, line)
                    except ValueError as exc:
                        renderer.show_warning(str(exc))
                        return None
                    finally:
                        sys.stdout, sys.stderr = old_stdout, old_stderr
                    out = cap_out.getvalue().rstrip()
                    err = cap_err.getvalue().rstrip()
                    if out:
                        try:
                            tv = renderer.app.query_one("#main")
                            renderer._post(tv.append_turn, "system", out)
                        except Exception:  # noqa: BLE001
                            pass
                    if err:
                        renderer.show_warning(err)
                    if handled:
                        if ctx.should_exit:
                            renderer.app.exit()
                        return None
                    renderer.show_warning(f"unknown command: {line}. /help for list.")
                    return None
                renderer.show_user(line)
                route = _ambient_route(line)
                if route == "local":
                    answer = _ambient_status_answer(ctx, auth_detail=auth_detail)
                    ctx.history.add(line, role="user")
                    ctx.history.add(answer, role="assistant")
                    renderer.show_final(answer, confidence=1.0, cost_usd=0.0)
                    return None
                try:
                    if not ctx.project_index_text:
                        ctx.project_index_text = _render_project_index_text(
                            cwd, session_id=record.id
                        )
                    if route == "ambient":
                        response = await _run_ambient_provider_turn(line, ctx)
                        ctx.total_cost += response.cost_usd
                        renderer.show_final(
                            response.text,
                            confidence=1.0,
                            cost_usd=response.cost_usd,
                        )
                        return None
                    renderer.set_phase("run")
                    try:
                        renderer.show_thinking("starting Voss run")
                        run_turn = _resolve_run_turn(cwd)
                        result = await _run_turn_with_teardown(
                            run_turn(
                                line,
                                tools=tools,
                                cwd=cwd,
                                renderer=renderer,
                                model=get_config().default_model,
                                history=ctx.history,
                                permissions=gate,
                                provider=ctx.provider,
                                session_id=record.id,
                                cognition=bundle,
                                prior_context=ctx.prior_context,
                                voss_md_text=ctx.voss_md_text,
                                project_index_text=ctx.project_index_text,
                                **_code_recall_kwargs(run_turn, cwd, line, session_id=record.id),
                                **_pinned_memory_kwargs(run_turn, cwd, model=get_config().default_model),
                            ),
                            _multiagent_teardown,
                        )
                        ctx.prior_context = None
                    finally:
                        renderer.set_phase("ambient")
                except Exception as e:  # noqa: BLE001
                    renderer.show_warning(f"error: {e}")
                    return None
                ctx.last_plan = result.plan
                if result.run is not None:
                    record.runs.append(asdict(result.run))
                ctx.total_cost += result.cost_usd
                renderer.show_final(
                    result.final,
                    confidence=result.confidence,
                    cost_usd=result.cost_usd,
                )
                return result

            renderer.app._turn_dispatch = _dispatch_tui_turn
            _run_textual_app(renderer.app)
            try:
                conventions.run_on_clean_exit(
                    ctx,
                    history=ctx.history,
                    record=record,
                    memory_store=ctx.memory_store,
                )
            except Exception as exc:  # noqa: BLE001
                click.echo(f"conventions extraction skipped: {exc}", err=True)
            return

        while True:
            try:
                line = input(_repl_prompt())
            except (EOFError, KeyboardInterrupt):
                click.echo()
                try:
                    conventions.run_on_clean_exit(
                        ctx,
                        history=ctx.history,
                        record=record,
                        memory_store=ctx.memory_store,
                    )
                except Exception as exc:  # noqa: BLE001
                    click.echo(f"conventions extraction skipped: {exc}", err=True)
                return
            line = line.strip()
            if not line:
                continue

            # Slash commands.
            if line.startswith("/"):
                try:
                    handled = slash_registry.dispatch(ctx, line)
                except ValueError as exc:
                    click.echo(str(exc), err=True)
                    continue
                if ctx.should_exit:
                    return
                if handled:
                    cfg = get_config()
                    continue
            if line.startswith("/"):
                click.echo(f"unknown command: {line}. /help for list.", err=True)
                continue

            if _classify_intent(line) == "analyze":
                skill = skill_registry.get("analyze")
                if skill is not None:
                    skill.handler(ctx, [])
                continue

            renderer.show_user(line)
            route = _ambient_route(line)
            if route == "local":
                answer = _ambient_status_answer(ctx, auth_detail=auth_detail)
                ctx.history.add(line, role="user")
                ctx.history.add(answer, role="assistant")
                renderer.show_final(answer, confidence=1.0, cost_usd=0.0)
                continue
            try:
                if not ctx.project_index_text:
                    ctx.project_index_text = _render_project_index_text(
                        cwd, session_id=record.id
                    )
                if route == "ambient":
                    response = _run_turn_cancellable(
                        _run_ambient_provider_turn(line, ctx),
                        renderer=renderer,
                    )
                    ctx.total_cost += response.cost_usd
                    renderer.show_final(
                        response.text,
                        confidence=1.0,
                        cost_usd=response.cost_usd,
                    )
                    continue
                renderer.show_thinking("starting Voss run")
                run_turn = _resolve_run_turn(cwd)
                result = _run_turn_cancellable(
                    _run_turn_with_teardown(
                        run_turn(
                            line,
                            tools=tools,
                            cwd=cwd,
                            renderer=renderer,
                            model=get_config().default_model,
                            history=ctx.history,
                            permissions=gate,
                            provider=ctx.provider,
                            session_id=record.id,
                            cognition=bundle,
                            prior_context=ctx.prior_context,
                            voss_md_text=ctx.voss_md_text,
                            project_index_text=ctx.project_index_text,
                            **_code_recall_kwargs(run_turn, cwd, line, session_id=record.id),
                            **_pinned_memory_kwargs(run_turn, cwd, model=get_config().default_model),
                        ),
                        _multiagent_teardown,
                    ),
                    renderer=renderer,
                )
                # prior_context is one-shot: only the first turn rehydrates it.
                ctx.prior_context = None
            except Exception as e:  # noqa: BLE001
                click.echo(f"error: {e}", err=True)
                continue
            ctx.last_plan = result.plan
            if result.run is not None:
                record.runs.append(asdict(result.run))
            ctx.total_cost += result.cost_usd
            renderer.show_final(
                result.final, confidence=result.confidence, cost_usd=result.cost_usd
            )
    finally:
        # V8 (VMAG-ROOT): finalize the chat root on session exit (idempotent;
        # safe on Ctrl+C / EOF / normal / TUI close). "done" is a valid existing
        # EXIT_REASON — no new reason invented.
        try:
            finalize_node(_chat_root, exit_reason="done", final="", cwd=cwd)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"chat root finalize skipped: {exc}", err=True)
        try:
            from . import lifecycle

            try:
                asyncio.run(lifecycle.reap_jobs())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(lifecycle.reap_jobs())
                finally:
                    loop.close()
            if not keep_logs:
                shutil.rmtree(jobs_root / record.id, ignore_errors=True)
            active_session.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"job reap skipped: {exc}", err=True)


# ---------------------------------------------------------------------------
# login / logout — credential setup
# ---------------------------------------------------------------------------


@click.command("login")
def login_cmd() -> None:
    """Launch the interactive sign-in wizard.

    Walks through Claude Code OAuth, Codex OAuth, or pasting an API key
    (persisted to the OS keychain via `keyring`). Idempotent — running it
    again over an existing credential just lets the user switch paths.
    """
    from . import login_wizard

    if not login_wizard.stdin_is_interactive():
        click.echo(
            "voss login requires an interactive terminal. Set ANTHROPIC_API_KEY "
            "or OPENAI_API_KEY for non-interactive use.",
            err=True,
        )
        sys.exit(2)
    res = login_wizard.run_login_wizard(reason="voss login")
    if res is None:
        sys.exit(2)


@click.command("logout")
@click.argument("provider", type=click.Choice(["anthropic", "openai"]))
def logout_cmd(provider: str) -> None:
    """Remove a voss-stored API key from the OS keychain.

    Does NOT touch Claude Code (~/.claude/.credentials.json) or Codex
    (~/.codex/auth.json) — manage those via their own CLIs.
    """
    removed = auth_mod.delete_voss_creds(provider)  # type: ignore[arg-type]
    if removed:
        click.echo(f"voss logout: cleared keyring entry for `{provider}`")
    else:
        click.echo(
            f"voss logout: no `{provider}` entry in keyring (or backend unavailable)",
            err=True,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# doctor — diagnostics
# ---------------------------------------------------------------------------


# Mirrors diagnostics.Category values; kept literal so the click decorator
# doesn't force an eager diagnostics import. Drift-guarded by test.
_DOCTOR_CATEGORIES = ("env", "auth", "config", "state", "project")


def _render_doctor_table(results) -> None:
    """Glyph table shared by `voss doctor` and the REPL `/doctor` command."""
    from . import diagnostics as diag

    glyph = {
        diag.CheckResult.OK: ("✓", "green"),
        diag.CheckResult.WARN: ("⚠", "yellow"),
        diag.CheckResult.FAIL: ("✗", "red"),
    }
    name_width = max(len(c.name) for c in results) + 2
    for c in results:
        g, color = glyph[c.result]
        click.echo(f"  {click.style(g, fg=color)}  {c.name:<{name_width}} {c.detail}")
        if c.fix and c.result is not diag.CheckResult.OK:
            click.echo(f"     → {c.fix}")


@click.command("doctor")
@click.option(
    "--cwd",
    "cwd_str",
    default=".",
    type=click.Path(file_okay=False),
    help="Project root to check.",
)
@click.option(
    "--fix",
    "do_fix",
    is_flag=True,
    default=False,
    help="Apply machine repairs after diagnosis (one confirmation for the plan).",
)
@click.option(
    "--yes",
    "assume_yes",
    is_flag=True,
    default=False,
    help="With --fix: skip confirmation; applies safe-tier repairs only.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON (same check shape as server GET /doctor).",
)
@click.option(
    "--only",
    "only_ids",
    multiple=True,
    metavar="ID",
    help="Run only the named check id(s); repeatable.",
)
@click.option(
    "--category",
    "category_strs",
    multiple=True,
    type=click.Choice(_DOCTOR_CATEGORIES),
    help="Run only checks in the given category; repeatable.",
)
def doctor_cmd(
    cwd_str: str,
    do_fix: bool,
    assume_yes: bool,
    as_json: bool,
    only_ids: tuple[str, ...],
    category_strs: tuple[str, ...],
) -> None:
    """Diagnose harness setup. Diagnose-only by default (D-13); repairs
    run only behind the explicit --fix opt-in, gated by RepairTier.

    Former ad-hoc rows (cognition init/staleness M2-06, legacy sessions,
    third-party skill confinement M15-06) are folded into the check
    registry in `diagnostics.REGISTRY` and render in the table below.
    """
    from . import diagnostics as diag
    from . import repair as repair_mod

    if as_json and do_fix and not assume_yes:
        raise click.UsageError("--json with --fix requires --yes (non-interactive)")

    cwd = Path(cwd_str).resolve()

    ids = set(only_ids) if only_ids else None
    if ids is not None:
        valid = [s.id for s in diag.REGISTRY]
        unknown = ids - set(valid)
        if unknown:
            raise click.UsageError(
                f"unknown check id(s): {', '.join(sorted(unknown))}. "
                f"valid ids: {', '.join(valid)}"
            )
    cats = {diag.Category(c) for c in category_strs} if category_strs else None

    if ids is not None or cats is not None:
        results = diag.run_checks(cwd, ids=ids, categories=cats)
        if not results:
            raise click.UsageError("no checks matched the given filters")
    else:
        results = diag.run_all_checks(cwd)

    if not as_json:
        _render_doctor_table(results)

    outcomes: list = []
    if do_fix:
        candidates = repair_mod.repair_candidates(results)
        if as_json:
            outcomes = repair_mod.execute_repairs(candidates, cwd, assume_yes=True)
            results = repair_mod.merge_results(results, outcomes)
        elif not candidates:
            click.echo("\nno machine-repairable issues.")
        else:
            click.echo("\nplanned repairs:")
            for c in candidates:
                click.echo(f"  [{c.tier.value}] {c.name} — {c.fix or c.detail}")
            proceed = assume_yes or click.confirm(
                f"apply {len(candidates)} repair(s)?"
            )
            if proceed:
                outcomes = repair_mod.execute_repairs(
                    candidates, cwd, assume_yes=assume_yes
                )
                for o in outcomes:
                    if not o.executed:
                        click.echo(f"  -  {o.check.name}: skipped ({o.skipped_reason})")
                    elif o.verified:
                        detail = o.result.detail if o.result else ""
                        click.echo(
                            f"  {click.style('✓', fg='green')}  "
                            f"{o.check.name}: repaired ({detail})"
                        )
                    elif o.result is not None and o.result.ok:
                        state = o.recheck.result.value if o.recheck else "unverified"
                        click.echo(
                            f"  {click.style('✗', fg='red')}  "
                            f"{o.check.name}: repair ran but re-check is {state}",
                            err=True,
                        )
                    else:
                        detail = o.result.detail if o.result else ""
                        click.echo(
                            f"  {click.style('✗', fg='red')}  "
                            f"{o.check.name}: repair failed ({detail})",
                            err=True,
                        )
                results = repair_mod.merge_results(results, outcomes)

    code = diag.aggregate_exit_code(results)

    if as_json:
        payload: dict = {
            "v": 1,
            "exit_code": code,
            "checks": [diag.to_dict(c) for c in results],
        }
        if do_fix:
            payload["repairs"] = [
                {
                    "id": o.check.id,
                    "name": o.check.name,
                    "executed": o.executed,
                    "skipped_reason": o.skipped_reason,
                    "ok": o.result.ok if o.result else None,
                    "detail": o.result.detail if o.result else "",
                    "verified": o.verified,
                    "recheck_status": o.recheck.result.name if o.recheck else "",
                }
                for o in outcomes
            ]
        click.echo(json.dumps(payload, indent=2))
        sys.exit(code)

    warns = [c for c in results if c.result is diag.CheckResult.WARN]
    fails = [c for c in results if c.result is diag.CheckResult.FAIL]
    if code != 0:
        click.echo("\nfailed checks. fix above and re-run.", err=True)
    elif warns and not fails:
        # D-14: WARN-only runs exit 0 but surface a one-line stderr summary
        # so CI / shell prompts can notice informational misses.
        names = ", ".join(c.name for c in warns)
        plural = "warning" if len(warns) == 1 else "warnings"
        click.echo(f"doctor: {len(warns)} {plural} ({names})", err=True)
    sys.exit(code)


def _print_slash_help(registry: SlashRegistry | None = None) -> None:
    """Render slash help grouped by semantic category (D-04 / SC#3).

    Named groups are rendered first in fixed order; any registered non-hidden
    slash not assigned to a named group falls under a final "Other" bucket so
    nothing is ever silently dropped. Per-group width alignment mirrors the
    style in SlashRegistry.help_lines (slash.py:45-52).
    """
    registry = registry or _build_slash_registry()

    # Explicit buckets finalized against live _build_slash_registry() contents.
    # Order of groups and members within groups is semantic (not alpha).
    named_groups: list[tuple[str, list[str]]] = [
        ("Editing", ["/diff", "/apply", "/discard"]),
        ("Session", ["/resume", "/budget", "/cost", "/clear", "/save-session"]),
        ("Insight", ["/why", "/probable", "/btrace", "/vdiff", "/tools", "/analyze"]),
        ("Control", ["/help", "/exit", "/mode", "/model"]),
    ]

    placed: set[str] = set()
    for header, names in named_groups:
        members: list[SlashCommand] = []
        for name in names:
            cmd = registry.lookup(name)
            if cmd and not cmd.hidden:
                members.append(cmd)
                placed.add(name)
        if not members:
            continue
        click.echo(header)
        width = max(len(c.name) for c in members)
        for c in members:
            click.echo(f"  {c.name:<{width}}  {c.help}")
        click.echo()

    # Long-tail Other bucket (D-05 / M9-03 parity): everything not yet placed.
    other_members: list[SlashCommand] = []
    for name in registry.ids(include_hidden=False):
        if name not in placed:
            cmd = registry.lookup(name)
            if cmd and not cmd.hidden:
                other_members.append(cmd)
    if other_members:
        click.echo("Other")
        width = max(len(c.name) for c in other_members)
        for c in other_members:
            click.echo(f"  {c.name:<{width}}  {c.help}")


@click.command("sessions")
@click.option(
    "--all",
    "--global",
    "include_legacy",
    is_flag=True,
    help="Include legacy sessions from ~/.local/state/voss/sessions/.",
)
def sessions_cmd(include_legacy: bool) -> None:
    """List saved agent sessions (cwd-scoped; --all merges legacy XDG dir)."""
    cwd = Path.cwd()
    records = session_store.list_sessions(cwd=cwd, include_legacy=include_legacy)
    if not records:
        click.echo("(no sessions)")
        return
    for r in records:
        tag = "[legacy] " if getattr(r, "_legacy", False) else ""
        click.echo(
            f"  {tag}{r.id[:8]}  {r.updated_at}  {r.model:<28}  {r.first_task()}"
        )


def _latest_root_id(sessions_dir: Path) -> str | None:
    """Name of the most-recently-modified session root dir, or None."""
    try:
        roots = [d for d in sessions_dir.iterdir() if d.is_dir()]
    except OSError:
        return None
    if not roots:
        return None
    return max(roots, key=lambda d: d.stat().st_mtime).name


def _render_review_card(node_id: str, data: dict) -> None:
    """Print one card's A verification + B verdict + final outcome."""
    click.echo(f"• {node_id}  [{data.get('final_outcome', '?')}]")
    a = data.get("a_verification")
    if a:
        click.echo(
            f"    A: {a.get('result', '?')}  "
            f"({a.get('test_path_or_rubric') or 'no rubric'})  {a.get('notes', '')}"
        )
    else:
        click.echo("    A: (none)")
    b = data.get("b_verdict")
    if b:
        click.echo(
            f"    B: {b.get('verdict', '?')}  conf={b.get('conf', '?')}  "
            f"tier={b.get('tier', '?')}  domain={b.get('domain_inferred', '?')}"
        )
        if b.get("notes"):
            click.echo(f"       {b['notes']}")
        if b.get("evidence_refs"):
            click.echo(f"       evidence: {', '.join(b['evidence_refs'])}")
    else:
        click.echo("    B: (none)")


@click.command("review")
@click.argument("run_id", required=False)
def review_cmd(run_id: str | None) -> None:
    """Show per-card A + B review for a run (latest if no run_id).

    Read-only from the `.review.json` sidecars written by the board; no live
    Board / SessionTreeManager / provider is constructed (VREV-10, D-11).
    """
    cwd = Path.cwd()
    sessions_dir = cwd / ".voss" / "sessions"
    if run_id is None:
        run_id = _latest_root_id(sessions_dir)
        if run_id is None:
            click.echo("(no review runs found)", err=True)
            raise SystemExit(1)
    sidecar_dir = sessions_dir / run_id
    if not sidecar_dir.is_dir():
        click.echo(f"unknown run_id: {run_id}", err=True)
        raise SystemExit(1)
    sidecars = sorted(sidecar_dir.glob("*.review.json"))
    if not sidecars:
        click.echo("(no review artifacts for this run)")
        return
    click.echo(f"review {run_id}:")
    for path in sidecars:
        node_id = path.name[: -len(".review.json")]
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            click.echo(f"  ! {node_id}: unreadable sidecar ({e})", err=True)
            continue
        _render_review_card(node_id, data)


@click.command("audit")
@click.argument("run_id", required=False)
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option(
    "--format", "fmt",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
)
@click.option("--output", "output_path", default=None, type=click.Path())
@click.option(
    "--approve",
    "approve",
    is_flag=True,
    help="Approve the audited run; refused if killed/misroute risks are unacknowledged.",
)
def audit_cmd(
    run_id: str | None,
    cwd_str: str,
    fmt: str,
    output_path: str | None,
    approve: bool,
) -> None:
    """Render a complete read-only audit for a run (latest if no run_id).

    Read-only: assembles the audit from persisted session data; no live Board /
    SessionTreeManager / provider is constructed (VAUD-01, mirrors review_cmd).
    """
    cwd = Path(cwd_str).resolve()
    sessions_dir = cwd / ".voss" / "sessions"

    if run_id is not None:
        # T-V9-04-01: reject traversal BEFORE any FS read.
        if "/" in run_id or "\\" in run_id or ".." in run_id:
            click.echo(f"<error: invalid run_id {run_id!r}>", err=True)
            raise SystemExit(1)
        candidate = (sessions_dir / run_id).resolve()
        if candidate.parent != sessions_dir.resolve():
            click.echo(f"<error: invalid run_id {run_id!r}>", err=True)
            raise SystemExit(1)
        if not candidate.is_dir():
            click.echo(f"unknown run_id: {run_id}", err=True)
            raise SystemExit(1)
    else:
        run_id = _latest_root_id(sessions_dir)
        if run_id is None:
            click.echo("(no runs found)", err=True)
            raise SystemExit(1)

    from voss.harness.audit import (
        build_audit_report,
        render_json,
        render_markdown,
        render_text,
    )

    calibration = None
    try:
        from voss.harness.audit.calibration import compute_calibration

        # Fixed seed → deterministic spot-audit selection (VAUD-08: audit output
        # must be reproducible from persisted data).
        calibration = compute_calibration(sessions_dir, seed=0)
    except Exception:
        calibration = None  # calibration optional; build tolerates None

    report = build_audit_report(cwd, run_id=run_id, calibration=calibration)

    # VAUD-SIGNOFF readback: approve is refused when killed/misroute risks exist
    # and the .signoff-ack.json governance record is absent.
    if approve:
        risks = bool(report.snapshot.kills) or any(
            r.confidence_hint is not None and r.confidence_hint < 0.7
            for r in report.snapshot.routings
        )
        if risks and report.signoff_ack is None:
            click.echo(
                "approve refused: killed-card/misroute risks unacknowledged — "
                "run `voss team run` sign-off to acknowledge.",
                err=True,
            )
            raise SystemExit(1)
        click.echo(f"approve: permitted for {report.run_id}")

    renderer = {
        "text": render_text,
        "json": render_json,
        "markdown": render_markdown,
    }[fmt]
    rendered = renderer(report)

    if output_path is not None:
        Path(output_path).write_text(rendered)
    else:
        click.echo(rendered)
    raise click.exceptions.Exit(0)


_JOB_META_FIELDS = (
    "handle",
    "pid",
    "started_at",
    "cmd",
    "log_path",
    "status",
    "exit_code",
    "runtime_ms",
)


def _read_job_meta(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except PermissionError:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not all(k in data for k in _JOB_META_FIELDS):
        return None
    return {k: data[k] for k in _JOB_META_FIELDS}


def _newest_jobs_dir(cache: Path) -> Path | None:
    newest: tuple[float, Path] | None = None
    try:
        entries = list(cache.iterdir())
    except OSError:
        return None
    for path in entries:
        try:
            if not path.is_dir():
                continue
            if not _has_job_sidecars(path):
                continue
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, path)
    return newest[1] if newest is not None else None


def _has_job_sidecars(path: Path) -> bool:
    try:
        return any(path.glob("*.meta.json"))
    except OSError:
        return False


def _active_jobs_session(cache: Path) -> Path | None:
    active = cache / ".active-session"
    try:
        sid = active.read_text().strip()
    except OSError:
        sid = ""
    if sid:
        try:
            session_dir = jail_path(cache, sid)
        except Exception:  # noqa: BLE001
            session_dir = None
        if session_dir is not None and session_dir.is_dir() and _has_job_sidecars(session_dir):
            return session_dir

    return _newest_jobs_dir(cache)


def _runtime_label(runtime_ms: object) -> str:
    try:
        ms = max(0, int(runtime_ms))
    except (TypeError, ValueError):
        ms = 0
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


def _display_status(rec: dict) -> str:
    status = str(rec.get("status", ""))
    if status != "running":
        return status
    try:
        live = psutil.pid_exists(int(rec["pid"]))
    except (TypeError, ValueError, psutil.Error):
        live = False
    return "running" if live else "stale"


@click.command("jobs")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option("--json", "json_mode", is_flag=True, help="One JSON record per line.")
def jobs_cmd(cwd_str: str, json_mode: bool) -> None:
    """List background jobs for the current session."""
    cwd = Path(cwd_str).resolve()
    cache = jail_path(cwd, ".voss-cache") / "jobs"
    session_dir = _active_jobs_session(cache)
    if session_dir is None:
        click.echo("(no background jobs)")
        return

    records: list[dict] = []
    try:
        meta_paths = sorted(session_dir.glob("*.meta.json"))
    except OSError:
        meta_paths = []
    for path in meta_paths:
        rec = _read_job_meta(path)
        if rec is not None:
            records.append(rec)

    if not records:
        click.echo("(no background jobs)")
        return

    if json_mode:
        for rec in records:
            rendered = dict(rec)
            rendered["status"] = _display_status(rec)
            click.echo(json.dumps(rendered))
        return

    rows = [
        (
            str(rec["handle"]),
            str(rec["pid"]),
            _display_status(rec),
            _runtime_label(rec["runtime_ms"]),
            str(rec["cmd"]),
        )
        for rec in records
    ]
    headers = ("HANDLE", "PID", "STATUS", "RUNTIME", "CMD")
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers) - 1)
    ]
    click.echo(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  "
        f"{headers[2]:<{widths[2]}}  {headers[3]:<{widths[3]}}  {headers[4]}"
    )
    terminal_cols = shutil.get_terminal_size((80, 24)).columns
    max_cmd = max(10, terminal_cols - sum(widths) - 10)
    for handle, pid, status, runtime, cmd in rows:
        if len(cmd) > max_cmd:
            cmd = cmd[: max_cmd - 1] + "…"
        click.echo(
            f"{handle:<{widths[0]}}  {pid:<{widths[1]}}  "
            f"{status:<{widths[2]}}  {runtime:<{widths[3]}}  {cmd}"
        )


async def _run_watch_loop(
    *,
    command: str,
    argv: list[str],
    cwd: Path,
    globs: list[str],
    debounce_ms: int,
    session_id: str,
    max_reruns: int,
    idle_timeout_s: float | None,
) -> None:
    """Watch loop: spawn the command, re-spawn it on debounced file change.

    Stops after `max_reruns` re-runs (0 = unbounded), after `idle_timeout_s`
    with no events (None = never), or on cancel/Ctrl-C. Always reaps the
    watcher and child job on exit. Kept free of test-environment sniffing so
    the same path runs in tests and production; tests bound it via the args.
    """
    import re
    import signal as signal_mod

    from . import lifecycle

    watch_handle = await lifecycle.register_watcher(
        globs, cwd, session_id=session_id, debounce_ms=debounce_ms
    )
    click.echo(watch_handle)

    job_handle = await lifecycle.register_job(
        cmd=command, argv=argv, cwd=cwd, session_id=session_id
    )

    rec = lifecycle._find_watcher(watch_handle, session_id=session_id)
    if rec is None:
        await lifecycle.reap_watchers()
        await lifecycle.reap_jobs()
        return

    cursor = 0
    reruns = 0
    last_activity = time.monotonic()
    try:
        while True:
            await asyncio.sleep(0.05)
            events_str = lifecycle._read_log_cursor(
                Path(rec.log_path), cursor, status=rec.status
            )
            match = re.match(r"\[cursor (\d+)\]", events_str)
            if match:
                new_cursor = int(match.group(1))
                if new_cursor > cursor:
                    cursor = new_cursor
                    last_activity = time.monotonic()
                    lifecycle.signal_job(
                        job_handle, signal_mod.SIGTERM, session_id=session_id
                    )
                    job_handle = await lifecycle.register_job(
                        cmd=command, argv=argv, cwd=cwd, session_id=session_id
                    )
                    reruns += 1
                    if max_reruns > 0 and reruns >= max_reruns:
                        break
            if (
                idle_timeout_s is not None
                and (time.monotonic() - last_activity) > idle_timeout_s
            ):
                break
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await lifecycle.reap_watchers()
        await lifecycle.reap_jobs()


@click.command("watch")
@click.argument("command")
@click.option("--glob", "globs", multiple=True, default=("**/*",))
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option("--daemon", "daemon_mode", is_flag=True)
@click.option("--debounce-ms", default=200, type=int)
@click.option("--_is-worker", "is_worker", is_flag=True)
@click.option("--_max-reruns", "max_reruns", default=0, type=int, hidden=True)
@click.option(
    "--_idle-timeout-ms", "idle_timeout_ms", default=0, type=int, hidden=True
)
def watch_cmd(
    command: str,
    globs: tuple[str, ...],
    cwd_str: str,
    daemon_mode: bool,
    debounce_ms: int,
    is_worker: bool,
    max_reruns: int,
    idle_timeout_ms: int,
) -> None:
    """Watch files and run a command on change."""
    cwd = Path(cwd_str).resolve()

    from .sandbox import shell_allowed, split_command, SandboxError

    ok, reason = shell_allowed(command)

    if not ok:
        click.echo(f"<denied: {reason}>")
        sys.exit(1)

    try:
        argv = split_command(command)
    except SandboxError as e:
        click.echo(f"<denied: {e}>")
        sys.exit(1)

    import shutil
    if argv and argv[0] in ("python", "python3") and not shutil.which(argv[0]):
        argv[0] = sys.executable

    if daemon_mode and not is_worker:
        from .watch.daemon import spawn_detached_worker

        try:
            watch_idx = sys.argv.index("watch")
            original_args = sys.argv[watch_idx + 1:]
        except ValueError:
            original_args = []
        pid = spawn_detached_worker(original_args)
        time.sleep(0.2)
        try:
            os.kill(pid, 0)
        except OSError:
            click.echo(f"<error: daemon worker {pid} exited immediately>")
            sys.exit(1)
        click.echo(f"watch (daemonized PID: {pid})")
        return

    session_id = "_nosession"
    idle_timeout_s = (idle_timeout_ms / 1000) if idle_timeout_ms > 0 else None

    asyncio.run(
        _run_watch_loop(
            command=command,
            argv=argv,
            cwd=cwd,
            globs=list(globs),
            debounce_ms=debounce_ms,
            session_id=session_id,
            max_reruns=max_reruns,
            idle_timeout_s=idle_timeout_s,
        )
    )


@click.group("inspect")
def inspect_group() -> None:
    """Inspect persisted run records."""


@inspect_group.command("probable")
@click.argument("session_id_or_name")
@click.option("--decision", "decision_index", type=int, default=None)
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def inspect_probable_cmd(
    session_id_or_name: str, decision_index: int | None, cwd_str: str
) -> None:
    """Show recorded probable decision sequence."""
    try:
        text = _render_probable_inspect(
            Path(cwd_str).resolve(), session_id_or_name, decision_index
        )
    except (FileNotFoundError, ValueError, IndexError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(text)


@inspect_group.command("budget")
@click.argument("session_id_or_name")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def inspect_budget_cmd(session_id_or_name: str, cwd_str: str) -> None:
    """Show recorded budget timeline."""
    try:
        text = _render_budget_inspect(Path(cwd_str).resolve(), session_id_or_name)
    except (FileNotFoundError, ValueError, IndexError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(text)


@click.command("vdiff")
@click.argument("source", metavar="FILE.voss")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def vdiff_cmd(source: str, cwd_str: str) -> None:
    """Show source vs generated Python for a .voss file."""
    try:
        text = _render_voss_py_diff(Path(cwd_str).resolve(), source)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(text)


@click.command("resume")
@click.argument("session_id_or_name")
@click.option(
    "--mode",
    type=click.Choice(["plan", "edit", "auto"]),
    default="edit",
    help="Permission tier.",
)
@click.option("--json", "json_mode", is_flag=True, help="Emit NDJSON events on stdout.")
@click.option("--plain", "plain", is_flag=True, help="Use line-streamed renderer; bypass TUI.")
@click.option(
    "--no-unicode",
    "no_unicode",
    is_flag=True,
    help="Use ASCII fallback for TUI glyphs (sets VOSS_NO_UNICODE=1).",
)
@click.option(
    "--auth",
    "auth_pref",
    type=click.Choice(AUTH_CHOICES),
    default="auto",
    help="Credential source.",
)
def resume_cmd(
    session_id_or_name: str,
    mode: str,
    json_mode: bool,
    plain: bool,
    no_unicode: bool,
    auth_pref: str,
) -> None:
    """Resume a saved session by id-prefix or name."""
    _apply_no_unicode_env(no_unicode)
    try:
        record, history = session_store.load(session_id_or_name, cwd=Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"resume failed: {e}", err=True)
        sys.exit(1)
    cwd = Path(record.cwd)
    if record.model:
        configure(default_model=record.model)
    _warn_instructions_drift(record, cwd)
    res, provider = _resolve_auth_or_die(auth_pref, announce=False)
    prior = record.runs[-1] if record.runs else None
    _run_repl(
        cwd=cwd,
        json_mode=json_mode,
        plain=plain,
        mode=mode,
        history=history,
        record=record,
        provider=provider,
        auth_detail=f"{res.source} — {res.detail}",
        prior_context=prior,
    )


# ---------------------------------------------------------------------------
# tools — registry table
# ---------------------------------------------------------------------------


@click.command("tools")
@click.option(
    "--cwd",
    "cwd_str",
    default=".",
    type=click.Path(file_okay=False),
    help="Project root.",
)
def tools_cmd(cwd_str: str) -> None:
    """List registered harness tools."""
    cwd = Path(cwd_str).resolve()
    # T5: no session_id — tools_cmd never invokes tools (deliberate _nosession).
    tools = make_toolset(cwd)
    name_w = max(len(n) for n in tools)
    click.echo(f"  {'name':<{name_w}}  {'mutating':<8}  description")
    click.echo(f"  {'-' * name_w}  {'-' * 8}  {'-' * 40}")
    for name in sorted(tools):
        entry = tools[name]
        mut = "yes" if entry.is_mutating else "no"
        desc = entry.description
        if len(desc) > 60:
            desc = desc[:59] + "…"
        click.echo(f"  {name:<{name_w}}  {mut:<8}  {desc}")


def _extension_context(
    *,
    cwd: Path,
    provider: ModelProvider | None = None,
    renderer=None,
    gate: PermissionGate | None = None,
) -> SimpleNamespace:
    skill_registry = default_skill_registry()
    subagent_registry = default_subagent_registry()
    slash_registry = _build_slash_registry()
    renderer = renderer or make_renderer(json_mode=False)
    # T5: deliberate _nosession — not a live session loop.
    tools = make_toolset(cwd, renderer=renderer, net=_get_net_session())
    gate = gate or PermissionGate(mode="edit", store=PermissionStore.load(cwd))
    ctx = SimpleNamespace(
        cwd=cwd,
        renderer=renderer,
        tools=tools,
        gate=gate,
        history=EpisodicMemory(capacity=40),
        record=session_store.SessionRecord.new(cwd=cwd, model=get_config().default_model),
        provider=provider,
        skill_registry=skill_registry,
        subagent_registry=subagent_registry,
        slash_registry=slash_registry,
        cognition=cognition_mod.load(cwd),
        prior_context=None,
        last_plan=None,
        total_cost=0.0,
        project_index_text=_render_project_index_text(cwd),
    )
    if provider is not None:
        attach_subagent_tool(
            tools,
            registry=subagent_registry,
            cwd=cwd,
            renderer=renderer,
            provider=provider,
            model=lambda: get_config().default_model,
            gate=gate,
            cognition=ctx.cognition,
        )
    attach_memory_tools(
        tools,
        store=MemoryStore(cwd).bind(session_id=ctx.record.id),
        session_id=ctx.record.id,
    )
    return ctx


@click.command("plugins")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def plugins_cmd(cwd_str: str) -> None:
    """List plugin manifests."""
    ctx = _extension_context(cwd=Path(cwd_str).resolve())
    _print_plugins(ctx)  # type: ignore[arg-type]


@click.group("plugin")
def plugin_group() -> None:
    """Manage plugin manifest enablement."""


@plugin_group.command("enable")
@click.argument("plugin_id")
def plugin_enable_cmd(plugin_id: str) -> None:
    path = set_plugin_enabled(plugin_id, True)
    click.echo(f"plugin {plugin_id} enabled: {path}")


@plugin_group.command("disable")
@click.argument("plugin_id")
def plugin_disable_cmd(plugin_id: str) -> None:
    path = set_plugin_enabled(plugin_id, False)
    click.echo(f"plugin {plugin_id} disabled: {path}")


@click.command("skills")
def skills_cmd() -> None:
    """List registered skills."""
    ctx = _extension_context(cwd=Path.cwd())
    _print_skills(ctx)  # type: ignore[arg-type]


@click.group("skill")
def skill_group() -> None:
    """Run registered skills."""


@skill_group.command("run")
@click.argument("skill_id")
@click.argument("args", nargs=-1)
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option("--model", default=None)
@click.option("--auth", "auth_pref", type=click.Choice(AUTH_CHOICES), default="auto")
def skill_run_cmd(
    skill_id: str,
    args: tuple[str, ...],
    cwd_str: str,
    model: str | None,
    auth_pref: str,
) -> None:
    """Run a registered skill."""
    cwd = Path(cwd_str).resolve()
    _resolve_default_model(model)
    _res, provider = _resolve_auth_or_die(auth_pref)
    ctx = _extension_context(cwd=cwd, provider=provider)
    entry = ctx.skill_registry.get(skill_id)
    if entry is None:
        raise click.ClickException(f"unknown skill: {skill_id}")
    entry.handler(ctx, list(args))


@skill_group.command("add")
@click.argument("source")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option("--allow-tofu", is_flag=True, default=False, help="TOFU-pin unknown keys on first install")
def skill_add_cmd(source: str, cwd_str: str, allow_tofu: bool) -> None:
    """Install a skill bundle from a local path, git URL, or GitHub shorthand."""
    from .skill.install import SkillTrustError, install_bundle

    cwd = Path(cwd_str).resolve()
    try:
        skill_id = install_bundle(source, cwd=cwd, allow_tofu=allow_tofu)
        click.echo(f"skill installed: {skill_id}")
    except SkillTrustError as e:
        click.echo(f"error: {e}", err=True)
        raise click.exceptions.Exit(code=1) from None


@skill_group.command("list")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def skill_list_cmd(cwd_str: str) -> None:
    """List installed third-party skills."""
    cwd = Path(cwd_str).resolve()
    plugins = load_plugins(cwd)
    found = False
    for p in plugins:
        if p.skill_id and p.voss_entry:
            found = True
            status = "enabled" if p.enabled else "disabled"
            click.echo(f"  {p.skill_id:<24} {status:<10} tools={p.scope_tools} fs={p.scope_fs} net={p.scope_net}")
    if found:
        click.echo("")
        click.echo("  note: scope enforcement applies to harness tool calls only (OS-level sandbox deferred)")
    else:
        click.echo("  (no third-party skills installed)")


@skill_group.command("remove")
@click.argument("skill_id")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def skill_remove_cmd(skill_id: str, cwd_str: str) -> None:
    """Remove an installed skill."""
    from .skill.install import remove_bundle

    cwd = Path(cwd_str).resolve()
    remove_bundle(skill_id, cwd=cwd)
    click.echo(f"skill removed: {skill_id}")


@skill_group.command("update")
@click.argument("skill_id")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def skill_update_cmd(skill_id: str, cwd_str: str) -> None:
    """Re-fetch and re-verify an installed skill (prior version intact on failure)."""
    from .skill.install import SkillTrustError, update_bundle

    cwd = Path(cwd_str).resolve()
    try:
        update_bundle(skill_id, cwd=cwd)
        click.echo(f"skill updated: {skill_id}")
    except SkillTrustError as e:
        click.echo(f"error: {e} (prior version intact)", err=True)
        raise click.exceptions.Exit(code=1) from None


@skill_group.command("trust")
@click.argument("pub_key_b64")
@click.option("--identity", required=True, help="Author identity (e.g. email)")
def skill_trust_cmd(pub_key_b64: str, identity: str) -> None:
    """Trust a signing key by pinning it to an identity."""
    from .trust import key_fingerprint, pin_key

    fp = key_fingerprint(pub_key_b64)
    click.echo(f"key fingerprint: {fp}")
    click.confirm(f"Trust key for identity '{identity}'?", abort=True)
    pin_key(identity, pub_key_b64)
    click.echo(f"key pinned for {identity}")


@click.command("agents")
def agents_cmd() -> None:
    """List registered subagents."""
    ctx = _extension_context(cwd=Path.cwd())
    _print_agents(ctx)  # type: ignore[arg-type]


@click.group("agent")
def agent_group() -> None:
    """Run registered subagents."""


@agent_group.command("spawn")
@click.argument("agent_id")
@click.argument("task", nargs=-1, required=True)
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option("--model", default=None)
@click.option("--auth", "auth_pref", type=click.Choice(AUTH_CHOICES), default="auto")
@click.option("--mode", type=click.Choice(["plan", "edit", "auto"]), default="edit")
def agent_spawn_cmd(
    agent_id: str,
    task: tuple[str, ...],
    cwd_str: str,
    model: str | None,
    auth_pref: str,
    mode: str,
) -> None:
    """Spawn a registered subagent for one task."""
    cwd = Path(cwd_str).resolve()
    _resolve_default_model(model)
    _res, provider = _resolve_auth_or_die(auth_pref)
    _emit_harness_boot_telemetry(cwd, get_config().default_model)
    renderer = make_renderer(json_mode=False)
    gate = PermissionGate(mode=mode, store=PermissionStore.load(cwd), auto_yes=True)  # type: ignore[arg-type]
    registry = default_subagent_registry()
    result = asyncio.run(
        run_subagent(
            agent_id=agent_id,
            task=" ".join(task),
            registry=registry,
            cwd=cwd,
            renderer=renderer,
            provider=provider,
            model=get_config().default_model,
            gate=gate,
            cognition=cognition_mod.load(cwd),
        )
    )
    click.echo(result)


# ---------------------------------------------------------------------------
# config — open/show ~/.config/voss/config.toml
# ---------------------------------------------------------------------------


def _config_toml_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "voss" / "config.toml"


@click.command("config")
@click.option(
    "--show",
    is_flag=True,
    help="Print config to stdout instead of opening editor.",
)
@click.option(
    "--config-path",
    "config_path_override",
    default=None,
    type=click.Path(path_type=Path),
    help="Override config.toml location (testing).",
)
def config_cmd(show: bool, config_path_override: Path | None) -> None:
    """Open or show ~/.config/voss/config.toml."""
    path = config_path_override if config_path_override else _config_toml_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[harness]\n")
        path.chmod(0o600)

    if show:
        text = path.read_text()
        if text.strip():
            click.echo(text, nl=False)
        else:
            click.echo("(empty)")
        return

    editor = os.environ.get("EDITOR", "vi")
    try:
        subprocess.run([editor, str(path)], check=False)
    except OSError as e:
        click.echo(f"failed to launch editor {editor!r}: {e}", err=True)
        sys.exit(1)


@click.command("eval")
@click.option("--suite", default="golden", show_default=True, help="Evaluation suite name.")
@click.option("--stub", is_flag=True, help="Use deterministic stub provider.")
@click.option("--live", is_flag=True, help="Mark run as live provider evaluation.")
@click.option("-k", "k", default=1, show_default=True, type=int, help="Runs per task.")
@click.option(
    "--out",
    "out_path",
    default=None,
    type=click.Path(path_type=Path, file_okay=False),
    help="Output directory.",
)
@click.option("--judge-model", default=None, help="Override judge model.")
@click.option("--task", default=None, help="Run a single task id.")
@click.option(
    "--auth",
    "auth_pref",
    type=click.Choice(AUTH_CHOICES),
    default="auto",
    show_default=True,
    help="Credential source.",
)
@click.option("--max-turns", "max_turns", default=None, type=int, help="Turn cap per task (overrides config default).")
@click.option(
    "--require-all-toolchains",
    "require_all_toolchains",
    is_flag=True,
    default=False,
    help="Fail run if python3/cargo/node is absent (strict mode).",
)
def eval_cmd(
    suite: str,
    stub: bool,
    live: bool,
    k: int,
    out_path: Path,
    judge_model: str | None,
    task: str | None,
    auth_pref: str,
    max_turns: int | None,
    require_all_toolchains: bool,
) -> None:
    """Run the golden evaluation suite."""
    if os.environ.get("VOSS_DEV") != "1":
        click.echo("voss eval: internal tool — set VOSS_DEV=1 to run", err=True)
        raise click.exceptions.Exit(code=1)

    from voss.eval.runner import run_suite

    run_suite(
        suite=suite,
        stub=stub,
        live=live,
        k=k,
        out=out_path,
        judge_model=judge_model,
        task=task,
        auth_pref=auth_pref,
        max_turns=max_turns,
        require_all_toolchains=require_all_toolchains,
    )


def _parse_arg_kvs(args_kvs: tuple[str, ...]) -> dict[str, object]:
    """Parse repeatable --arg key=value pairs for direct MCP calls."""
    import json as json_lib

    args_dict: dict[str, object] = {}
    for kv in args_kvs:
        if "=" not in kv:
            raise click.ClickException(
                f"invalid --arg {kv!r}: expected key=value"
            )
        key, raw_val = kv.split("=", 1)
        try:
            args_dict[key] = json_lib.loads(raw_val)
        except (json_lib.JSONDecodeError, ValueError):
            args_dict[key] = raw_val
    return args_dict


@click.group("mcp")
def mcp_group() -> None:
    """Inspect and debug MCP server connections."""


@mcp_group.command("list")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON.")
def mcp_list_cmd(cwd_str: str, json_mode: bool) -> None:
    """List configured MCP servers and their advertised tools."""
    import json as json_lib

    from voss.harness.mcp import McpClient, McpConfigError, load_mcp_config

    cwd = Path(cwd_str).resolve()
    try:
        config = load_mcp_config(cwd)
    except McpConfigError as e:
        click.echo(f"<error: mcp config: {e}>", err=True)
        raise click.exceptions.Exit(1) from e

    if config is None or not config.servers:
        if json_mode:
            click.echo(json_lib.dumps({"servers": []}))
        else:
            click.echo("<no MCP servers configured>")
        return

    client = McpClient(config)
    client.set_cwd(cwd)

    async def _populate() -> None:
        try:
            for name in config.servers:
                try:
                    await client.ensure_launched(name)
                except Exception as ex:  # noqa: BLE001
                    click.echo(f"<warning: {name} launch failed: {ex}>", err=True)
        finally:
            await client.aclose()

    asyncio.run(_populate())
    servers_payload = []
    for name, server in config.servers.items():
        tools = client._tools_cache.get(name, [])
        servers_payload.append(
            {
                "name": name,
                "command": server.command + server.args,
                "tools": [tool["name"] for tool in tools],
            }
        )

    if json_mode:
        click.echo(json_lib.dumps({"servers": servers_payload}, indent=2))
    else:
        for server_payload in servers_payload:
            click.echo(f"{server_payload['name']}:")
            click.echo(f"  command: {' '.join(server_payload['command'])}")
            tools = server_payload["tools"]
            click.echo(
                f"  tools: {', '.join(tools) if tools else '<none discovered>'}"
            )
            click.echo("")


@mcp_group.command("call")
@click.argument("server")
@click.argument("tool_name")
@click.option(
    "--arg",
    "args_kvs",
    multiple=True,
    help=(
        "key=value argument (repeatable). Values parsed as JSON when JSON-shaped; "
        "raw string fallback."
    ),
)
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def mcp_call_cmd(
    server: str,
    tool_name: str,
    args_kvs: tuple[str, ...],
    cwd_str: str,
) -> None:
    """Call an MCP tool directly. Bypasses PermissionGate (developer tool)."""
    from voss.harness.mcp import McpClient, McpConfigError, load_mcp_config

    cwd = Path(cwd_str).resolve()
    try:
        config = load_mcp_config(cwd)
    except McpConfigError as e:
        click.echo(f"<error: mcp config: {e}>", err=True)
        raise click.exceptions.Exit(1) from e

    if config is None or server not in config.servers:
        click.echo(f"<error: unknown server: {server!r}>", err=True)
        raise click.exceptions.Exit(1)

    try:
        args_dict = _parse_arg_kvs(args_kvs)
    except click.ClickException as e:
        click.echo(f"<error: {e.message}>", err=True)
        raise click.exceptions.Exit(1) from e

    client = McpClient(config)
    client.set_cwd(cwd)

    async def _invoke() -> dict[str, object]:
        try:
            return await client.call_tool(server, tool_name, args_dict)
        except Exception as ex:  # noqa: BLE001
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"<error: mcp transport: {ex}>",
                    }
                ],
                "__transport_error": True,
            }
        finally:
            await client.aclose()

    result = asyncio.run(_invoke())
    if result.get("__transport_error"):
        content = result["content"]
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                click.echo(first.get("text", ""), err=True)
        raise click.exceptions.Exit(1)

    transport_error = False
    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                if text.startswith("<error: mcp transport:"):
                    transport_error = True
                click.echo(text)

    if result.get("isError"):
        if transport_error:
            raise click.exceptions.Exit(1)
        raise click.exceptions.Exit(2)


class _NullRenderer:
    """Renderer that emits nothing.

    The MCP server's stdout is the JSON-RPC wire; PlainRenderer writes
    show_final/stream_delta/finalize_stream to stdout and would corrupt the
    frame stream (Threat T-M12-04-02). Any renderer method a skill calls is a
    no-op here.
    """

    def __getattr__(self, _name: str):
        return lambda *a, **k: None


@mcp_group.command("serve")
@click.option(
    "--mode",
    type=click.Choice(["plan", "edit", "auto"], case_sensitive=False),
    required=True,
    help=(
        "Permission mode for incoming MCP calls. REQUIRED — no default. "
        "plan denies all mutating tools; edit allows fs writes but denies "
        "shell; auto allows everything."
    ),
)
@click.option(
    "--cwd",
    "cwd_str",
    default=".",
    type=click.Path(file_okay=False),
    help="Project root the server operates against. Default: current dir.",
)
def mcp_serve_cmd(mode: str, cwd_str: str) -> None:
    """Run the Voss MCP server over stdio.

    Skills executed by this server use the SERVER's configured LLM provider
    for cost. The calling MCP host does NOT see the LLM cost.
    """
    import types

    from voss.harness.mcp.config import (
        McpConfigError,
        McpServerExposureConfig,
        load_mcp_config,
    )
    from voss.harness.mcp.server import McpServer
    from voss.harness.mcp.server_skills import make_skill_dispatch
    from voss.harness.mcp.server_tools import (
        build_tool_descriptors,
        build_tool_dispatch,
    )
    from voss.harness.permissions import PermissionGate
    from voss.harness.skill_registry import default_skill_registry
    from voss.harness.tools import make_toolset

    cwd = Path(cwd_str).resolve()
    try:
        cfg = load_mcp_config(cwd)
    except McpConfigError as e:
        click.echo(f"<error: mcp config: {e}>", err=True)
        raise click.exceptions.Exit(1) from e
    server_cfg = cfg.server if cfg is not None else None
    if server_cfg is None:
        server_cfg = McpServerExposureConfig()

    tools = make_toolset(cwd)
    reg = default_skill_registry()
    try:
        descriptors = build_tool_descriptors(tools, reg, server_cfg)
    except McpConfigError as e:
        click.echo(f"<error: mcp config: {e}>", err=True)
        raise click.exceptions.Exit(1) from e

    gate = PermissionGate(mode=mode, auto_yes=True)
    record = types.SimpleNamespace(model="mcp-server", id="mcp-serve")
    renderer = _NullRenderer()  # JSON-RPC stdout purity (T-M12-04-02)
    skill_dispatch = make_skill_dispatch(
        cwd=cwd,
        provider=None,
        history=None,
        record=record,
        renderer=renderer,
        tools=tools,
        gate=gate,
        skill_registry=reg,
    )
    dispatch = build_tool_dispatch(tools, reg, skill_dispatch, gate)
    server_name = server_cfg.name or "voss"
    server = McpServer(
        name=server_name, tool_descriptors=descriptors, dispatch=dispatch
    )

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader(loop=loop)
        protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
        transport, w_proto = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout.buffer
        )
        writer = asyncio.StreamWriter(transport, w_proto, None, loop)
        await server.serve_stdio(reader, writer)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        raise click.exceptions.Exit(0)


@click.group("logs")
def logs_group() -> None:
    """Tail NDJSON harness telemetry (written when VOSS_LOG=1 and VOSS_LOG_PATH is set)."""


@logs_group.command("watch")
@click.argument(
    "path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
)
@click.option(
    "--poll-interval",
    default=0.15,
    type=float,
    show_default=True,
    help="Sleep interval when no new lines are available.",
)
def logs_watch_cmd(path: Path, poll_interval: float) -> None:
    """Follow a log file while another process appends JSON lines (Ctrl-C to stop).

    Example — terminal A: VOSS_LOG=1 VOSS_LOG_PATH=.voss-cache/harness.ndjson voss chat

    Terminal B: voss logs watch .voss-cache/harness.ndjson
    """
    import time

    with path.open(encoding="utf-8") as fh:
        fh.seek(0, os.SEEK_END)
        try:
            while True:
                line = fh.readline()
                if line:
                    click.echo(line.rstrip("\n"))
                else:
                    time.sleep(max(poll_interval, 0.05))
        except KeyboardInterrupt:
            click.echo("", err=True)


@click.command("consensus")
@click.option("--staged", "input_mode", flag_value="staged", default=True, help="Critique staged changes (default).")
@click.option("--diff", "ref", default=None, metavar="REF", help="Critique diff against REF.")
@click.option("--stdin", "input_mode", flag_value="stdin", help="Read diff from stdin.")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Working directory.")
@click.option("--auth", "auth_pref", type=click.Choice(AUTH_CHOICES), default="auto", help="Credential source.")
@click.option("--model", default=None, help="Model override.")
def consensus_cmd(input_mode: str, ref: str | None, cwd_str: str, auth_pref: str, model: str | None) -> None:
    """Critique a diff against .voss/constraints.yml rules."""
    from voss.harness.consensus import capture_diff, format_violations, load_constraints, run_critique

    cwd = Path(cwd_str).resolve()
    _resolve_default_model(model)

    constraints = load_constraints(cwd)
    if constraints is None:
        sys.exit(0)

    mode = "ref" if ref else input_mode
    try:
        diff_text = capture_diff(mode, cwd, ref=ref)
    except RuntimeError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)

    if not diff_text:
        click.echo("\u2713 No changes to critique.")
        sys.exit(0)

    res, provider = _resolve_auth_or_die(auth_pref)
    provider = _apply_boot_model(provider, user_explicit=model, auth_source=res.source)
    # commit-time critique runs the `commit` role chain when configured,
    # overriding the default-role provider; --model still wins.
    provider = _apply_role_chain(provider, "commit", user_explicit=model)
    cfg = get_config()
    result = asyncio.run(run_critique(provider, cfg.default_model, constraints, diff_text))

    if result is None:
        click.echo("warning: LLM request failed — commit proceeds (fail-open).", err=True)
        sys.exit(0)

    text, has_violations = format_violations(result)
    click.echo(text)
    if has_violations and constraints.mode == "block":
        sys.exit(1)
    sys.exit(0)


HOOK_SHIM = "#!/bin/sh\n# Installed by: voss hooks install\nexec voss consensus --staged\n"
HOOK_MARKER = "Installed by: voss hooks install"


@click.group("hooks")
def hooks_group() -> None:
    """Manage git pre-commit hook for voss consensus."""


@hooks_group.command("install")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Working directory.")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing hook.")
def hooks_install_cmd(cwd_str: str, force: bool) -> None:
    """Install a pre-commit hook that runs voss consensus."""
    cwd = Path(cwd_str).resolve()
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=5,
    )
    if out.returncode != 0:
        click.echo("Error: not a git repository.", err=True)
        sys.exit(2)
    git_root = Path(out.stdout.strip())
    hook_path = git_root / ".git" / "hooks" / "pre-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    if hook_path.exists() and not force:
        click.echo("Error: .git/hooks/pre-commit already exists. Use --force to overwrite.", err=True)
        sys.exit(1)
    hook_path.write_text(HOOK_SHIM)
    hook_path.chmod(0o755)
    click.echo(f"Installed pre-commit hook at {hook_path}")


@hooks_group.command("uninstall")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Working directory.")
def hooks_uninstall_cmd(cwd_str: str) -> None:
    """Remove a voss-installed pre-commit hook."""
    cwd = Path(cwd_str).resolve()
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=5,
    )
    if out.returncode != 0:
        click.echo("Error: not a git repository.", err=True)
        sys.exit(2)
    git_root = Path(out.stdout.strip())
    hook_path = git_root / ".git" / "hooks" / "pre-commit"
    if not hook_path.exists():
        click.echo("No pre-commit hook found.")
        sys.exit(0)
    content = hook_path.read_text(encoding="utf-8")
    if HOOK_MARKER not in content:
        click.echo("Error: .git/hooks/pre-commit was not installed by voss. Remove manually.", err=True)
        sys.exit(1)
    hook_path.unlink()
    click.echo("Removed pre-commit hook.")


@click.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind host (loopback only).")
@click.option("--port", default=0, type=int, help="Bind port; 0 = ephemeral.")
@click.option("--token", default=None, help="Bearer token; auto-generated if omitted.")
def serve_cmd(host: str, port: int, token: str | None) -> None:
    """Run the REST+SSE harness server for thin clients (voss-tui).

    Prints a one-line `{port, token}` handshake to stdout, then serves until
    the parent process exits. Requires the `server` extra (`pip install
    voss[server]`).
    """
    try:
        from .server.serve import run_server
    except ImportError as exc:  # pragma: no cover - missing optional dep
        raise click.ClickException(
            "the server extra is not installed — run: pip install 'voss[server]'"
        ) from exc
    run_server(host=host, port=port, token=token)


@click.group("capabilities")
def capabilities_group() -> None:
    """List and inspect the static project capability registry.

    This view does not open MCP sessions; use `voss mcp list` for configured
    MCP servers.
    """


@capabilities_group.command("list")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON.")
def capabilities_list_cmd(cwd_str: str, json_mode: bool) -> None:
    """List static capabilities grouped by group (compact names)."""
    import json as json_lib

    cwd = Path(cwd_str).resolve()
    tools = make_toolset(cwd)  # no session_id — listing never invokes tools
    by_group: dict[str, list[str]] = {}
    for name, entry in tools.items():
        by_group.setdefault(entry.group, []).append(name)

    if json_mode:
        out = {g: sorted(by_group[g]) for g in CAPABILITY_GROUPS if g in by_group}
        click.echo(json_lib.dumps(out))
        return

    for g in CAPABILITY_GROUPS:
        names = by_group.get(g)
        if not names:
            continue  # omit empty groups
        click.echo(f"{g}:")
        for name in sorted(names):
            click.echo(f"  {name}")


@capabilities_group.command("inspect")
@click.argument("name")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON.")
def capabilities_inspect_cmd(name: str, cwd_str: str, json_mode: bool) -> None:
    """Show full normalized detail for one static capability."""
    import json as json_lib

    cwd = Path(cwd_str).resolve()
    tools = make_toolset(cwd)
    entry = tools.get(name)
    if entry is None:
        click.echo(f"<error: unknown capability: {name}>", err=True)
        raise click.exceptions.Exit(1)

    cap = entry.capability_dict()
    if json_mode:
        click.echo(json_lib.dumps(cap, indent=2, default=str))
        return

    width = max(len(k) for k in cap)
    for key in (
        "name",
        "description",
        "group",
        "is_mutating",
        "is_network",
        "is_stateful",
        "scope_requirements",
        "audit_behavior",
        "input_schema",
        "output_schema",
    ):
        click.echo(f"{key:<{width}} : {cap[key]}")


@click.group("principles")
def principles_group() -> None:
    """Inspect the active engineering principles (VPRIN-07)."""


@principles_group.command("show")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON.")
def principles_show_cmd(cwd_str: str, json_mode: bool) -> None:
    """Show the merged active principles with each one's source."""
    import json as json_lib

    from voss.harness.principles import VossPrinciplesConfigError, resolve_with_sources

    cwd = Path(cwd_str).resolve()
    try:
        items = resolve_with_sources(cwd)
    except VossPrinciplesConfigError as e:
        click.echo(f"<error: {e}>", err=True)
        raise click.exceptions.Exit(1) from e

    if json_mode:
        click.echo(
            json_lib.dumps(
                [{"key": k, "text": t, "source": s} for k, t, s in items]
            )
        )
        return

    if not items:
        click.echo("(no active principles)")
        return
    key_w = max(len(k) for k, _, _ in items)
    for key, text, source in items:
        click.echo(f"{key:<{key_w}}  [{source}]  {text}")


@click.command("board")
@click.argument("root_id", required=False, default=None)
@click.option(
    "--cwd",
    "cwd_str",
    default=".",
    type=click.Path(file_okay=False),
    help="Project root.",
)
def board_cmd(root_id: str | None, cwd_str: str) -> None:
    """Render the board read-only from persisted session-tree nodes (VBOARD-10)."""
    from voss.harness.board.cli_view import render_board

    cwd = Path(cwd_str).resolve()
    rc = render_board(cwd, root_id=root_id)
    raise click.exceptions.Exit(code=rc)


@click.group("team")
def team_group() -> None:
    """Inspect and validate the team cage (VTEAM-10)."""


@team_group.command("check")
@click.argument("path", required=False, default=".voss/team.voss")
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON.")
def team_check_cmd(path: str, json_mode: bool) -> None:
    """Validate a .voss team file via the compile_team validator."""
    import json as json_lib

    from voss import parse
    from voss.ast_nodes import TeamDecl
    from voss.harness.team import VossTeamConfigError, compile_team

    def _fail(msg: str) -> None:
        if json_mode:
            click.echo(json_lib.dumps({"ok": False, "error": msg}))
        else:
            click.echo(f"<error: {msg}>", err=True)
        raise click.exceptions.Exit(1)

    p = Path(path)
    if not p.is_file():
        _fail(f"team file not found: {path}")
    team_cwd = p.resolve().parent.parent if p.resolve().parent.name == ".voss" else p.resolve().parent

    src = p.read_text(encoding="utf-8")
    program = parse(src if src.endswith("\n") else src + "\n", str(p))
    team_decl = next(
        (d for d in program.body if isinstance(d, TeamDecl)), None
    )
    if team_decl is None:
        _fail(f"no team{{}} block in {path}")

    try:
        config, _registry = compile_team(team_decl, cwd=team_cwd)
    except VossTeamConfigError as e:
        _fail(e.format_diagnostic())
        return  # unreachable; _fail raises. keeps type-checker happy.

    ceiling = config.ceiling
    scope_globs = list(ceiling.scope.globs) if ceiling.scope is not None else []
    roster = sorted(config.roster_ids)

    if json_mode:
        click.echo(
            json_lib.dumps(
                {
                    "ok": True,
                    "team": config.name,
                    "roster": roster,
                    "ceiling": {
                        "budget_tokens": ceiling.budget_tokens,
                        "scope": scope_globs,
                        "latency_seconds": ceiling.latency_seconds,
                    },
                }
            )
        )
        return

    click.echo(f"PASS  {config.name}")
    click.echo(f"roster: {', '.join(roster)}")
    click.echo(
        f"ceiling: budget={ceiling.budget_tokens} "
        f"scope={scope_globs} latency={ceiling.latency_seconds}"
    )


def _default_team_config():
    """Build the DEFAULT_ROSTER team config + registry (no .voss/team.voss).

    Direct construction (no AST TeamDecl). Mirrors compile_team's output shape:
    a TeamConfig over the shipped DEFAULT_ROSTER and a SubagentRegistry holding
    one spec per role (apply_role_defaults resolves model tiers via the
    configured catalog — V7-RESEARCH Pitfall 7).
    """
    from voss.ast_nodes import Span
    from voss.harness.subagents import SubagentRegistry
    from voss.harness.team import (
        DEFAULT_ROSTER,
        BoardSpec,
        TeamCeiling,
        TeamConfig,
        TeamPolicy,
        subagent_spec_from_role,
    )

    ceiling = TeamCeiling(budget_tokens=500_000, scope=None, latency_seconds=3600)
    registry = SubagentRegistry()
    span = Span(file="<default>", line_start=0, col_start=0, line_end=0, col_end=0)
    for role_name in DEFAULT_ROSTER:
        spec = subagent_spec_from_role(
            role_name=role_name,
            role_decl_span=span,
            kvs={},
            ceiling=ceiling,
            ceiling_ast=None,
            apply_role_defaults=True,
        )
        registry.register(spec)
    config = TeamConfig(
        name="default",
        ceiling=ceiling,
        policy=TeamPolicy(p=None),
        em_agent_id=None,
        roster_ids=frozenset(DEFAULT_ROSTER),
        board=BoardSpec(raw_items=()),
        rituals=(),
    )
    return config, registry


def _persist_run_final(rf, cwd: Path, decision: str | None = None) -> Path:
    """Write RunFinal to <cwd>/.voss/sessions/<root_id>/run-final.json (0o600).

    Mirrors session_tree._write_node_file (mkdir parents, write, chmod 0o600).
    SECURITY (T-V7-05): root_id comes ONLY from rf.root_id (a SessionTreeNode
    UUID), never user input — no path traversal. RunFinal is frozen+slots and is
    never mutated; the sign_off decision lives only in the serialized dict.
    """
    from datetime import datetime, timezone

    run_dir = cwd / ".voss" / "sessions" / rf.root_id
    run_dir.mkdir(parents=True, exist_ok=True)
    persist_path = run_dir / "run-final.json"
    data = asdict(rf)
    if decision is not None:
        data["sign_off"] = {
            "decision": decision,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    persist_path.write_text(json.dumps(data, indent=2))
    persist_path.chmod(0o600)
    return persist_path


def _write_signoff_ack(
    cwd: Path, root_id: str, *, killed_count: int, misroute_count: int
) -> Path:
    """Write the killed/misroute acknowledgement to a NEW .signoff-ack.json (VAUD-SIGNOFF).

    A governance record ALONGSIDE the audited run, never a mutation of
    run-final.json or any node JSON. Mirrors _persist_run_final's 0o600
    mkdir+write+chmod pattern. SECURITY (T-V9-06-03): root_id comes ONLY from
    rf.root_id (a SessionTreeNode UUID), never user input — no path traversal.
    """
    from datetime import datetime, timezone

    run_dir = cwd / ".voss" / "sessions" / root_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / ".signoff-ack.json"
    data = {
        "ack_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "killed_count": killed_count,
        "misroute_count": misroute_count,
    }
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)
    return path


def _enforce_signoff_ack(
    cwd: Path, root_id: str, *, killed_count: int, misroute_count: int
) -> None:
    """Force acknowledgement of killed/misroute risks before approve (VAUD-SIGNOFF).

    Pitfall 5: a clean run (no kills, no misroutes) returns immediately — no
    empty-diff prompt. Otherwise displays the risk diff and prompts; a non-"yes"
    answer aborts sign-off non-zero; "yes" records the ack in a new
    .signoff-ack.json sidecar.
    """
    if killed_count <= 0 and misroute_count <= 0:
        return
    click.echo(
        f"\nRisk summary: {killed_count} killed card(s), "
        f"{misroute_count} misroute candidate(s)."
    )
    ack = click.prompt(
        "Acknowledge killed/misroute risks? Type 'yes' to continue"
    )
    if ack.strip().lower() != "yes":
        click.echo("Sign-off aborted — acknowledgement required.", err=True)
        raise click.exceptions.Exit(1)
    _write_signoff_ack(
        cwd, root_id, killed_count=killed_count, misroute_count=misroute_count
    )


@team_group.command("approve")
@click.argument("card_id")
@click.option("--reject", is_flag=True, default=False, help="Record a rejection instead.")
@click.option("--note", default="", help="Operator note stored on the record.")
@click.option("--root", "root_id", default=None, help="Session root id (default: most recent).")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
def team_approve_cmd(
    card_id: str, reject: bool, note: str, root_id: str | None, cwd_str: str
) -> None:
    """Record the operator decision for a critical-tier card (VRES-04).

    Writes the approval/rejection sidecar that the 'human' Done clause
    reads — the only thing that can move a critical card past pending-human.
    """
    from voss.harness.board.machine import write_human_approval

    cwd = Path(cwd_str).resolve()
    sessions_dir = cwd / ".voss" / "sessions"
    # Same traversal guards as cli_view.render_board.
    for value, label in ((card_id, "card_id"), (root_id or "", "root_id")):
        if "/" in value or "\\" in value or ".." in value:
            click.echo(f"<error: invalid {label} {value!r}>", err=True)
            raise click.exceptions.Exit(1)
    if root_id is None:
        root_dirs = sorted(
            (d for d in sessions_dir.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        ) if sessions_dir.is_dir() else []
        if not root_dirs:
            click.echo(f"<error: no session roots under {sessions_dir}>", err=True)
            raise click.exceptions.Exit(1)
        root_id = root_dirs[0].name
    elif not (sessions_dir / root_id).is_dir():
        click.echo(f"<error: unknown root {root_id!r}>", err=True)
        raise click.exceptions.Exit(1)
    decision = "rejected" if reject else "approved"
    path = write_human_approval(cwd, root_id, card_id, decision=decision, note=note)
    click.echo(f"{card_id}: {decision} (root {root_id})")
    click.echo(f"recorded: {path}")


@team_group.command("run")
@click.argument("goal")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--max-iterations", default=50, type=int, help="EM loop iteration ceiling.")
def team_run_cmd(goal: str, cwd_str: str, max_iterations: int) -> None:
    """Run the EM loop on a goal: compose team + board + V6 reviewers, sign off.

    Composes the shipped V3 team config + V4 session tree + V5 board + the real
    V6 Reviewer-A/B slots + the O5 em_loop, runs autonomously to terminal,
    persists RunFinal, prints a summary, and records a human approve/reject.
    """
    from voss import parse
    from voss.ast_nodes import TeamDecl
    from voss.harness.board.machine import Board
    from voss.harness.board.stub import DeterministicReviewerStub
    from voss.harness.em.handle import EMBoardHandle
    from voss.harness.em.loop import em_loop
    from voss.harness.em.schema import CreateTicketOp, EMPlanResponse, NoopOp
    from voss.harness.em.stub import DeterministicEMStub
    from voss.harness.permissions import PermissionGate
    from voss.harness.session_tree import SessionTreeManager, SessionTreeNode
    from voss.harness.team import VossTeamConfigError, compile_team

    cwd = Path(cwd_str).resolve()

    team_file = cwd / ".voss" / "team.voss"
    if team_file.is_file():
        src = team_file.read_text(encoding="utf-8")
        program = parse(src if src.endswith("\n") else src + "\n", str(team_file))
        team_decl = next(
            (d for d in program.body if isinstance(d, TeamDecl)), None
        )
        if team_decl is None:
            click.echo(f"<error: no team{{}} block in {team_file}>", err=True)
            raise click.exceptions.Exit(2)
        try:
            config, registry = compile_team(team_decl, cwd=cwd)
        except VossTeamConfigError as e:
            click.echo(e.format_diagnostic(), err=True)
            raise click.exceptions.Exit(2) from e
    else:
        config, registry = _default_team_config()

    async def _run():
        root = SessionTreeNode.create_root(cwd=cwd, limit=500_000)
        manager = SessionTreeManager(root, reserve=0, cwd=cwd)
        reviewer_a = DeterministicReviewerStub(
            conf=0.99, verdict="pass", source="A", tier="fast"
        )
        reviewer_b = DeterministicReviewerStub(
            conf=0.99, verdict="pass", source="B", tier="strong"
        )
        board = Board.from_team_config(
            config,
            recorder=manager,
            reviewer_a=reviewer_a,
            reviewer_b=reviewer_b,
            cwd=cwd,
            per_card_budget=100_000,
        )
        # Pre-spawn >=1 card so RunFinal.total_cards >= 1 (Pitfall 1).
        await board.spawn_card(risk_tier="med")
        base_gate = PermissionGate(mode="auto", auto_yes=True)
        handle = EMBoardHandle(
            board=board,
            registry=registry,
            team_config=config,
            manager=manager,
            base_gate=base_gate,
            cwd=cwd,
        )
        roster_descs = {spec.id: spec.description for spec in registry.entries()}
        worker_role = "backend" if "backend" in config.roster_ids else sorted(config.roster_ids)[0]
        em_agent = DeterministicEMStub(
            scripted=[
                EMPlanResponse(
                    ops=[CreateTicketOp(original_idea=goal, worker_role=worker_role)]
                ),
                EMPlanResponse(ops=[NoopOp(reason="waiting")]),
            ]
        )
        return await em_loop(
            idea=goal,
            em_handle=handle,
            em_agent=em_agent,
            roster_descriptions=roster_descs,
            max_iterations=max_iterations,
        )

    try:
        rf = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — surface as a clean CLI error
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(2) from exc

    # finalize_run() leaves idea="" (handle.py:352); thread the goal in via the
    # frozen-replace mechanism em_loop itself uses for em_iterations.
    import dataclasses

    rf = dataclasses.replace(rf, idea=goal)

    _persist_run_final(rf, cwd)

    click.echo(f"run complete: {rf.idea}")
    click.echo(
        f"cards: total={rf.total_cards} done={rf.done_count} "
        f"blocked={rf.blocked_count} killed={rf.killed_count} "
        f"rescope={rf.rescope_count}"
    )
    click.echo(f"em_iterations: {rf.em_iterations}")

    # VAUD-SIGNOFF: gate approve behind a forced acknowledgement of the
    # killed-card + misroute risk diff. Misroute = a routing with a stated
    # confidence_hint below 0.7 (read-only from the just-persisted snapshot).
    killed_count = rf.killed_count
    misroute_count = 0
    try:
        from voss.harness.audit.load import load_audit_snapshot

        routings = load_audit_snapshot(cwd, run_id=rf.root_id).routings
        misroute_count = sum(
            1
            for r in routings
            if r.confidence_hint is not None and r.confidence_hint < 0.7
        )
    except Exception:
        misroute_count = 0

    _enforce_signoff_ack(
        cwd, rf.root_id, killed_count=killed_count, misroute_count=misroute_count
    )

    decision = click.prompt(
        "Sign off on this run (approve/reject)",
        type=click.Choice(["approve", "reject"]),
    )
    _persist_run_final(rf, cwd, decision=decision)
    click.echo(f"sign-off recorded: {decision}")
    raise click.exceptions.Exit(0)


@click.group("session")
def session_group() -> None:
    """Inspect persisted session trees (VTREE-09)."""


@session_group.command("tree")
@click.argument("root_id")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--json", "json_mode", is_flag=True, help="Machine-readable JSON export.")
def session_tree_cmd(root_id: str, cwd_str: str, json_mode: bool) -> None:
    """Show the session tree for a root node id."""
    import json as json_lib

    from .session_tree import SessionTreeNotFoundError, export_tree

    cwd = Path(cwd_str).resolve()
    try:
        tree = export_tree(root_id, cwd)
    except SessionTreeNotFoundError:
        click.echo(f"<error: no session tree for root_id {root_id!r}>", err=True)
        raise click.exceptions.Exit(1)

    if json_mode:
        click.echo(json_lib.dumps(tree, indent=2))
        return

    for node in tree["nodes"]:
        indent = "  " if node["parent_run_id"] else ""
        envelope = node["envelope"]
        terminal = node["terminal_state"]
        state = terminal["exit_reason"] if terminal else "open"
        click.echo(
            f"{indent}{node['id']}  "
            f"parent={node['parent_run_id'] or '—'}  "
            f"limit={envelope['limit']} spent={envelope['spent']}  "
            f"state={state}  "
            f"scope={node.get('scope') or '—'} role={node.get('role') or '—'}"
        )


# --- V19-04 VSEM-05: unified cross-corpus recall verb (D-09 user-locked) ---

# T-V19-04: excerpts are raw repo source — scrub secret-shaped strings before
# they leave the process (plain AND --json output).
_RECALL_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[bap]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b(\s*[=:]\s*)[\"']([^\"']{8,})[\"']"),
)


def _redact_recall_text(text: str) -> str:
    for pattern in _RECALL_SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}\"[redacted]\"", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text


def _recall_hit_fields(hit) -> dict:
    """Documented --json schema: source, locator, path, line_start, line_end,
    score, excerpt. ONLY Hit fields — never keys/env/secrets (T-V19-04)."""
    is_code = (hit.source or "").startswith("code")
    path = None
    if is_code:
        parts = hit.locator.split(":")
        path = ":".join(parts[1:-1]) if len(parts) >= 3 else hit.locator
    return {
        "source": hit.source,
        "locator": hit.locator,
        "path": path,
        "line_start": hit.line_start if is_code else None,
        "line_end": hit.line_end if is_code else None,
        "score": hit.score,
        "excerpt": _redact_recall_text((hit.excerpt or "").replace("\n", " ")[:160]),
    }


def _recall_external_rankings(rankings: list[list]) -> list[list]:
    """Keep CLI source labels as corpus names even when an index marks BM25 fallback."""
    normalized: list[list] = []
    for hits in rankings:
        normalized.append(
            [
                replace(hit, source=hit.source.removesuffix("[degraded]"))
                if (hit.source or "").endswith("[degraded]")
                else hit
                for hit in hits
            ]
        )
    return normalized


@click.command("recall")
@click.argument("query", nargs=-1, required=False)
@click.option("--json", "json_out", is_flag=True, help="Emit machine-readable hits.")
@click.option("--top", "top_k", default=10, type=int, help="Max fused hits.")
@click.option("--refresh", "do_refresh", is_flag=True, help="Reindex before querying (D-13 trigger #3).")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False))
def recall_cmd(query: tuple[str, ...], json_out: bool, top_k: int, do_refresh: bool, cwd_str: str) -> None:
    """Unified recall across the code index AND project memory (RRF-fused)."""
    query_str = " ".join(query).strip()
    if not query_str:
        click.echo("usage: voss recall <query> [--top N] [--json] [--refresh]")
        return

    cwd = Path(cwd_str).resolve()

    from voss.harness.code.semantic_index import CodeIndex
    from voss.harness.recall.external_index import ExternalRecallService

    code_index = CodeIndex(cwd)
    ext_svc = ExternalRecallService(cwd)
    if do_refresh:
        try:
            from voss.harness.code.index import build_index as _build_m10

            _build_m10(cwd)
        except Exception:  # noqa: BLE001 — M10 refresh is best-effort; chunker falls back
            pass
        code_index.build()
        ext_svc.build_all()
    else:
        try:
            ext_svc.ensure_background_build()
        except Exception:  # noqa: BLE001 — source config/build issues must not kill recall
            pass

    recall_k = max(top_k * 3, top_k)
    code_hits = code_index.query(query_str, top_k=recall_k)
    try:
        mem_hits = MemoryStore(cwd).recall(query_str, top_k=recall_k)
    except Exception:  # noqa: BLE001 — missing/corrupt memory store must not kill code recall
        mem_hits = []
    # V21 (VGMEM-*): fuse the cross-project global corpus. Global hits carry a
    # `global:` locator prefix so they survive RRF dedup distinctly and render
    # with a `[global]` label (stripped from the displayed locator).
    global_hits: list = []
    try:
        import dataclasses as _dc

        global_store = make_global_store()
        if global_store is not None:
            raw_global = global_store.recall(query_str, top_k=recall_k)
            global_hits = [_dc.replace(h, locator=f"global:{h.locator}") for h in raw_global]
    except Exception:  # noqa: BLE001 — missing/disabled global corpus must not kill recall
        global_hits = []
    try:
        external_hits_per_source = _recall_external_rankings(ext_svc.query_all(query_str, top_k=recall_k))
    except Exception:  # noqa: BLE001 — missing/misconfigured sources must not kill recall
        external_hits_per_source = []

    # RRF is rank-based and corpus-agnostic (D-09); the code: id prefix
    # guarantees no locator collision with memory/external ids in the dedup.
    fused = MemoryStore._rrf_merge([code_hits, mem_hits, global_hits, *external_hits_per_source], top_k=top_k)

    if json_out:
        click.echo(json.dumps({"query": query_str, "hits": [_recall_hit_fields(h) for h in fused]}, indent=2))
        return

    if not fused:
        click.echo("(no hits)")
        return
    for hit in fused:
        fields = _recall_hit_fields(hit)
        if hit.locator.startswith("global:"):
            label = "global"
            display = hit.locator[len("global:"):]
        elif fields["source"] == "code":
            label = fields["source"]
            display = f"{fields['path']}:{fields['line_start']}" if fields["line_start"] else fields["path"]
        else:
            label = fields["source"]
            display = hit.locator
        click.echo(f"[{label}] {display} (score {hit.score:.2f})")
        if fields["excerpt"]:
            click.echo(f"  {fields['excerpt']}")


def _warn_instructions_drift(record, cwd: Path) -> None:
    """One-line warning when AGENTS.md/CLAUDE.md changed since the session started."""
    from . import instructions as instructions_mod
    from .config import get_instructions_config

    recorded = getattr(record, "instructions_hash", "") or ""
    if not recorded:
        return
    current = instructions_mod.load(cwd, config=get_instructions_config()).bundle_hash
    if current != recorded:
        click.echo(
            "  [instructions changed since this session started "
            f"({recorded[:12]} → {current[:12]}); the next turn loads the new files]",
            err=True,
        )


@click.group("instructions")
def instructions_group() -> None:
    """Inspect the AGENTS.md / CLAUDE.md bundle the harness injects."""


def _instructions_bundle_for(cwd_str: str, target: str | None):
    from . import instructions as instructions_mod
    from .config import get_instructions_config

    cwd = Path(cwd_str).resolve()
    return instructions_mod.load(cwd, target, config=get_instructions_config())


def _bundle_payload(bundle) -> dict:
    return {
        "bundle_hash": bundle.bundle_hash,
        "tokens": bundle.tokens,
        "files": [
            {
                "path": f.path,
                "kind": f.kind,
                "scope_dir": f.scope_dir,
                "sha256": f.sha256,
                "bytes": f.bytes,
                "tokens": f.tokens,
                "imports": list(f.imports),
                "truncated": f.path in bundle.truncated,
            }
            for f in bundle.files
        ],
        "collapsed": list(bundle.collapsed),
        "truncated": list(bundle.truncated),
        "load_errors": list(bundle.load_errors),
    }


@instructions_group.command("show")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--target", default=None, help="Directory (relative to root) to scope nested files.")
@click.option("--json", "json_mode", is_flag=True, help="Machine-readable output.")
def instructions_show_cmd(cwd_str: str, target: str | None, json_mode: bool) -> None:
    """Show instruction files in load order with kind, tokens, and hash."""
    bundle = _instructions_bundle_for(cwd_str, target)
    if json_mode:
        click.echo(json.dumps(_bundle_payload(bundle), indent=2))
        return
    if not bundle.files:
        click.echo("(no instruction files found)")
    for f in bundle.files:
        flag = " [truncated]" if f.path in bundle.truncated else ""
        imports = f" imports={','.join(f.imports)}" if f.imports else ""
        click.echo(f"  {f.path}  [{f.kind}]  {f.tokens} tokens  {f.sha256[:12]}{imports}{flag}")
    for c in bundle.collapsed:
        click.echo(f"  {c}  [collapsed]")
    for e in bundle.load_errors:
        click.echo(f"  ! {e}")
    click.echo(f"  bundle: {bundle.bundle_hash[:16]}  {bundle.tokens} tokens")


@instructions_group.command("check")
@click.option("--cwd", "cwd_str", default=".", type=click.Path(file_okay=False), help="Project root.")
@click.option("--target", default=None, help="Directory (relative to root) to scope nested files.")
def instructions_check_cmd(cwd_str: str, target: str | None) -> None:
    """Exit 1 on import cycles, unreadable files, or budget overflow."""
    bundle = _instructions_bundle_for(cwd_str, target)
    problems = list(bundle.load_errors) + [f"budget overflow: {p}" for p in bundle.truncated]
    for p in problems:
        click.echo(f"  ! {p}", err=True)
    if problems:
        sys.exit(1)
    click.echo(f"  ok: {len(bundle.files)} file(s), {bundle.tokens} tokens, {bundle.bundle_hash[:16]}")


AGENT_COMMANDS = (
    do_cmd,
    serve_cmd,
    chat_cmd,
    edit_cmd,
    login_cmd,
    logout_cmd,
    doctor_cmd,
    sessions_cmd,
    review_cmd,
    jobs_cmd,
    watch_cmd,
    inspect_group,
    vdiff_cmd,
    resume_cmd,
    tools_cmd,
    plugins_cmd,
    plugin_group,
    skills_cmd,
    skill_group,
    agents_cmd,
    agent_group,
    memory_group,
    recall_cmd,
    config_cmd,
    mcp_group,
    logs_group,
    eval_cmd,
    consensus_cmd,
    hooks_group,
    capabilities_group,
    principles_group,
    instructions_group,
    session_group,
    team_group,
    board_cmd,
    audit_cmd,
    claims_group,
)


def register(group: click.Group) -> None:
    """Attach all agent commands to a click Group."""
    for cmd in AGENT_COMMANDS:
        group.add_command(cmd)


# ---------------------------------------------------------------------------
# standalone entry: `python -m voss.harness ...`
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """voss · agent (standalone harness invocation).

    Usually invoked as `voss do` / `voss chat`. Bare invocation drops into chat.
    Interactive commands: run `voss chat`, then /help
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(
            chat_cmd,
            model=None,
            cwd_str=".",
            json_mode=False,
            mode="plan",  # D-07: bare voss defaults to plan
            auth_pref="auto",
        )


register(main)


if __name__ == "__main__":
    main()
