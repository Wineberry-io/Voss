"""Skill-execution bridge for the MCP server (M12-03).

Thin adapter: given a skill id + `args: list[str]`, build a `SimpleNamespace`
ctx satisfying every `SkillEntry.handler` caller's expectations
(`ctx.cwd`/`provider`/`history`/`record`/`renderer`/`tools`/`gate`/
`skill_registry`), run the handler in a worker thread with stdout captured,
and return the captured text.

D-05: the server's `provider` reference is passed through, so a skill that
runs `run_turn` charges the SERVER's configured provider, not the calling
MCP host. M12-04 surfaces this in `voss mcp serve --help`.

Decoupled from T7's concrete skill set: imports NO `voss.harness.skills.*`
module; consumes only the `SkillEntry.handler` callable from the passed
registry. Adding/removing skills requires zero edits here.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Awaitable, Callable


def make_skill_dispatch(
    *,
    cwd: Path,
    provider,
    history,
    record,
    renderer,
    tools,
    gate,
    skill_registry,
) -> Callable[[str, list[str]], Awaitable[str]]:
    async def dispatch(name: str, args: list[str]) -> str:
        entry = skill_registry.get(name)
        if entry is None:
            raise KeyError(f"unknown skill: {name}")
        ctx = SimpleNamespace(
            cwd=cwd,
            provider=provider,
            history=history,
            record=record,
            renderer=renderer,
            tools=tools,
            gate=gate,
            skill_registry=skill_registry,
        )
        buf = io.StringIO()

        def _run() -> None:
            with contextlib.redirect_stdout(buf):
                entry.handler(ctx, list(args))

        # T-M12-03-02: run the sync handler in a worker thread so a blocking
        # asyncio.run(run_turn(...)) inside an agentic skill cannot deadlock
        # the server's event loop.
        await asyncio.to_thread(_run)
        return buf.getvalue()

    return dispatch
