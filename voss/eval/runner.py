"""Evaluation suite runner for `voss eval` (M5)."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import textwrap
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import httpx

from voss import __version__ as VOSS_VERSION
from voss.harness import auth as auth_mod
from voss.harness.config import get_eval_judge_model, get_eval_max_turns
from voss.harness.agent import run_turn
from voss.harness.net import NetSession
from voss.harness.permissions import PermissionGate
from voss.harness.render import PlainRenderer
from voss.harness.session import SessionRecord, load, save
from voss.harness.tools import make_toolset
from voss_runtime import EpisodicMemory, configure, get_config
from voss_runtime.providers import StubProvider, get as get_provider, has as has_provider
from voss_runtime.providers.base import ModelProvider

from .friction import friction
from .judge import judge_run
from .suite import TaskSpec, load_suite
from .summary import write_summary

SUITE_ROOT = Path("tests/eval")
RESUME_CANCEL_DELAY_S = float(os.environ.get("EVAL_RESUME_CANCEL_DELAY_S", "0.05"))
NO_CREDS_MESSAGE = "voss eval: no provider creds — pass --stub for hermetic smoke or run /login"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_dir_name() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(":", "")


def _prepare_fixture(task_dir: Path, tmp: Path) -> Path:
    cwd = tmp / "fixture"
    shutil.copytree(task_dir / "fixture", cwd)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=cwd, check=True)
    subprocess.run(["git", "add", "-A"], cwd=cwd, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=eval@voss",
            "-c",
            "user.name=eval",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        cwd=cwd,
        check=True,
    )
    return cwd


def _file_diff(cwd: Path) -> str:
    completed = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else ""


def _run_checks(checks: list, cwd: Path) -> tuple[bool, list[dict]]:
    """Run all checks; return (gate_pass, results_list). Never short-circuits."""
    results = []
    for check in checks:
        if check.type == "cmd":
            try:
                cp = subprocess.run(
                    check.run,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=getattr(check, "timeout", 60),
                    check=False,
                )
                passed = cp.returncode == 0
                detail = cp.stdout[:200] if passed else cp.stderr[:200]
            except subprocess.TimeoutExpired:
                passed = False
                detail = "timeout"
        elif check.type == "file_exists":
            passed = (cwd / check.path).exists()
            detail = ""
        elif check.type == "file_contains":
            p = cwd / check.path
            passed = p.exists() and check.text in p.read_text()
            detail = ""
        results.append({"type": check.type, "pass": passed, "detail": detail})
    gate_pass = all(r["pass"] for r in results)
    return gate_pass, results


def _extract_signals(record: SessionRecord) -> tuple[float | None, float | None]:
    total = 0.0
    saw_cost = False
    confidence: float | None = None
    for run in record.runs:
        cost = run.get("cost_usd")
        if isinstance(cost, (int, float)) and cost > 0:
            total += float(cost)
            saw_cost = True
        plan = run.get("plan")
        if confidence is None and isinstance(plan, dict):
            value = plan.get("confidence")
            if isinstance(value, (int, float)):
                confidence = float(value)
    return (total if saw_cost else None), confidence


def _append_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _sum_input_tokens(record: SessionRecord) -> int:
    """V18 VOPT-07: sum prompt_tokens over every run iteration.

    Additive row field so the packing eval gate measures input-token
    reduction from a real figure (runs.jsonl previously carried no token
    field). Missing/crashed iterations contribute 0 — never raises.
    """
    total = 0
    for run in record.runs:
        for it in run.get("iterations") or []:
            if isinstance(it, dict):
                v = it.get("prompt_tokens")
                if isinstance(v, (int, float)):
                    total += int(v)
    return total


def _record_model(model: str | None) -> str:
    return model or get_config().default_model


def _add_run(record: SessionRecord, result) -> None:
    if result.run is None:
        return
    record.runs.append(asdict(result.run))
    record.total_cost_usd += result.cost_usd


def _make_stub_net_session(spec: TaskSpec, *, stub: bool) -> NetSession | None:
    if not stub or "web_fetch" not in spec.tools:
        return None

    def _stub_handler(request: httpx.Request) -> httpx.Response:
        if "example.com" in str(request.url):
            return httpx.Response(
                200,
                text=textwrap.dedent(
                    """
                    <html>
                      <head><title>Example Domain</title></head>
                      <body>
                        <h1>Example Domain</h1>
                        <p>This domain is for illustration.</p>
                      </body>
                    </html>
                    """
                ).strip(),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        return httpx.Response(404, text="not found")

    return NetSession(
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(_stub_handler),
            follow_redirects=True,
            max_redirects=5,
        )
    )


def _live_env(cwd: Path) -> dict[str, str]:
    """Env for live surface drivers: inherit auth keys, never inject stubs (D-05)."""
    env = dict(os.environ)
    env["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"
    env["VOSS_DEV"] = "1"
    env["PYDANTIC_DISABLE_PLUGINS"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    return env


async def _drive_cli_do(
    spec: TaskSpec, cwd: Path, *, auth: str = "auto", timeout: float = 120.0
) -> tuple[str, str | None, bool]:
    """Returns (final, crash_reason_or_None, capped=False)."""
    cmd = [
        sys.executable, "-m", "voss.cli", "do", spec.prompt,
        "--cwd", str(cwd), "--plain", "--mode", spec.mode, "--auth", auth,
    ]
    if spec.auto_approve_edits:
        cmd.append("--yes")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=_live_env(cwd),
            input="",  # empty stdin → isatty()=False, piped-stdin branch appends nothing
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", "timeout", False
    if result.returncode != 0:
        return "", f"returncode={result.returncode}: {result.stderr[:200]}", False
    return result.stdout.strip(), None, False


async def _drive_cli_chat(
    spec: TaskSpec, cwd: Path, *, auth: str = "auto", timeout: float = 120.0
) -> tuple[str, str | None, bool]:
    """Single piped turn: input() reads the line, next call EOFError → clean exit."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "voss.cli", "chat",
                "--cwd", str(cwd), "--plain", "--mode", spec.mode, "--auth", auth,
            ],
            cwd=str(cwd),
            env=_live_env(cwd),
            input=spec.prompt + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", "timeout", False
    if result.returncode != 0:
        return "", f"returncode={result.returncode}: {result.stderr[:200]}", False
    return result.stdout.strip(), None, False


