"""T1-03 Task 1: AnthropicOAuthProvider.stream() — SSE decode + OAuth refresh + cancel safety."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx
import pytest

from voss.harness import auth as A
from voss.harness.agent import Plan
from voss.harness.providers import (
    AnthropicOAuthProvider,
    Done,
    ParsedPlan,
    TextDelta,
    ToolUseEnd,
    ToolUseStart,
    Usage,
)


FIXTURE = Path(__file__).parent / "fixtures" / "anthropic_stream_plan.sse"


def _creds(expires_in: int = 3600) -> A.AnthropicOAuthCreds:
    return A.AnthropicOAuthCreds(
        access_token="sk-ant-oat01-A",
        refresh_token="sk-ant-ort01-R",
        expires_at_ms=int((time.time() + expires_in) * 1000),
        subscription_type="max",
    )


def _sse_response(body_bytes: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        content=body_bytes,
        headers={"content-type": "text/event-stream"},
    )


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_stream_emits_documented_event_sequence() -> None:
    body = FIXTURE.read_bytes()
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = req.content.decode()
        captured["headers"] = dict(req.headers)
        return _sse_response(body)

    p = AnthropicOAuthProvider(_creds(), client=_mock_client(handler))
    events = []
    async for ev in p.stream(
        messages=[{"role": "user", "content": "hi"}],
        model="claude-sonnet-4-5",
        response_format=Plan,
    ):
        events.append(ev)

    # Documented sequence: TextDelta*3, ToolUseStart, ToolUseDelta*2,
    # ToolUseEnd, Usage, ParsedPlan, Done.
    types = [type(e).__name__ for e in events]
    assert types == [
        "TextDelta",
        "TextDelta",
        "TextDelta",
        "ToolUseStart",
        "ToolUseDelta",
        "ToolUseDelta",
        "ToolUseEnd",
        "Usage",
        "ParsedPlan",
        "Done",
    ]

    text_chunks = [e.text for e in events if isinstance(e, TextDelta)]
    assert "".join(text_chunks) == "Hello world"

    tus = next(e for e in events if isinstance(e, ToolUseStart))
    assert tus.name == "submit_response"
    assert tus.id == "tu_01"

    tues = [e for e in events if isinstance(e, ToolUseEnd)]
    assert len(tues) == 1 and tues[0].id == "tu_01"

    usage = next(e for e in events if isinstance(e, Usage))
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50

    parsed = next(e for e in events if isinstance(e, ParsedPlan))
    assert isinstance(parsed.plan, Plan)
    assert parsed.plan.rationale == "test rationale"
    assert parsed.plan.steps == []
    assert parsed.plan.confidence == pytest.approx(0.92)
    assert parsed.plan.final_when_done == "done"

    done = events[-1]
    assert isinstance(done, Done)
    assert done.stop_reason == "end_turn"

    # Request shape sanity: stream=true and oauth-2025-04-20 beta header.
    assert '"stream":true' in captured["body"].replace(" ", "")
    assert captured["headers"].get("anthropic-beta") == A.ANTHROPIC_OAUTH_BETA


@pytest.mark.asyncio
async def test_stream_refreshes_on_401(monkeypatch) -> None:
    body = FIXTURE.read_bytes()
    call_count = {"n": 0}
    refresh_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(401, content=b'{"error":"unauthorized"}')
        return _sse_response(body)

    refreshed_creds = A.AnthropicOAuthCreds(
        access_token="NEW",
        refresh_token="NEWR",
        expires_at_ms=int((time.time() + 3600) * 1000),
        subscription_type="max",
    )

    def fake_refresh(creds):
        refresh_calls["n"] += 1
        return refreshed_creds

    monkeypatch.setattr("voss.harness.providers.auth.refresh_anthropic", fake_refresh)

    p = AnthropicOAuthProvider(_creds(), client=_mock_client(handler))
    events = []
    async for ev in p.stream(
        messages=[{"role": "user", "content": "hi"}],
        model="claude-sonnet-4-5",
        response_format=Plan,
    ):
        events.append(ev)

    assert refresh_calls["n"] == 1
    assert call_count["n"] == 2
    # Final event sequence still includes ParsedPlan + Done.
    assert any(isinstance(e, ParsedPlan) for e in events)
    assert isinstance(events[-1], Done)
    # Provider creds now point at refreshed token.
    assert p.creds.access_token == "NEW"


@pytest.mark.asyncio
async def test_stream_cancel_closes_connection() -> None:
    """Mid-stream aclose() on the generator runs the async-with __aexit__,
    which closes the httpx response. CountingStream counts close calls."""

    close_count = {"n": 0}

    class CountingStream(httpx.AsyncByteStream):
        def __init__(self, chunks: list[bytes]):
            self._chunks = chunks

        async def __aiter__(self):
            for c in self._chunks:
                await asyncio.sleep(0)
                yield c

        async def aclose(self) -> None:
            close_count["n"] += 1

    chunks = [
        b'event: message_start\ndata: {"type":"message_start","message":'
        b'{"id":"m","model":"x","usage":{"input_tokens":0,"output_tokens":0}}}\n\n',
        b'event: content_block_start\ndata: {"type":"content_block_start",'
        b'"index":0,"content_block":{"type":"text","text":""}}\n\n',
        b'event: content_block_delta\ndata: {"type":"content_block_delta",'
        b'"index":0,"delta":{"type":"text_delta","text":"hi"}}\n\n',
    ] * 50

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=CountingStream(chunks),
            headers={"content-type": "text/event-stream"},
        )

    p = AnthropicOAuthProvider(_creds(), client=_mock_client(handler))

    gen = p.stream(
        messages=[{"role": "user", "content": "hi"}],
        model="claude-sonnet-4-5",
        response_format=Plan,
    )
    seen_text = False
    async for ev in gen:
        if isinstance(ev, TextDelta):
            seen_text = True
            break

    assert seen_text, "stream should have produced at least one TextDelta"
    await gen.aclose()

    # async-with around resp guaranteed aclose() ran on the underlying stream.
    assert close_count["n"] >= 1


@pytest.mark.asyncio
async def test_stream_cancel_via_task_does_not_leak() -> None:
    """asyncio.CancelledError inside the consumer task propagates without
    leaving the generator dangling — gen.aclose runs via async-with exit."""

    close_count = {"n": 0}

    class CountingStream(httpx.AsyncByteStream):
        def __init__(self, chunks: list[bytes]):
            self._chunks = chunks

        async def __aiter__(self):
            for c in self._chunks:
                await asyncio.sleep(0)
                yield c

        async def aclose(self) -> None:
            close_count["n"] += 1

    chunks = [
        b'event: content_block_start\ndata: {"type":"content_block_start",'
        b'"index":0,"content_block":{"type":"text","text":""}}\n\n',
        b'event: content_block_delta\ndata: {"type":"content_block_delta",'
        b'"index":0,"delta":{"type":"text_delta","text":"x"}}\n\n',
    ] * 100

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=CountingStream(chunks),
            headers={"content-type": "text/event-stream"},
        )

    p = AnthropicOAuthProvider(_creds(), client=_mock_client(handler))
    gen = p.stream(
        messages=[{"role": "user", "content": "hi"}],
        model="claude-sonnet-4-5",
        response_format=Plan,
    )

    async def consume():
        try:
            async for _ in gen:
                pass
        finally:
            await gen.aclose()

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let task start streaming
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert close_count["n"] >= 1
