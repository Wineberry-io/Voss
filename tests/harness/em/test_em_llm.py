"""O5-03: em_plan call-shape — mocked provider, ParseError sentinel, L2-vocab scan."""
from __future__ import annotations


import pytest

from voss_runtime.exceptions import ParseError
from voss_runtime.providers.base import ProviderResponse

from voss.harness.em.llm import EM_SYSTEM, em_plan
from voss.harness.em.schema import CreateTicketOp, EMPlanResponse, NoopOp


class _FakeProvider:
    def __init__(self, parsed=None, *, raise_parse=False, raise_generic=False):
        self._parsed = parsed
        self._raise_parse = raise_parse
        self._raise_generic = raise_generic
        self.calls: list[dict] = []

    async def complete(self, **kw):
        self.calls.append(kw)
        if self._raise_parse:
            raise ParseError("fake parse error")
        if self._raise_generic:
            raise RuntimeError("generic boom")
        return ProviderResponse(
            text="{}", model=kw.get("model", "test"),
            prompt_tokens=1, completion_tokens=1, cost_usd=0.0,
            parsed=self._parsed,
        )

    def count_tokens(self, **kw):
        return 1


class TestEmPlanCallShape:
    @pytest.mark.asyncio
    async def test_calls_provider_once(self):
        plan = EMPlanResponse(ops=[CreateTicketOp(
            original_idea="x", worker_role="be",
        )], reasoning="ok")
        prov = _FakeProvider(parsed=plan)
        result = await em_plan(
            provider=prov, model="test-em", idea="Build API",
            snapshot="cards: 0", roster_descriptions={"backend": "API dev"},
        )
        assert len(prov.calls) == 1

    @pytest.mark.asyncio
    async def test_call_kwargs(self):
        plan = EMPlanResponse(ops=[], reasoning="")
        prov = _FakeProvider(parsed=plan)
        await em_plan(
            provider=prov, model="test-em", idea="Build API",
            snapshot="cards: 0",
        )
        call = prov.calls[0]
        assert call["model"] == "test-em"
        assert call["response_format"] is EMPlanResponse
        assert call["temperature"] == 0.0
        msgs = call["messages"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"].startswith("You are the Engineering Manager")
        assert "Build API" in msgs[1]["content"]
        assert "cards: 0" in msgs[1]["content"]

    @pytest.mark.asyncio
    async def test_returns_parsed_response(self):
        plan = EMPlanResponse(ops=[CreateTicketOp(
            original_idea="x", worker_role="be",
        )], reasoning="ok")
        prov = _FakeProvider(parsed=plan)
        result = await em_plan(
            provider=prov, model="m", idea="x", snapshot="",
        )
        assert isinstance(result, EMPlanResponse)
        assert len(result.ops) == 1


class TestEmPlanErrorHandling:
    @pytest.mark.asyncio
    async def test_parse_error_returns_noop(self):
        prov = _FakeProvider(raise_parse=True)
        result = await em_plan(provider=prov, model="m", idea="x", snapshot="")
        assert len(result.ops) == 1
        assert isinstance(result.ops[0], NoopOp)
        assert result.ops[0].reason == "parse_failure"

    @pytest.mark.asyncio
    async def test_parsed_none_returns_noop(self):
        prov = _FakeProvider(parsed=None)
        result = await em_plan(provider=prov, model="m", idea="x", snapshot="")
        assert isinstance(result.ops[0], NoopOp)
        assert result.ops[0].reason == "parse_failure"

    @pytest.mark.asyncio
    async def test_generic_exception_reraises(self):
        prov = _FakeProvider(raise_generic=True)
        with pytest.raises(RuntimeError, match="generic boom"):
            await em_plan(provider=prov, model="m", idea="x", snapshot="")


class TestEmSystemNoL2Vocab:
    """L-03: system prompt + schema descriptions contain no L2 vocab."""
    _BANNED = {"model", "cost", "token", "provider"}

    def test_em_system_no_l2_vocab(self):
        lower = EM_SYSTEM.lower()
        for word in self._BANNED:
            assert word not in lower, f"L2 vocab '{word}' found in EM_SYSTEM"