async def _drive_cli_edit(
    spec: TaskSpec, cwd: Path, *, auth: str = "auto", timeout: float = 120.0
) -> tuple[str, str | None, bool]:
    if not spec.target_file:
        return "", "cli:edit requires target_file in task.toml", False
    target = cwd / spec.target_file
    # edit_cmd has no --yes; mode "auto" is the no-prompt tier (EditScope still
    # enforces the target jail). auto_approve_edits=true maps to it.
    mode = "auto" if spec.auto_approve_edits else spec.mode
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "voss.cli", "edit", str(target),
                "--cwd", str(cwd), "--plain", "--mode", mode, "--auth", auth,
            ],
            cwd=str(cwd),
            env=_live_env(cwd),
            input=spec.prompt + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", "timeout", False
    if result.returncode != 0:
        return "", f"returncode={result.returncode}: {result.stderr[:200]}", False
    return result.stdout.strip(), None, False


async def _consume_sse(
    client,
    base_url: str,
    sid: str,
    headers: dict[str, str],
    *,
    permission_choice: str,
    message_body: dict,
) -> str:
    """Open the SSE stream, post the message INSIDE the stream context (events
    emitted in the gap are not lost), and consume until session.idle.

    permission.updated → reply as a normal await inside the loop (httpx
    AsyncClient supports concurrent requests on one client). Returns the
    final event's text.
    """
    final_text = ""
    async with client.stream(
        "GET",
        f"{base_url}/session/{sid}/events",
        headers={**headers, "Accept": "text/event-stream"},
    ) as sse:
        await client.post(
            f"{base_url}/session/{sid}/message", json=message_body, headers=headers
        )
        event_type = ""
        async for line in sse.aiter_lines():
            line = line.rstrip("\r")
            if not line:
                event_type = ""
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    payload = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                ev_type = payload.get("type", event_type)
                if ev_type == "permission.updated":
                    await client.post(
                        f"{base_url}/session/{sid}/permission",
                        json={"id": payload["id"], "choice": permission_choice},
                        headers=headers,
                    )
                elif ev_type == "final":
                    final_text = payload.get("text", "")
                elif ev_type == "session.idle":
                    break
    return final_text


