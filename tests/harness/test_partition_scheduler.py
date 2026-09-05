"""T2-03 / PAR-01 + PAR-02 + PAR-06: partition scheduler tests.

Covers:
- Author-order partition correctness ([R, W, R, R] → [R],[W],[R,R])
- Semaphore cap enforcement (peak in-flight <= cap)
- BatchInvariantError on synthetic mutating-in-batch
- batch.start / batch.end telemetry on multi-step batches only
- recorder.begin_batch / end_batch wiring on multi-step batches only
- Per-step tool.call/tool.result preserved inside batches
- Return contract (length + author order + failure-slot strings)
- Cancellation discipline (outer cancel reaches in-flight reads)
- _run_turn_exec exit_reason="batch-invariant" finalize path
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import voss.harness.agent as agent_mod
from voss.harness import telemetry as telemetry_mod
from voss.harness.agent import (
    BatchInvariantError,
    Plan,
    ToolCall,
    _dispatch_read_batch,
    _run_step_loop,
    _run_turn_exec,
)
from voss.harness.permissions import PermissionGate
from voss.harness.recorder import RunRecorder
from voss.harness.tools import ToolEntry
from voss_runtime._config import configure, reset_config
from voss_runtime.tools import ToolDescriptor


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class NullRenderer:
    """Minimal Renderer stub. Records tool_call invocations for assertions."""

    tool_calls: list[tuple] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)
    finalize_calls: list[dict] = field(default_factory=list)

    def show_tool_call(self, call_id, name, args, summary, state, **kw):
        self.tool_calls.append((name, args, summary, state))

    def show_thinking(self, *a, **kw): pass
    def show_plan(self, *a, **kw): pass
    def show_clarify(self, *a, **kw): pass
    def show_final(self, *a, **kw): pass
    def show_cognition(self, *a, **kw): pass
    def show_cognition_overflow(self, *a, **kw): pass
    def show_warning(self, *a, **kw): pass
    def status(self, *a, **kw): pass

    def stream_delta(self, text):
        self.deltas.append(text)

    def finalize_stream(self, **kw):
        self.finalize_calls.append(kw)


def _mk_tool(
    name: str,
    *,
    is_mutating: bool,
    result: str = "",
    sleep_s: float = 0.0,
    counter: list[int] | None = None,
    peak: list[int] | None = None,
    start_event: asyncio.Event | None = None,
    started: list[str] | None = None,
    done: list[str] | None = None,
) -> ToolEntry:
    """Build a ToolEntry whose tool body optionally:
    - awaits sleep_s (lets us observe interleaving)
    - increments `counter[0]` on enter / decrements on exit; tracks peak
    - logs name into `started`/`done` lists (author-order observations)
    - awaits `start_event` to coordinate cancellation tests
    """

    async def _impl() -> str:
        if started is not None:
            started.append(name)
        if counter is not None:
            counter[0] += 1
            if peak is not None and counter[0] > peak[0]:
                peak[0] = counter[0]
        try:
            if start_event is not None:
                await start_event.wait()
            if sleep_s > 0.0:
                await asyncio.sleep(sleep_s)
        finally:
            if counter is not None:
                counter[0] -= 1
        if done is not None:
            done.append(name)
        return result or f"ok:{name}"

    desc = ToolDescriptor(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}, "required": []},
        func=_impl,
    )
    return ToolEntry(descriptor=desc, is_mutating=is_mutating, group="fs")


def _steps(*names: str) -> list[ToolCall]:
    return [ToolCall(name=n, args={}, why="") for n in names]


@pytest.fixture(autouse=True)
def _reset_runtime():
    reset_config()
    yield
    reset_config()


@pytest.fixture(autouse=True)
def _reset_telemetry():
    telemetry_mod.begin_turn()
    yield
    telemetry_mod.clear_turn()


# ---------------------------------------------------------------------------
# Partition correctness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partition_read_write_read_read() -> None:
    """[R_a, W_b, R_c, R_d]: A < B < (C, D)."""
    started: list[str] = []
    done: list[str] = []
    tools = {
        "R_a": _mk_tool("R_a", is_mutating=False, sleep_s=0.02, started=started, done=done),
        "W_b": _mk_tool("W_b", is_mutating=True, sleep_s=0.02, started=started, done=done),
        "R_c": _mk_tool("R_c", is_mutating=False, sleep_s=0.05, started=started, done=done),
        "R_d": _mk_tool("R_d", is_mutating=False, sleep_s=0.05, started=started, done=done),
    }
    plan = _steps("R_a", "W_b", "R_c", "R_d")
    results = await _run_step_loop(plan, tools, PermissionGate(auto_yes=True), NullRenderer())

    assert results == ["ok:R_a", "ok:W_b", "ok:R_c", "ok:R_d"]
    # A must finish before B starts; B before C and D start.
    a_done = done.index("R_a")
    b_started = started.index("W_b")
    b_done = done.index("W_b")
    c_started = started.index("R_c")
    d_started = started.index("R_d")
    assert a_done < b_started
    assert b_done < c_started
    assert b_done < d_started


@pytest.mark.asyncio
async def test_partition_all_reads_one_batch() -> None:
    counter = [0]
    peak = [0]
    tools = {
        n: _mk_tool(n, is_mutating=False, sleep_s=0.03, counter=counter, peak=peak)
        for n in ("R_a", "R_b", "R_c")
    }
    results = await _run_step_loop(
        _steps("R_a", "R_b", "R_c"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
    )
    assert results == ["ok:R_a", "ok:R_b", "ok:R_c"]
    assert peak[0] == 3  # all three interleaved in one batch


@pytest.mark.asyncio
async def test_partition_all_writes_serial() -> None:
    counter = [0]
    peak = [0]
    tools = {
        n: _mk_tool(n, is_mutating=True, sleep_s=0.02, counter=counter, peak=peak)
        for n in ("W_a", "W_b", "W_c")
    }
    results = await _run_step_loop(
        _steps("W_a", "W_b", "W_c"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
    )
    assert results == ["ok:W_a", "ok:W_b", "ok:W_c"]
    assert peak[0] == 1  # never overlap


@pytest.mark.asyncio
async def test_partition_read_alone_between_writes_is_singleton() -> None:
    """[R, W, R] → 3 singletons; no multi-step batch wrappers emitted."""
    events: list[dict] = []
    original = telemetry_mod.emit

    def _spy(kind, level, msg=None, *, data=None):
        if kind.startswith("batch."):
            events.append({"kind": kind, "data": data})
        original(kind, level, msg=msg, data=data)

    telemetry_mod.emit = _spy
    try:
        tools = {
            "R_a": _mk_tool("R_a", is_mutating=False),
            "W_b": _mk_tool("W_b", is_mutating=True),
            "R_c": _mk_tool("R_c", is_mutating=False),
        }
        await _run_step_loop(
            _steps("R_a", "W_b", "R_c"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )
    finally:
        telemetry_mod.emit = original

    assert events == []  # zero batch wrappers; all three are singletons


@pytest.mark.asyncio
async def test_partition_empty_steps_returns_empty() -> None:
    result = await _run_step_loop(
        [], {}, PermissionGate(auto_yes=True), NullRenderer()
    )
    assert result == []


@pytest.mark.asyncio
async def test_partition_unknown_tool_slot_is_error_string() -> None:
    tools = {"R_a": _mk_tool("R_a", is_mutating=False)}
    plan = _steps("R_a", "missing_tool", "R_a")
    results = await _run_step_loop(
        plan, tools, PermissionGate(auto_yes=True), NullRenderer()
    )
    assert len(results) == 3
    assert results[0] == "ok:R_a"
    assert results[1].startswith("<error: unknown tool")
    assert results[2] == "ok:R_a"


# ---------------------------------------------------------------------------
# Semaphore cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semaphore_cap_enforced_at_2() -> None:
    configure(max_parallel_reads=2)
    counter = [0]
    peak = [0]
    tools = {
        n: _mk_tool(n, is_mutating=False, sleep_s=0.03, counter=counter, peak=peak)
        for n in ("a", "b", "c", "d", "e", "f")
    }
    results = await _run_step_loop(
        _steps("a", "b", "c", "d", "e", "f"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
    )
    assert len(results) == 6
    assert peak[0] <= 2


@pytest.mark.asyncio
async def test_semaphore_cap_allows_full_batch_when_high() -> None:
    configure(max_parallel_reads=8)
    counter = [0]
    peak = [0]
    tools = {
        n: _mk_tool(n, is_mutating=False, sleep_s=0.03, counter=counter, peak=peak)
        for n in ("a", "b", "c", "d", "e", "f")
    }
    await _run_step_loop(
        _steps("a", "b", "c", "d", "e", "f"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
    )
    assert peak[0] == 6


@pytest.mark.asyncio
async def test_author_order_preserved_with_variable_latency() -> None:
    # Reads finish in reverse order but results stay in author order.
    tools = {
        "a": _mk_tool("a", is_mutating=False, sleep_s=0.06, result="A"),
        "b": _mk_tool("b", is_mutating=False, sleep_s=0.03, result="B"),
        "c": _mk_tool("c", is_mutating=False, sleep_s=0.01, result="C"),
    }
    results = await _run_step_loop(
        _steps("a", "b", "c"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
    )
    assert results == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Batch invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_invariant_raises_on_mutating_in_multi_step_batch() -> None:
    """Synthetic: bypass partitioner, hand a multi-step batch with a write."""
    tools = {
        "R_a": _mk_tool("R_a", is_mutating=False),
        "W_b": _mk_tool("W_b", is_mutating=True),
    }
    results: list = [None, None]
    with pytest.raises(BatchInvariantError, match="W_b"):
        await _dispatch_read_batch(
            steps=[ToolCall(name="R_a"), ToolCall(name="W_b")],
            step_indices=[0, 1],
            tools=tools,
            gate=PermissionGate(auto_yes=True),
            renderer=NullRenderer(),
            recorder=None,
            results=results,
            cap=4,
            batch_index=0,
        )


@pytest.mark.asyncio
async def test_batch_invariant_raises_on_unknown_tool_in_multi_step_batch() -> None:
    tools = {"R_a": _mk_tool("R_a", is_mutating=False)}
    results: list = [None, None]
    with pytest.raises(BatchInvariantError, match="missing"):
        await _dispatch_read_batch(
            steps=[ToolCall(name="R_a"), ToolCall(name="missing")],
            step_indices=[0, 1],
            tools=tools,
            gate=PermissionGate(auto_yes=True),
            renderer=NullRenderer(),
            recorder=None,
            results=results,
            cap=4,
            batch_index=0,
        )


@pytest.mark.asyncio
async def test_singleton_skips_invariant_check() -> None:
    """A singleton with a mutating step does NOT raise (singletons are exempt)."""
    tools = {"W_b": _mk_tool("W_b", is_mutating=True)}
    results: list = [None]
    # batch_index=None signals singleton-via-batch (no invariant, no wrappers).
    await _dispatch_read_batch(
        steps=[ToolCall(name="W_b")],
        step_indices=[0],
        tools=tools,
        gate=PermissionGate(auto_yes=True),
        renderer=NullRenderer(),
        recorder=None,
        results=results,
        cap=4,
        batch_index=None,
    )
    assert results[0] == "ok:W_b"


@pytest.mark.asyncio
async def test_partition_classifies_by_is_mutating_not_name() -> None:
    """Tool NAMED `fs_read_evil` but is_mutating=True must flush as singleton."""
    counter = [0]
    peak = [0]
    tools = {
        "fs_read_evil": _mk_tool(
            "fs_read_evil", is_mutating=True, sleep_s=0.02, counter=counter, peak=peak
        ),
        "R_real": _mk_tool(
            "R_real", is_mutating=False, sleep_s=0.02, counter=counter, peak=peak
        ),
    }
    # If classifier matched on name, both would batch; peak would be 2.
    await _run_step_loop(
        _steps("fs_read_evil", "R_real"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
    )
    assert peak[0] == 1


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class _TelemetrySpy:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def install(self):
        self._original = telemetry_mod.emit

        def _spy(kind, level, msg=None, *, data=None):
            self.events.append({"kind": kind, "data": dict(data) if data else None})
            self._original(kind, level, msg=msg, data=data)

        telemetry_mod.emit = _spy

    def restore(self):
        telemetry_mod.emit = self._original


@pytest.mark.asyncio
async def test_telemetry_multi_step_emits_batch_start_end() -> None:
    spy = _TelemetrySpy()
    spy.install()
    try:
        tools = {n: _mk_tool(n, is_mutating=False) for n in ("a", "b", "c", "d")}
        await _run_step_loop(
            _steps("a", "b", "c", "d"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )
    finally:
        spy.restore()
    starts = [e for e in spy.events if e["kind"] == "batch.start"]
    ends = [e for e in spy.events if e["kind"] == "batch.end"]
    assert len(starts) == 1
    assert len(ends) == 1
    assert starts[0]["data"]["batch_index"] == 0
    assert starts[0]["data"]["parallel_count"] == 4
    assert starts[0]["data"]["step_indices"] == [0, 1, 2, 3]
    assert ends[0]["data"]["batch_index"] == 0
    assert ends[0]["data"]["ok_count"] == 4
    assert ends[0]["data"]["err_count"] == 0
    assert ends[0]["data"]["wall_clock_ms"] >= 0


@pytest.mark.asyncio
async def test_telemetry_singleton_emits_no_batch_wrappers() -> None:
    spy = _TelemetrySpy()
    spy.install()
    try:
        tools = {
            "W_a": _mk_tool("W_a", is_mutating=True),
            "R_b": _mk_tool("R_b", is_mutating=False),
        }
        # Each step alternates between mutating + isolated read → 2 singletons.
        await _run_step_loop(
            _steps("W_a", "R_b"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )
    finally:
        spy.restore()
    batch_events = [e for e in spy.events if e["kind"].startswith("batch.")]
    assert batch_events == []


@pytest.mark.asyncio
async def test_telemetry_per_step_events_preserved_inside_batches() -> None:
    spy = _TelemetrySpy()
    spy.install()
    try:
        tools = {n: _mk_tool(n, is_mutating=False) for n in ("a", "b", "c", "d")}
        await _run_step_loop(
            _steps("a", "b", "c", "d"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )
    finally:
        spy.restore()
    tool_calls = [e for e in spy.events if e["kind"] == "tool.call"]
    tool_results = [e for e in spy.events if e["kind"] == "tool.result"]
    assert len(tool_calls) == 4
    assert len(tool_results) == 4


@pytest.mark.asyncio
async def test_telemetry_monotonic_batch_index_across_iterations() -> None:
    """Two multi-step batches in one _run_step_loop: indices 0, 1."""
    spy = _TelemetrySpy()
    spy.install()
    try:
        tools = {
            "R_a": _mk_tool("R_a", is_mutating=False),
            "R_b": _mk_tool("R_b", is_mutating=False),
            "W_c": _mk_tool("W_c", is_mutating=True),
            "R_d": _mk_tool("R_d", is_mutating=False),
            "R_e": _mk_tool("R_e", is_mutating=False),
        }
        # [R, R] → batch 0; [W] → singleton; [R, R] → batch 1.
        await _run_step_loop(
            _steps("R_a", "R_b", "W_c", "R_d", "R_e"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )
    finally:
        spy.restore()
    starts = [e for e in spy.events if e["kind"] == "batch.start"]
    assert [e["data"]["batch_index"] for e in starts] == [0, 1]


@pytest.mark.asyncio
async def test_batch_end_ok_err_counts_on_mixed_pass_fail() -> None:
    spy = _TelemetrySpy()
    spy.install()
    try:
        async def _ok() -> str:
            return "ok:x"

        async def _boom() -> str:
            raise RuntimeError("kaboom")

        tools = {
            "good": ToolEntry(
                descriptor=ToolDescriptor(
                    name="good",
                    description="g",
                    parameters={"type": "object", "properties": {}, "required": []},
                    func=_ok,
                ),
                is_mutating=False,
                group="fs",
            ),
            "bad": ToolEntry(
                descriptor=ToolDescriptor(
                    name="bad",
                    description="b",
                    parameters={"type": "object", "properties": {}, "required": []},
                    func=_boom,
                ),
                is_mutating=False,
                group="fs",
            ),
        }
        await _run_step_loop(
            _steps("good", "bad", "good"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )
    finally:
        spy.restore()
    ends = [e for e in spy.events if e["kind"] == "batch.end"]
    assert len(ends) == 1
    assert ends[0]["data"]["ok_count"] == 2
    assert ends[0]["data"]["err_count"] == 1


# ---------------------------------------------------------------------------
# Recorder wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recorder_begin_batch_called_for_multi_step() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    tools = {n: _mk_tool(n, is_mutating=False) for n in ("a", "b", "c")}
    await _run_step_loop(
        _steps("a", "b", "c"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
        recorder=rec,
    )
    batches = rec._iterations[-1].batches
    assert len(batches) == 1
    assert batches[0].batch_index == 0
    assert batches[0].step_indices == [0, 1, 2]
    assert batches[0].parallel_count == 3
    assert batches[0].ok_count == 3
    assert batches[0].err_count == 0
    assert batches[0].wall_clock_ms >= 0


@pytest.mark.asyncio
async def test_recorder_no_begin_batch_for_singleton() -> None:
    rec = RunRecorder.start()
    rec.begin_iteration()
    tools = {
        "W_a": _mk_tool("W_a", is_mutating=True),
        "R_b": _mk_tool("R_b", is_mutating=False),
    }
    await _run_step_loop(
        _steps("W_a", "R_b"),
        tools,
        PermissionGate(auto_yes=True),
        NullRenderer(),
        recorder=rec,
    )
    assert rec._iterations[-1].batches == []


@pytest.mark.asyncio
async def test_recorder_end_batch_matches_telemetry_data() -> None:
    """end_batch's counts must equal batch.end telemetry data (single source)."""
    spy = _TelemetrySpy()
    spy.install()
    rec = RunRecorder.start()
    rec.begin_iteration()
    try:
        tools = {n: _mk_tool(n, is_mutating=False) for n in ("a", "b", "c")}
        await _run_step_loop(
            _steps("a", "b", "c"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
            recorder=rec,
        )
    finally:
        spy.restore()
    ends = [e for e in spy.events if e["kind"] == "batch.end"]
    br = rec._iterations[-1].batches[0]
    assert ends[0]["data"]["ok_count"] == br.ok_count
    assert ends[0]["data"]["err_count"] == br.err_count
    assert ends[0]["data"]["wall_clock_ms"] == br.wall_clock_ms


# ---------------------------------------------------------------------------
# Return contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_return_contract_length_and_strings() -> None:
    async def _boom() -> str:
        raise RuntimeError("kaboom")

    tools = {
        "a": _mk_tool("a", is_mutating=False),
        "bad": ToolEntry(
            descriptor=ToolDescriptor(
                name="bad",
                description="b",
                parameters={"type": "object", "properties": {}, "required": []},
                func=_boom,
            ),
            is_mutating=False,
            group="fs",
        ),
    }
    plan = _steps("a", "bad", "a", "unknown_tool")
    results = await _run_step_loop(
        plan, tools, PermissionGate(auto_yes=True), NullRenderer()
    )
    assert len(results) == 4
    assert all(isinstance(r, str) for r in results)
    assert all(r is not None for r in results)
    assert results[0] == "ok:a"
    assert results[1].startswith("<error:")
    assert results[2] == "ok:a"
    assert results[3].startswith("<error: unknown tool")


# ---------------------------------------------------------------------------
# Cancellation discipline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_propagates_to_in_flight_reads() -> None:
    """Outer task.cancel() while a multi-read batch is mid-flight propagates."""
    started: list[str] = []
    done: list[str] = []
    block = asyncio.Event()
    tools = {
        n: _mk_tool(
            n,
            is_mutating=False,
            start_event=block,
            started=started,
            done=done,
        )
        for n in ("a", "b", "c", "d")
    }

    async def _runner():
        await _run_step_loop(
            _steps("a", "b", "c", "d"),
            tools,
            PermissionGate(auto_yes=True),
            NullRenderer(),
        )

    task = asyncio.create_task(_runner())
    # Yield to let the gather schedule all children.
    for _ in range(5):
        await asyncio.sleep(0)
    assert len(started) == 4  # all 4 entered the tool body
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # None finished — block.set() was never called.
    assert done == []


# ---------------------------------------------------------------------------
# _run_turn_exec exit_reason="batch-invariant" finalize path
# ---------------------------------------------------------------------------


@dataclass
class _Recorder:
    deltas: list[str] = field(default_factory=list)
    finalize_calls: list[dict] = field(default_factory=list)
    plan_calls: list[Any] = field(default_factory=list)
    tool_calls: list[tuple] = field(default_factory=list)

    def banner(self, **kw): pass
    def show_user(self, *a, **kw): pass
    def show_thinking(self, *a, **kw): pass
    def show_plan(self, plan, *, cost_usd): self.plan_calls.append(plan)
    def show_tool_call(self, *a, **kw): self.tool_calls.append(a)
    def show_clarify(self, *a, **kw): pass
    def show_final(self, *a, **kw): pass
    def stream_delta(self, text): self.deltas.append(text)
    def finalize_stream(self, **kw): self.finalize_calls.append(kw)
    def status(self, **kw): pass
    def show_cognition(self, **kw): pass
    def show_cognition_overflow(self, **kw): pass
    def show_warning(self, msg): pass


@dataclass
class _FakeProvider:
    scripts: list[list[Any]]
    record_run_return: Any = None
    _stream_index: int = 0

    def stream(self, **kwargs):
        script = self.scripts[self._stream_index]
        self._stream_index += 1

        async def _gen():
            for ev in script:
                yield ev

        return _gen()

    async def complete(self, **kwargs):
        from voss_runtime.providers.base import ProviderResponse

        return ProviderResponse(
            text="",
            model=kwargs.get("model", "stub"),
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            raw={},
            parsed=self.record_run_return,
        )

    def count_tokens(self, *, text: str, model: str) -> int:
        return max(len(text) // 4, 1)


@pytest.mark.asyncio
async def test_exit_reason_batch_invariant_surfaces_through_run_turn_exec(
    tmp_path: Path,
) -> None:
    """Synthetic mutating-in-batch through the full _run_turn_exec path.

    We bypass the partitioner by mounting tools.get() with two non-mutating
    entries for 'fs_read' AND 'fs_write' but then DEFINE fs_write entry with
    is_mutating=True — the partitioner SHOULD split. To force a true
    invariant violation we use _dispatch_read_batch through the agent
    surface: instead, simpler — wrap _dispatch_read_batch via monkeypatch
    so it raises directly.
    """
    from voss.harness.providers import Done, ParsedPlan, TextDelta, Usage

    plan_with_steps = Plan(
        rationale="r",
        steps=[ToolCall(name="R_a"), ToolCall(name="R_b")],
        confidence=0.9,
        final_when_done="",
    )
    script = [
        TextDelta(text="..."),
        ParsedPlan(plan=plan_with_steps),
        Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001),
        Done(stop_reason="end_turn"),
    ]
    provider = _FakeProvider(scripts=[script])

    tools = {
        "R_a": _mk_tool("R_a", is_mutating=False),
        "R_b": _mk_tool("R_b", is_mutating=False),
    }
    renderer = _Recorder()

    # Force a BatchInvariantError mid-dispatch via monkeypatch.
    original_loop = agent_mod._run_step_loop

    async def _boom_loop(*a, **kw):
        raise BatchInvariantError("synthetic: step 'R_b' is mutating")

    agent_mod._run_step_loop = _boom_loop
    try:
        with pytest.raises(BatchInvariantError):
            await _run_turn_exec(
                "task",
                tools=tools,
                cwd=tmp_path,
                renderer=renderer,
                provider=provider,
                model="stub",
            )
    finally:
        agent_mod._run_step_loop = original_loop

    # Renderer surfaced the error.
    assert any("batch-invariant" in d for d in renderer.deltas)


@pytest.mark.asyncio
async def test_runrecord_accepts_batch_invariant_exit_reason() -> None:
    """EXIT_REASONS frozenset must include 'batch-invariant' (additive)."""
    from voss.harness.session import EXIT_REASONS, RunRecord

    assert "batch-invariant" in EXIT_REASONS
    rec = RunRecord(id="x", started_at="a", ended_at="b", exit_reason="batch-invariant")
    assert rec.exit_reason == "batch-invariant"
