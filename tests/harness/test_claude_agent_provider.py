"""ClaudeAgentProvider — claude-agent-sdk subprocess provider (offline, fake SDK).

All tests inject `query_fn` fakes; no claude-agent-sdk install, no subprocess,
no network. Fakes are local dataclasses duck-typing the SDK message shapes the
provider sniffs (`content` list for AssistantMessage, `total_cost_usd` for
ResultMessage).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from voss.harness.agent import Plan
from voss.harness.claude_agent_provider import (
    ClaudeAgentProvider,
    _flatten_messages,
    _subscription_env_overrides,
)
from voss.harness.providers import Done, ParsedPlan, TextDelta, Usage


# ---------------------------------------------------------------------------
# SDK message doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeTextBlock:
    text: str


@dataclass
class FakeToolUseBlock:
    name: str
    input: dict


@dataclass
class FakeAssistantMessage:
    content: list


@dataclass
class FakeResultMessage:
    total_cost_usd: Optional[float] = None
    usage: Optional[dict] = None
    is_error: bool = False
    subtype: str = "success"
    api_error_status: Optional[int] = None
    errors: Any = None
    result: Optional[str] = None
    structured_output: Any = None
    stop_reason: Optional[str] = "end_turn"


PLAN_JSON = json.dumps(
    {
        "rationale": "test rationale",
        "steps": [],
        "confidence": 0.9,
        "open_question": None,
        "final_when_done": "done",
    }
)

USAGE = {
    "input_tokens": 120,
    "output_tokens": 60,
    "cache_creation_input_tokens": 7,
    "cache_read_input_tokens": 11,
}


def _fake_query(messages: list, captured: dict | None = None):
    """Build a query_fn yielding the given message doubles."""

    async def query(*, prompt: str, options: Any):
        if captured is not None:
            captured["prompt"] = prompt
            captured["options"] = options
        for m in messages:
            yield m

    return query


def _provider(messages: list, captured: dict | None = None) -> ClaudeAgentProvider:
    return ClaudeAgentProvider(query_fn=_fake_query(messages, captured))


async def _drain(p: ClaudeAgentProvider, **kw) -> list:
    events = []
    async for ev in p.stream(
        messages=kw.pop("messages", [{"role": "user", "content": "hi"}]),
        model=kw.pop("model", "claude-sonnet-4-5"),
        **kw,
    ):
        events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Event sequence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_emits_documented_event_sequence() -> None:
    p = _provider(
        [
            FakeAssistantMessage([FakeTextBlock(PLAN_JSON)]),
            FakeResultMessage(total_cost_usd=1.23, usage=USAGE),
        ]
    )
    events = await _drain(p, response_format=Plan)
    types = [type(e).__name__ for e in events]
    assert types == ["TextDelta", "Usage", "ParsedPlan", "Done"]

    usage = next(e for e in events if isinstance(e, Usage))
    assert usage.prompt_tokens == 120
    assert usage.completion_tokens == 60
    assert usage.cache_creation_input_tokens == 7
    assert usage.cache_read_input_tokens == 11
    # Subscription turns never count as harness spend, even when the SDK
    # reports an advisory total_cost_usd.
    assert usage.cost_usd == 0.0

    parsed = next(e for e in events if isinstance(e, ParsedPlan))
    assert isinstance(parsed.plan, Plan)
    assert parsed.plan.rationale == "test rationale"

    assert isinstance(events[-1], Done)
    assert events[-1].stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_structured_output_wins_over_text() -> None:
    structured = json.loads(PLAN_JSON) | {"rationale": "from structured_output"}
    p = _provider(
        [
            FakeAssistantMessage([FakeTextBlock("not json at all")]),
            FakeResultMessage(usage=USAGE, structured_output=structured),
        ]
    )
    events = await _drain(p, response_format=Plan)
    parsed = next(e for e in events if isinstance(e, ParsedPlan))
    assert parsed.plan.rationale == "from structured_output"


@pytest.mark.asyncio
async def test_malformed_json_yields_no_parsed_plan_but_done() -> None:
    p = _provider(
        [
            FakeAssistantMessage([FakeTextBlock("{broken")]),
            FakeResultMessage(usage=USAGE),
        ]
    )
    events = await _drain(p, response_format=Plan)
    assert not any(isinstance(e, ParsedPlan) for e in events)
    assert isinstance(events[-1], Done)


@pytest.mark.asyncio
async def test_no_response_format_skips_plan_extraction() -> None:
    p = _provider(
        [
            FakeAssistantMessage([FakeTextBlock("hello")]),
            FakeResultMessage(usage=USAGE),
        ]
    )
    events = await _drain(p)
    assert [type(e).__name__ for e in events] == ["TextDelta", "Usage", "Done"]


@pytest.mark.asyncio
async def test_iterator_end_without_result_message_is_incomplete() -> None:
    p = _provider([FakeAssistantMessage([FakeTextBlock("partial")])])
    events = await _drain(p)
    assert isinstance(events[-1], Done)
    assert events[-1].stop_reason == "incomplete"


@pytest.mark.asyncio
async def test_stray_tool_use_blocks_are_ignored() -> None:
    p = _provider(
        [
            FakeAssistantMessage(
                [FakeToolUseBlock("Bash", {"cmd": "ls"}), FakeTextBlock("ok")]
            ),
            FakeResultMessage(usage=USAGE),
        ]
    )
    events = await _drain(p)
    deltas = [e for e in events if isinstance(e, TextDelta)]
    assert [d.text for d in deltas] == ["ok"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_result_raises_runtime_error_with_subtype() -> None:
    p = _provider(
        [
            FakeResultMessage(
                is_error=True,
                subtype="error_max_budget",
                result="usage limit reached",
            )
        ]
    )
    with pytest.raises(RuntimeError, match=r"error_max_budget.*usage limit reached"):
        await _drain(p)


@pytest.mark.asyncio
async def test_sdk_exception_is_wrapped_with_login_hint() -> None:
    class ProcessError(Exception):
        exit_code = 1

    async def query(*, prompt, options):
        raise ProcessError("authentication_error")
        yield  # pragma: no cover — makes this an async generator

    p = ClaudeAgentProvider(query_fn=query)
    with pytest.raises(RuntimeError, match=r"exit 1.*claude /login"):
        await _drain(p)


@pytest.mark.asyncio
async def test_missing_sdk_mentions_extra(monkeypatch) -> None:
    p = ClaudeAgentProvider()  # no seam → real import path
    import builtins

    real_import = builtins.__import__

    def block_sdk(name, *a, **kw):
        if name == "claude_agent_sdk":
            raise ImportError("nope")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", block_sdk)
    with pytest.raises(RuntimeError, match=r"voss\[claude\]"):
        await _drain(p)


# ---------------------------------------------------------------------------
# Options + prompt construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_options_lock_down_tools_and_settings() -> None:
    captured: dict = {}
    p = _provider(
        [FakeResultMessage(usage=USAGE, result=PLAN_JSON)], captured
    )
    await _drain(
        p,
        messages=[
            {"role": "system", "content": "sys A"},
            {"role": "system", "content": [{"type": "text", "text": "sys B"}]},
            {"role": "user", "content": "do the thing"},
        ],
        response_format=Plan,
    )
    opt = captured["options"]
    # Structured output needs the StructuredOutput tool round-trip plus
    # possible text-only turns first → loose runaway cap, not 1.
    assert opt.max_turns == 8
    assert opt.tools == []
    assert opt.allowed_tools == []
    assert opt.setting_sources == []
    assert opt.cwd is None
    assert opt.output_format["type"] == "json_schema"
    assert opt.output_format["schema"] == Plan.model_json_schema()
    # System messages land in system_prompt, not the prompt body.
    assert opt.system_prompt == "sys A\n\nsys B"
    assert "sys A" not in captured["prompt"]
    assert "do the thing" in captured["prompt"]


@pytest.mark.asyncio
async def test_plain_text_call_stays_single_turn() -> None:
    captured: dict = {}
    p = _provider([FakeResultMessage(usage=USAGE)], captured)
    await _drain(p)  # no response_format
    assert captured["options"].max_turns == 1
    assert captured["options"].output_format is None


@pytest.mark.asyncio
async def test_cli_path_threads_into_options() -> None:
    captured: dict = {}
    p = ClaudeAgentProvider(
        cli_path="/opt/bin/claude",
        query_fn=_fake_query([FakeResultMessage(usage=USAGE)], captured),
    )
    await _drain(p)
    assert captured["options"].cli_path == "/opt/bin/claude"


@pytest.mark.asyncio
async def test_subscription_provider_shadows_api_billing_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.example.test")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")

    captured: dict = {}
    p = ClaudeAgentProvider(
        query_fn=_fake_query([FakeResultMessage(usage=USAGE)], captured),
    )
    await _drain(p)

    opt = captured["options"]
    assert opt.env["ANTHROPIC_API_KEY"] == ""
    assert opt.env["ANTHROPIC_BASE_URL"] == ""
    assert opt.env["CLAUDE_CODE_USE_BEDROCK"] == ""


def test_subscription_env_overrides_omits_unset_keys(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    assert _subscription_env_overrides() == {}


def test_flatten_messages_markers_and_order() -> None:
    system, prompt = _flatten_messages(
        [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": [{"type": "text", "text": "u2"}]},
        ],
        want_json=True,
    )
    assert system == "S"
    assert prompt.index("<<<USER>>>\nu1") < prompt.index("<<<ASSISTANT>>>\na1")
    assert prompt.index("a1") < prompt.index("u2")
    assert prompt.rstrip().endswith("required schema.")


def test_flatten_messages_no_json_tail_without_schema() -> None:
    _, prompt = _flatten_messages([{"role": "user", "content": "hi"}])
    assert "required schema" not in prompt


# ---------------------------------------------------------------------------
# Timeout + cancellation hygiene
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_raises_and_closes_generator() -> None:
    closed = {"flag": False}

    async def slow_query(*, prompt, options):
        try:
            await asyncio.sleep(60)
            yield FakeResultMessage(usage=USAGE)
        finally:
            closed["flag"] = True

    p = ClaudeAgentProvider(query_fn=slow_query)
    with pytest.raises(RuntimeError, match="timed out after 0.01"):
        await _drain(p, timeout=0.01)
    assert closed["flag"] is True


# ---------------------------------------------------------------------------
# complete() parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_drains_stream_into_provider_response() -> None:
    p = _provider(
        [
            FakeAssistantMessage([FakeTextBlock(PLAN_JSON)]),
            FakeResultMessage(total_cost_usd=9.99, usage=USAGE),
        ]
    )
    resp = await p.complete(
        messages=[{"role": "user", "content": "hi"}],
        model="claude-sonnet-4-5",
        response_format=Plan,
    )
    assert resp.text == PLAN_JSON
    assert resp.prompt_tokens == 120
    assert resp.completion_tokens == 60
    assert resp.cost_usd == 0.0
    assert isinstance(resp.parsed, Plan)


def test_count_tokens_heuristic() -> None:
    p = ClaudeAgentProvider()
    assert p.count_tokens(text="x" * 40, model="claude-sonnet-4-5") == 10
    assert p.count_tokens(text="", model="claude-sonnet-4-5") == 1
