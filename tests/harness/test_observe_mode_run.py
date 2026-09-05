"""AC-S0-6 — a read-only turn in observe mode records the instruction hash and denies writes."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from voss.harness import instructions as instr
from voss.harness import telemetry
from voss.harness.agent import Plan, ToolCall, _run_turn_exec
from voss.harness.permissions import PermissionGate, PermissionStore
from voss.harness.providers import Done, ParsedPlan, ProviderStreamEvent, TextDelta, Usage
from voss.harness.tools import ToolEntry
from voss_runtime.tools import ToolDescriptor


def _tool(name: str, *, mutating: bool, calls: list[str]) -> ToolEntry:
    async def _impl(**_kw: Any) -> str:
        calls.append(name)
        return f"{name}-ok"

    desc = ToolDescriptor(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": []},
        func=_impl,
    )
    return ToolEntry(descriptor=desc, is_mutating=mutating, group="fs")


def _plan(steps: list[dict], *, done: str = "") -> Plan:
    return Plan(
        rationale="r",
        steps=[ToolCall(**s) for s in steps],
        confidence=0.9,
        final_when_done=done,
        open_question=None,
    )


@dataclass
class _Provider:
    scripts: list[list[ProviderStreamEvent]]
    stream_calls: list[dict] = field(default_factory=list)
    _i: int = 0

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        script = self.scripts[self._i]
        self._i += 1

        async def _gen():
            for ev in script:
                yield ev

        return _gen()

    async def complete(self, **kwargs):
        from voss_runtime.providers.base import ProviderResponse

        return ProviderResponse(text="", model="stub", prompt_tokens=0, completion_tokens=0,
                                cost_usd=0.0, raw={}, parsed=None)

    def count_tokens(self, *, text: str, model: str) -> int:
        return max(len(text) // 4, 1)


@dataclass
class _Renderer:
    tool_calls: list[tuple] = field(default_factory=list)

    def banner(self, **kw): pass
    def show_user(self, task): pass
    def show_thinking(self, label): pass
    def show_plan(self, plan, *, cost_usd): pass
    def show_tool_call(self, call_id, name, args, summary, state, **kw):
        self.tool_calls.append((name, state, summary))
    def show_clarify(self, question, confidence): pass
    def show_final(self, text, *, confidence, cost_usd): pass
    def stream_delta(self, text): pass
    def finalize_stream(self, **kw): pass
    def status(self, **kw): pass
    def show_cognition(self, **kw): pass
    def show_cognition_overflow(self, **kw): pass
    def show_principles_overflow(self, **kw): pass
    def show_instructions_overflow(self, **kw): pass
    def show_warning(self, msg): pass


def _script(plan: Plan) -> list[ProviderStreamEvent]:
    return [TextDelta(text="."), ParsedPlan(plan=plan),
            Usage(prompt_tokens=5, completion_tokens=2, cost_usd=0.0), Done(stop_reason="end_turn")]


@pytest.fixture(autouse=True)
def _telemetry():
    telemetry.begin_turn()
    yield
    telemetry.clear_turn()


@pytest.mark.asyncio
async def test_ac_s0_6_observe_turn_reads_denies_writes_records_hash(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Always run tests.\n", encoding="utf-8")
    calls: list[str] = []
    tools = {
        "fs_read": _tool("fs_read", mutating=False, calls=calls),
        "fs_write": _tool("fs_write", mutating=True, calls=calls),
    }
    gate = PermissionGate(mode="observe", store=PermissionStore(cwd=tmp_path))
    gate.prompt_fn = lambda *a, **k: pytest.fail("prompt in observe mode")
    provider = _Provider(scripts=[
        _script(_plan([
            {"name": "fs_read", "args": {"path": "AGENTS.md"}, "why": "look"},
            {"name": "fs_write", "args": {"path": "x.txt", "content": "no"}, "why": "try"},
        ])),
        _script(_plan([], done="observed")),
    ])
    renderer = _Renderer()

    result = await _run_turn_exec(
        "list files",
        tools=tools,
        cwd=tmp_path,
        renderer=renderer,
        provider=provider,
        model="stub-model",
        permissions=gate,
        session_id="observe-test",
    )

    assert calls == ["fs_read"]
    assert not (tmp_path / "x.txt").exists()
    assert result.run.instructions_hash == instr.load(tmp_path).bundle_hash
    assert result.run.instructions_files == ["AGENTS.md"]
    denied = [c for c in renderer.tool_calls if c[0] == "fs_write" and "denied" in str(c[2])]
    assert denied, renderer.tool_calls
    prompt_blob = json.dumps(provider.stream_calls[0], default=str)
    assert "## Instructions" in prompt_blob
    assert "Always run tests." in prompt_blob