async def _drive_serve(
    spec: TaskSpec,
    cwd: Path,
    *,
    permission_choice: str = "a",
    auth: str = "auto",
    model: str | None = None,
    timeout: float = 180.0,
) -> tuple[str, str | None, bool]:
    """Spawn `voss serve`, parse the {v,port,token} handshake, drive one turn
    over httpx REST+SSE. The bearer token lives ONLY in the Authorization
    header — never in any return value or artifact.
    """
    env = _live_env(cwd)
    env["VOSS_DEV"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "voss.cli", "serve"],
        env=env,
        cwd=str(cwd),
        stdin=subprocess.PIPE,  # held open = heartbeat; EOF self-terminates server
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stderr_lines: list[str] = []
    threading.Thread(
        target=lambda: stderr_lines.extend(iter(proc.stderr)), daemon=True
    ).start()
    final = ""
    try:
        handshake = None
        deadline = time.monotonic() + 60.0
        for line in proc.stdout:
            try:
                h = json.loads(line.strip())
            except json.JSONDecodeError:
                h = None
            if isinstance(h, dict) and h.get("token"):
                handshake = h
                break
            if time.monotonic() > deadline:
                break
        if handshake is None:
            proc.kill()
            return (
                "",
                f"handshake timeout; stderr: {''.join(stderr_lines[-10:])[:300]}",
                False,
            )

        base_url = f"http://127.0.0.1:{handshake['port']}"
        headers = {"Authorization": f"Bearer {handshake['token']}"}
        # auth + model must agree (the server does NOT remap the default model
        # to the credential source: auth=env-openai + a claude default model
        # dies in the provider on turn 1).
        session_body: dict = {"cwd": str(cwd), "auth": auth}
        if model is not None:
            session_body["model"] = model
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{base_url}/session",
                json=session_body,
                headers=headers,
            )
            r.raise_for_status()
            sid = r.json()["id"]
            final = await _consume_sse(
                client,
                base_url,
                sid,
                headers,
                permission_choice=permission_choice,
                message_body={
                    "parts": [{"type": "text", "text": spec.prompt}],
                    "mode": spec.mode,
                },
            )
    except Exception as exc:  # noqa: BLE001 - eval records failures as rows
        return "", f"{type(exc).__name__}: {str(exc)[:300]}", False
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return final, None, False


