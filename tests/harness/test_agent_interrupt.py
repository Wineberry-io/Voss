"""T1-06 Task 2: _run_turn_exec CancelledError handler."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from voss.harness import telemetry
from voss.harness.agent import Plan, _run_turn_exec
from voss.harness.providers import (
    Done,
    ParsedPlan,
    TextDelta,
    Usage,
)


@dataclass
class HangingProvider:
    """Provider whose stream() yields one TextDelta then hangs on an Event."""

    release_event: asyncio.Event
    parsed_plan: Plan
    hang_before_parsed: bool = True
    _stream_calls: int = 0

    def stream(self, **kwargs):
        self._stream_calls += 1
        plan = self.parsed_plan

        async def _gen():
            yield TextDelta(text="planning…")
            if self.hang_before_parsed:
                # Hang until cancelled.
                await self.release_event.wait()
            yield ParsedPlan(plan=plan)
            yield Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001)
            yield Done(stop_reason="end_turn")

        return _gen()

    async def complete(self, **kwargs):
        # _record_run_call uses complete(); return None semantics fast.
        from voss_runtime.providers.base import ProviderResponse

        return ProviderResponse(
            text="",
            model=kwargs.get("model", "stub"),
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            raw={},
            parsed=None,
        )

    def count_tokens(self, *, text: str, model: str) -> int:
        return 1


@dataclass
class RecordingRenderer:
    deltas: list[str] = field(default_factory=list)
    finalize_calls: list[dict] = field(default_factory=list)

    def banner(self, **kw): pass
    def show_user(self, task): pass
    def show_thinking(self, label): pass
    def show_plan(self, plan, *, cost_usd): pass
    def show_tool_call(self, *a, **k): pass
    def show_clarify(self, *a, **k): pass
    def show_final(self, *a, **k): pass
    def stream_delta(self, text): self.deltas.append(text)
    def finalize_stream(self, **kw): self.finalize_calls.append(kw)
    def status(self, **kw): pass
    def show_cognition(self, **kw): pass
    def show_cognition_overflow(self, **kw): pass
    def show_warning(self, msg): pass


@pytest.fixture(autouse=True)
def _reset_telemetry():
    telemetry.begin_turn()
    yield
    telemetry.clear_turn()


@pytest.fixture(autouse=True)
def _reset_runtime():
    from voss_runtime._config import reset_config
    reset_config()
    yield
    reset_config()


def _done_plan() -> Plan:
    return Plan(
        rationale="ok",
        steps=[],
        confidence=0.9,
        final_when_done="all done",
    )


@pytest.mark.asyncio
async def test_cancel_mid_stream_finalizes_with_interrupt(
    tmp_path: Path, monkeypatch
) -> None:
    release = asyncio.Event()
    provider = HangingProvider(release_event=release, parsed_plan=_done_plan())
    renderer = RecordingRenderer()

    # ContextVar in note_turn is task-local; spy via monkeypatch so the test
    # can observe the handler's call from the parent context.
    note_turn_calls: list[dict] = []
    real_note_turn = telemetry.note_turn

    def spy(**fields):
        note_turn_calls.append(dict(fields))
        return real_note_turn(**fields)

    monkeypatch.setattr(telemetry, "note_turn", spy)
    import voss.harness.agent as agent_mod

    monkeypatch.setattr(agent_mod.telemetry, "note_turn", spy)

    task = asyncio.create_task(
        _run_turn_exec(
            "do thing",
            tools={},
            cwd=tmp_path,
            renderer=renderer,
            provider=provider,
            model="stub",
        )
    )
    await asyncio.sleep(0.05)  # let the stream start

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert task.cancelled()
    # Telemetry recorded interrupt outcome + exit_reason.
    assert note_turn_calls, "note_turn never called"
    last = note_turn_calls[-1]
    assert last.get("outcome") == "interrupt"
    assert last.get("exit_reason") == "interrupt"


@pytest.mark.asyncio
async def test_interrupt_latency_under_100ms(tmp_path: Path) -> None:
    release = asyncio.Event()
    provider = HangingProvider(release_event=release, parsed_plan=_done_plan())

    finalize_calls: list[float] = []

    from voss.harness import recorder as recorder_mod

    real_finalize = recorder_mod.RunRecorder.finalize

    def timed_finalize(self, cwd, cost_usd, *, exit_reason=None):
        finalize_calls.append(time.monotonic())
        return real_finalize(self, cwd, cost_usd, exit_reason=exit_reason)

    recorder_mod.RunRecorder.finalize = timed_finalize  # type: ignore[assignment]
    try:
        task = asyncio.create_task(
            _run_turn_exec(
                "do thing",
                tools={},
                cwd=tmp_path,
                renderer=RecordingRenderer(),
                provider=provider,
                model="stub",
            )
        )
        await asyncio.sleep(0.05)

        cancel_t0 = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert finalize_calls, "rec.finalize should have been called by handler"
        latency = finalize_calls[-1] - cancel_t0
        assert latency < 0.1, f"finalize latency {latency:.3f}s exceeds 100ms"
    finally:
        recorder_mod.RunRecorder.finalize = real_finalize  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_no_task_leak_after_cancel(tmp_path: Path) -> None:
    release = asyncio.Event()
    provider = HangingProvider(release_event=release, parsed_plan=_done_plan())

    before = set(asyncio.all_tasks())
    task = asyncio.create_task(
        _run_turn_exec(
            "x",
            tools={},
            cwd=tmp_path,
            renderer=RecordingRenderer(),
            provider=provider,
            model="stub",
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.01)  # let any pending callbacks run

    after = set(asyncio.all_tasks()) - {asyncio.current_task()}
    leaked = (after - before) - {task}
    # task itself is settled — leaked = any extra leftover tasks.
    leaked_alive = {t for t in leaked if not t.done()}
    assert not leaked_alive, f"leaked tasks: {leaked_alive}"


@pytest.mark.asyncio
async def test_renderer_surfaces_interrupted_marker(tmp_path: Path) -> None:
    release = asyncio.Event()
    provider = HangingProvider(release_event=release, parsed_plan=_done_plan())
    renderer = RecordingRenderer()

    task = asyncio.create_task(
        _run_turn_exec(
            "x",
            tools={},
            cwd=tmp_path,
            renderer=renderer,
            provider=provider,
            model="stub",
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    joined = "".join(renderer.deltas)
    assert "interrupted" in joined
    assert any(
        call.get("role") == "system" for call in renderer.finalize_calls
    )


@pytest.mark.asyncio
async def test_cancel_between_iters_finalizes_clean(
    tmp_path: Path, monkeypatch
) -> None:
    """Cancel arriving between iterations finalizes the record with
    exit_reason='interrupt' and no open iter to close."""
    from voss_runtime._config import configure

    configure(max_iterations=2)

    note_turn_calls: list[dict] = []
    real_note_turn = telemetry.note_turn

    def spy(**fields):
        note_turn_calls.append(dict(fields))
        return real_note_turn(**fields)

    monkeypatch.setattr(telemetry, "note_turn", spy)
    import voss.harness.agent as agent_mod

    monkeypatch.setattr(agent_mod.telemetry, "note_turn", spy)

    # Provider that returns a non-done plan first, then hangs on iter 2.
    release = asyncio.Event()

    @dataclass
    class _BetweenIterProvider:
        release_event: asyncio.Event = release
        _idx: int = 0

        def stream(self, **kw):
            idx = self._idx
            self._idx += 1
            if idx == 0:
                # iter 0: simple done plan, exits loop normally — actually
                # we want a non-done plan so loop continues, then hang on
                # iter 1 to allow cancel between iters.
                plan = Plan(
                    rationale="r",
                    steps=[],
                    confidence=0.9,
                    final_when_done="",  # empty → not done → loop continues
                )

                async def _gen0():
                    yield ParsedPlan(plan=plan)
                    yield Usage(prompt_tokens=5, completion_tokens=5, cost_usd=0.0)
                    yield Done(stop_reason="end_turn")

                return _gen0()

            async def _gen1():
                await self.release_event.wait()
                yield ParsedPlan(plan=Plan(
                    rationale="r2", steps=[], confidence=0.9, final_when_done="ok"
                ))
                yield Done(stop_reason="end_turn")

            return _gen1()

        async def complete(self, **kw):
            from voss_runtime.providers.base import ProviderResponse
            return ProviderResponse(
                text="", model="stub", prompt_tokens=0, completion_tokens=0,
                cost_usd=0.0, raw={}, parsed=None,
            )

        def count_tokens(self, *, text, model):
            return 1

    task = asyncio.create_task(
        _run_turn_exec(
            "x",
            tools={},
            cwd=tmp_path,
            renderer=RecordingRenderer(),
            provider=_BetweenIterProvider(),
            model="stub",
        )
    )
    await asyncio.sleep(0.1)  # let iter 0 finish + iter 1 start
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert note_turn_calls, "note_turn never called"
    assert note_turn_calls[-1].get("exit_reason") == "interrupt"