async def _drive_sdk_client(
    spec: TaskSpec,
    *,
    cwd: Path,
    consumer: str,  # "ts" | "go" | "rust"
    auth: str = "auto",
    model: str | None = None,
    timeout: float = 180.0,
) -> str:
    """Spawn `voss serve`, then spawn the committed consumer subprogram for the
    given client SDK; parse its structured-JSON stdout line; return the final
    text. The runner owns the serve lifecycle — the consumer never self-launches
    the server (TS launcher 10s-handshake pitfall) and receives coordinates via
    env only (token never on a CLI arg).
    """
    repo_root = Path(__file__).resolve().parents[2]
    consumers_dir = repo_root / "tests" / "eval" / "sdk" / "consumers"

    env = _live_env(cwd)
    # The public SDK createSession surfaces post only {cwd}; the serve owner
    # (this runner) pins the session defaults instead, otherwise auth="auto"
    # resolves env API keys ahead of the requested subscription and the
    # config-default model can mismatch the credential source (E4 live-proof
    # failure mode: env-openai + claude default model dies on turn 1).
    env["VOSS_SERVE_DEFAULT_AUTH"] = auth
    if model is not None:
        env["VOSS_SERVE_DEFAULT_MODEL"] = model
    proc_server = subprocess.Popen(
        [sys.executable, "-m", "voss.cli", "serve"],
        env=env,
        cwd=str(cwd),
        stdin=subprocess.PIPE,  # held open = heartbeat; EOF self-terminates server
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stderr_lines: list[str] = []
    threading.Thread(
        target=lambda: stderr_lines.extend(iter(proc_server.stderr)), daemon=True
    ).start()
    try:
        handshake = None
        deadline = time.monotonic() + 60.0
        for line in proc_server.stdout:
            try:
                h = json.loads(line.strip())
            except json.JSONDecodeError:
                h = None
            if isinstance(h, dict) and h.get("token"):
                handshake = h
                break
            if time.monotonic() > deadline:
                break
        if handshake is None:
            raise TimeoutError(
                f"serve handshake timeout; stderr: {''.join(stderr_lines[-10:])[:300]}"
            )

        consumer_env = {
            **env,
            "VOSS_BASE_URL": f"http://127.0.0.1:{handshake['port']}",
            "VOSS_TOKEN": handshake["token"],
            "VOSS_CWD": str(cwd),
            # Go interpreterPath() resolves python relative to CWD — pin it.
            "VOSS_PYTHON": str(Path(sys.executable).resolve()),
            "VOSS_PROMPT": spec.prompt,
            "VOSS_MODE": spec.mode,
            # Deny scenarios set permission_choice="d" in task.toml; consumers
            # default to "a" when unset (TaskSpec default is "a" already).
            "VOSS_PERMISSION_CHOICE": spec.permission_choice,
        }
        run_cwd: str | None = None
        if consumer == "ts":
            cmd = ["node", str(consumers_dir / "ts" / "consumer.js")]
        elif consumer == "go":
            cmd = ["go", "run", "."]
            run_cwd = str(consumers_dir / "go")  # go.mod resolution needs the module dir
        elif consumer == "rust":
            cmd = [
                "cargo", "run",
                "--manifest-path", str(repo_root / "crates" / "voss-sdk" / "Cargo.toml"),
                "--example", "sdk_proof_consumer", "--quiet",
            ]
        else:
            raise ValueError(f"unknown sdk consumer {consumer!r}")

        try:
            cp = subprocess.run(
                cmd,
                env=consumer_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                cwd=run_cwd,
            )
            consumer_result = json.loads(cp.stdout.strip().splitlines()[-1])
            return consumer_result.get("final", "")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
            return ""
    finally:
        if proc_server.stdin:
            proc_server.stdin.close()  # EOF heartbeat → server self-terminates
        try:
            proc_server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc_server.kill()


# sdk:python proves the docs/sdk.md public embedder surface (D-04). It is
# in-process like `internal` but restricts itself to voss.harness/voss_runtime
# public __all__ symbols; PlainRenderer + make_toolset are the documented M7
# private gap (docs/sdk.md "Known gaps — NullRenderer").
async def _drive_sdk_python(
    spec: TaskSpec,
    *,
    cwd: Path,
    provider: ModelProvider,
    model: str | None,
    max_turns: int = 15,
) -> str:
    """Drive one turn via the public voss.harness embedder API; return final."""
    from voss.harness import PermissionGate, run_turn  # public __all__
    from voss.harness.render import PlainRenderer  # private — documented M7 SDK gap (docs/sdk.md "Known gaps — NullRenderer")
    from voss.harness.tools import make_toolset  # private — runner-internal; acceptable (same path as _drive_task)
    from voss_runtime import EpisodicMemory, configure, get_config  # public

    prev_cfg = get_config()
    configure(max_iterations=max_turns)
    try:
        permissions = PermissionGate(mode=spec.mode, auto_yes=spec.auto_approve_edits)
        result = await run_turn(
            spec.prompt,
            tools=make_toolset(cwd, background_indexing=False),
            cwd=cwd,
            renderer=PlainRenderer(),
            model=model,
            provider=provider,
            history=EpisodicMemory(capacity=40),
            permissions=permissions,
        )
    finally:
        configure(max_iterations=prev_cfg.max_iterations)
    return result.final


async def _drive_resume(
    record: SessionRecord,
    spec: TaskSpec,
    *,
    cwd: Path,
    provider: ModelProvider,
    model: str | None,
    permissions: PermissionGate,
    net_session: NetSession | None = None,
    max_turns: int = 15,
) -> tuple[SessionRecord, str, bool]:
    history = EpisodicMemory(capacity=40)
    prev_cfg = get_config()
    configure(max_iterations=max_turns)
    try:
        task = asyncio.create_task(
            run_turn(
                spec.prompt,
                tools=make_toolset(cwd, net=net_session, background_indexing=False),
                cwd=cwd,
                renderer=PlainRenderer(),
                model=model,
                provider=provider,
                history=history,
                permissions=permissions,
                session_id=record.id,
            )
        )
        await asyncio.sleep(RESUME_CANCEL_DELAY_S)
        task.cancel()
        try:
            result = await task
            _add_run(record, result)
        except asyncio.CancelledError:
            pass

        save(record, history)
        record, history = load(record.id, cwd=cwd)
        result = await run_turn(
            spec.prompt,
            tools=make_toolset(cwd, net=net_session, background_indexing=False),
            cwd=cwd,
            renderer=PlainRenderer(),
            model=model,
            provider=provider,
            history=history,
            permissions=permissions,
            session_id=record.id,
        )
        _add_run(record, result)
    finally:
        configure(max_iterations=prev_cfg.max_iterations)
    capped = bool(
        record.runs
        and record.runs[-1].get("exit_reason") == "max-iter"
    )
    return record, result.final, capped


async def _drive_task(
    task_id: str,
    spec: TaskSpec,
    *,
    cwd: Path,
    provider: ModelProvider,
    model: str | None,
    stub: bool = False,
    max_turns: int = 15,
    auth_pref: str = "auto",
) -> tuple[SessionRecord, str, str | None, bool]:
    record = SessionRecord.new(cwd=cwd, model=_record_model(model), name=task_id)
    permissions = PermissionGate(mode=spec.mode, auto_yes=spec.auto_approve_edits)
    net_session = _make_stub_net_session(spec, stub=stub)
    capped = False
    try:
        if spec.surface == "cli:do":
            final, crash_reason, capped = await _drive_cli_do(spec, cwd, auth=auth_pref)
            return record, final, crash_reason, capped
        if spec.surface == "cli:chat":
            final, crash_reason, capped = await _drive_cli_chat(spec, cwd, auth=auth_pref)
            return record, final, crash_reason, capped
        if spec.surface == "cli:edit":
            final, crash_reason, capped = await _drive_cli_edit(spec, cwd, auth=auth_pref)
            return record, final, crash_reason, capped
        if spec.surface == "serve":
            final, crash_reason, capped = await _drive_serve(
                spec,
                cwd,
                permission_choice=spec.permission_choice,
                auth=auth_pref,
                model=None if stub else model,
            )
            return record, final, crash_reason, capped
        if spec.surface == "sdk:python":
            final = await _drive_sdk_python(
                spec, cwd=cwd, provider=provider, model=model, max_turns=max_turns
            )
            return record, final, None, False
        if spec.surface in ("sdk:ts", "sdk:go", "sdk:rust"):
            final = await _drive_sdk_client(
                spec,
                cwd=cwd,
                consumer=spec.surface.split(":")[1],
                auth=auth_pref,
                model=None if stub else model,
            )
            return record, final, None, False
        if task_id.startswith("05-"):
            record, final, capped = await _drive_resume(
                record,
                spec,
                cwd=cwd,
                provider=provider,
                model=model,
                permissions=permissions,
                net_session=net_session,
                max_turns=max_turns,
            )
        else:
            prev_cfg = get_config()
            configure(max_iterations=max_turns)
            try:
                result = await run_turn(
                    spec.prompt,
                    tools=make_toolset(
                        cwd, net=net_session, background_indexing=False
                    ),
                    cwd=cwd,
                    renderer=PlainRenderer(),
                    model=model,
                    provider=provider,
                    permissions=permissions,
                    session_id=record.id,
                )
            finally:
                configure(max_iterations=prev_cfg.max_iterations)
            _add_run(record, result)
            final = result.final
            if result.run and result.run.exit_reason == "max-iter":
                capped = True
    except Exception as exc:  # noqa: BLE001 - eval records failures as rows
        return record, "", f"{type(exc).__name__}: {str(exc)[:300]}", False
    finally:
        if net_session is not None:
            await net_session.aclose()
    return record, final, None, capped


def _build_provider_from_resolution(res: auth_mod.Resolution) -> ModelProvider:
    """Mirror cli._resolve_auth_or_die / server._resolve_provider provider selection."""
    from voss_runtime.providers import LiteLLMProvider

    from voss.harness.claude_agent_provider import ClaudeAgentProvider
    from voss.harness.providers import OpenAIOAuthProvider

    if res.source == "claude-agent":
        cfg = get_config()
        if not cfg.default_model.startswith("claude"):
            configure(default_model="claude-sonnet-4-5")
        return ClaudeAgentProvider(cli_path=res.cli_path)
    if res.source == "codex-oauth":
        cfg = get_config()
        if not cfg.default_model.startswith("gpt-5."):
            configure(default_model="gpt-5.5")
        return OpenAIOAuthProvider(res.codex_oauth)  # type: ignore[arg-type]
    if res.source in ("env-openai", "voss-openai", "codex"):
        if res.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", res.openai_api_key)
        cfg = get_config()
        if cfg.default_model.startswith("claude"):
            configure(default_model="gpt-4o")
    return LiteLLMProvider()


def _provider_for_eval(*, stub: bool, auth_pref: str) -> tuple[ModelProvider, auth_mod.Resolution | None]:
    if stub:
        return StubProvider(), None
    res = auth_mod.resolve(auth_pref, role="runner")
    if res.source == "none":
        click.echo(NO_CREDS_MESSAGE, err=True)
        raise click.exceptions.Exit(code=2)
    return _build_provider_from_resolution(res), res


def _judge_provider_for_eval(*, auth_pref: str) -> ModelProvider | None:
    res = auth_mod.resolve(auth_pref, role="judge")
    if res.source == "none":
        return None
    return _build_provider_from_resolution(res)


def _provider_for_task(
    *,
    default_provider: ModelProvider,
    spec: TaskSpec,
    stub: bool,
) -> ModelProvider:
    if stub or spec.provider is None:
        return default_provider
    if not has_provider(spec.provider):
        raise click.UsageError(f"unknown eval provider {spec.provider!r}")
    return get_provider(spec.provider)


async def _run_suite_async(
    *,
    tasks: list[tuple[str, TaskSpec]],
    suite_root: Path,
    runs_path: Path,
    default_provider: ModelProvider,
    judge_provider: ModelProvider | None,
    stub: bool,
    live: bool,
    k: int,
    model: str | None,
    judge_model: str | None,
    max_turns: int,
    auth_pref: str = "auto",
    toolchains: dict[str, str | None] | None = None,
) -> None:
    """Drive + judge all tasks on one event loop (httpx clients are loop-bound)."""
    toolchains = toolchains or {}
    for task_id, spec in tasks:
        for run_idx in range(k):
            started_at = _now_iso()
            # Skip guard (EVGLD-05): lang prefix maps to an absent toolchain →
            # record a skip row (gate_pass=None, NEVER False) and continue
            # before any fixture copy or model call.
            lang = task_id.split("-")[0] if "-" in task_id else None
            if lang in toolchains and toolchains[lang] is None:
                _append_row(
                    runs_path,
                    {
                        "task_id": task_id,
                        "run_idx": run_idx,
                        "success": None,
                        "skipped": True,
                        "skip_reason": "toolchain-absent",
                        "gate_pass": None,
                        "capped": False,
                        "checks": [],
                        "cost_usd": None,
                        "confidence": None,
                        "duration_s": 0.0,
                        "judge_verdict": "skipped",
                        "judge_confidence": 0.0,
                        "judge_rationale": f"skipped: toolchain-absent ({lang})",
                        "provider": "n/a",
                        "model": "n/a",
                        "judge_model": "n/a",
                        "live": live,
                        "seed": run_idx,
                        "voss_version": VOSS_VERSION,
                        "started_at": started_at,
                        "input_tokens": 0,
                        "surface": spec.surface,
                    },
                )
                continue
            start = time.monotonic()
            with tempfile.TemporaryDirectory(prefix=f"voss-eval-{task_id}-") as tmp:
                cwd = _prepare_fixture(suite_root / task_id, Path(tmp))
                provider = _provider_for_task(
                    default_provider=default_provider,
                    spec=spec,
                    stub=stub,
                )
                model_eff = (
                    "__stub__"
                    if stub
                    else (spec.model or model or get_config().default_model)
                )
                if stub:
                    judge_model_eff = judge_model or model_eff or get_config().default_model
                else:
                    judge_model_eff = judge_model or get_eval_judge_model()
                if not stub and judge_model_eff == model_eff:
                    click.echo(
                        f"voss eval: judge model == actor model ({judge_model_eff!r}); proceeding",
                        err=True,
                    )
                if "web_fetch" in spec.tools:
                    configure(allow_net=True)
                record, final, crash_reason, capped = await _drive_task(
                    task_id,
                    spec,
                    cwd=cwd,
                    provider=provider,
                    model=model_eff,
                    stub=stub,
                    max_turns=max_turns,
                    auth_pref=auth_pref,
                )
                diff = _file_diff(cwd)
                # After diff (never pollutes the judge's file_diff input), before
                # checks (model output is check-addressable for every surface).
                (cwd / ".voss-eval-final.txt").write_text(final or "")
                gate_pass, check_results = _run_checks(spec.checks, cwd)
                cost_usd, confidence = _extract_signals(record)

                verdict = None
                judge_verdict = "skipped"
                judge_rationale = ""
                if crash_reason is None and not capped and judge_provider is not None:
                    try:
                        verdict, judge_verdict = await judge_run(
                            provider=judge_provider,
                            model=judge_model_eff,
                            task_prompt=spec.prompt,
                            final=final,
                            file_diff=diff if "file_diff" in spec.judge_inputs else "",
                            rubric=spec.rubric,
                        )
                    except Exception as exc:  # noqa: BLE001 - eval records judge failures as rows
                        judge_verdict = "error"
                        judge_rationale = f"judge error: {type(exc).__name__}: {str(exc)[:300]}"

                if crash_reason or capped:
                    success = False
                elif not gate_pass:
                    success = False
                elif verdict:
                    success = verdict.verdict == "pass"
                else:
                    success = None

                row = {
                    "task_id": task_id,
                    "run_idx": run_idx,
                    "success": success,
                    "cost_usd": cost_usd,
                    "confidence": confidence,
                    "duration_s": round(time.monotonic() - start, 3),
                    "judge_verdict": judge_verdict,
                    "judge_confidence": verdict.confidence if verdict else 0.0,
                    "judge_rationale": (
                        verdict.rationale if verdict else (crash_reason or judge_rationale)
                    ),
                    "provider": provider.__class__.__name__,
                    "model": model_eff,
                    "judge_model": judge_model_eff,
                    "live": live,
                    "seed": run_idx,
                    "voss_version": VOSS_VERSION,
                    "started_at": started_at,
                    "gate_pass": gate_pass,
                    "capped": capped,
                    "checks": check_results,
                    "input_tokens": _sum_input_tokens(record),
                    "surface": spec.surface,
                    "friction": friction(record),
                }
                _append_row(runs_path, row)


def run_suite(
    *,
    suite: str = "golden",
    stub: bool = False,
    live: bool = False,
    k: int = 1,
    out: Path | None = None,
    out_dir: Path | None = None,
    judge_model: str | None = None,
    task: str | None = None,
    task_id: str | None = None,
    auth_pref: str = "auto",
    model: str | None = None,
    max_turns: int | None = None,
    require_all_toolchains: bool = False,
) -> Path:
    if k < 1:
        raise click.UsageError("-k must be at least 1")
    if live and stub:
        raise click.UsageError("--live cannot be combined with --stub")

    project_root = Path.cwd()
    out = out or out_dir or project_root / ".voss" / "eval" / _run_dir_name()
    task = task or task_id
    suite_root = project_root / SUITE_ROOT / suite
    if not suite_root.is_dir():
        raise click.UsageError(f"eval suite not found: {suite!r}")
    tasks = load_suite(suite_root, suite=suite)
    if task is not None:
        tasks = [(task_id, spec) for task_id, spec in tasks if task_id == task]
    if not tasks:
        target = f"task {task!r}" if task is not None else f"suite {suite!r}"
        raise click.UsageError(f"no eval tasks found for {target}")

    max_turns = max_turns if max_turns is not None else get_eval_max_turns()

    # Toolchain preflight (D-03): lang prefix → required binary. A missing
    # toolchain must read as SKIPPED (or fail fast under strict), never green.
    toolchain_bins = {"py": "python3", "rust": "cargo", "ts": "node"}
    toolchains = {lang: shutil.which(bin_) for lang, bin_ in toolchain_bins.items()}
    if require_all_toolchains:
        missing = sorted(
            toolchain_bins[lang] for lang, path in toolchains.items() if path is None
        )
        if missing:
            raise click.UsageError(
                f"missing toolchains: {', '.join(missing)} (--require-all-toolchains)"
            )
    toolchain_status = " ".join(
        f"{lang}={'OK' if path else 'MISSING'}" for lang, path in toolchains.items()
    )
    click.echo(
        f"{len(tasks)} tasks · max {max_turns} turns/task · toolchains: {toolchain_status}"
    )

    default_provider, _ = _provider_for_eval(stub=stub, auth_pref=auth_pref)
    judge_provider = _judge_provider_for_eval(auth_pref=auth_pref)

    runs_path = out / "runs.jsonl"
    if runs_path.exists():
        runs_path.unlink()

    async def _run() -> None:
        try:
            await _run_suite_async(
                tasks=tasks,
                suite_root=suite_root,
                runs_path=runs_path,
                default_provider=default_provider,
                judge_provider=judge_provider,
                stub=stub,
                live=live,
                k=k,
                model=model,
                judge_model=judge_model,
                max_turns=max_turns,
                auth_pref=auth_pref,
                toolchains=toolchains,
            )
        finally:
            for provider in (default_provider, judge_provider):
                if provider is not None and hasattr(provider, "aclose"):
                    await provider.aclose()

    asyncio.run(_run())

    write_summary(runs_path, out / "summary.md")
    return out
