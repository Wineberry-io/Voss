"""T1 acceptance test suite — 12 SPEC checkboxes + 4 quantitative thresholds.

This file is the goal-backward contract for phase T1. Earlier plan tests
covered individual mechanisms; these tests assert each SPEC acceptance
checkbox from the user-visible perspective so refactors in the
implementation tests don't silently break the contract.

Run isolated: `uv run pytest -m t1 -v`.
"""
from __future__ import annotations

import asyncio
import inspect
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import voss.harness.agent as agent_mod
from voss.harness import telemetry
from voss.harness.agent import (
    HALTED_BUDGET_FINAL,
    HALTED_MAX_ITER_FINAL,
    Plan,
    ToolCall,
    _run_turn_exec,
)
from voss.harness.permissions import PermissionGate
from voss.harness.providers import (
    AnthropicOAuthProvider,
    Done,
    OpenAIOAuthProvider,
    ParsedPlan,
    ProviderStreamEvent,
    TextDelta,
    Usage,
)
from voss.harness.session import EXIT_REASONS, RunRecord
from voss.harness.tools import ToolEntry
from voss_runtime._config import configure, reset_config
from voss_runtime.tools import ToolDescriptor


pytestmark = [pytest.mark.t1, pytest.mark.acceptance]


# ---------------------------------------------------------------------------
# Shared fixtures + helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str, result: str) -> ToolEntry:
    async def _impl(**_kwargs) -> str:
        return result

    desc = ToolDescriptor(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}, "required": []},
        func=_impl,
    )
    return ToolEntry(descriptor=desc, is_mutating=name in {"fs_edit", "fs_write"}, group="fs")


def _message_content_text(content) -> str:
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return str(content or "")


def _plan(
    *,
    steps: list[dict] | None = None,
    confidence: float = 0.9,
    final_when_done: str = "",
    rationale: str = "r",
    open_question: str | None = None,
) -> Plan:
    step_objs = [ToolCall(**s) for s in (steps or [])]
    return Plan(
        rationale=rationale,
        steps=step_objs,
        confidence=confidence,
        final_when_done=final_when_done,
        open_question=open_question,
    )


@dataclass
class FakeStreamingProvider:
    scripts: list[list[ProviderStreamEvent]]
    stream_calls: list[dict] = field(default_factory=list)
    _stream_index: int = 0

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        if self._stream_index < len(self.scripts):
            script = self.scripts[self._stream_index]
        else:
            script = self.scripts[-1]
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
            parsed=None,
        )

    def count_tokens(self, *, text: str, model: str) -> int:
        return 1


@dataclass
class RecordingRenderer:
    deltas: list[tuple[float, str]] = field(default_factory=list)
    finalize_calls: list[dict] = field(default_factory=list)
    finalize_times: list[float] = field(default_factory=list)
    clarify_calls: list[tuple] = field(default_factory=list)

    def banner(self, **kw): pass
    def show_user(self, task): pass
    def show_thinking(self, label): pass
    def show_plan(self, plan, *, cost_usd): pass
    def show_tool_call(self, *a, **k): pass
    def show_clarify(self, q, c): self.clarify_calls.append((q, c))
    def show_final(self, *a, **k): pass
    def stream_delta(self, text):
        self.deltas.append((time.monotonic(), text))
    def finalize_stream(self, **kw):
        self.finalize_times.append(time.monotonic())
        self.finalize_calls.append(kw)
    def status(self, **kw): pass
    def show_cognition(self, **kw): pass
    def show_cognition_overflow(self, **kw): pass
    def show_warning(self, msg): pass


def _done_script(*, plan: Plan, cost: float = 0.001) -> list[ProviderStreamEvent]:
    return [
        TextDelta(text="…"),
        ParsedPlan(plan=plan),
        Usage(prompt_tokens=10, completion_tokens=5, cost_usd=cost),
        Done(stop_reason="end_turn"),
    ]


@pytest.fixture(autouse=True)
def _reset_telemetry():
    telemetry.begin_turn()
    yield
    telemetry.clear_turn()


@pytest.fixture(autouse=True)
def _reset_runtime():
    reset_config()
    yield
    reset_config()


@pytest.fixture
def telemetry_capture(monkeypatch):
    """Spy on telemetry.emit + note_turn, returning lists of captured calls."""
    emits: list[tuple[str, dict]] = []
    note_turns: list[dict] = []

    real_emit = telemetry.emit
    real_note = telemetry.note_turn

    def emit_spy(event_type, level="info", *, data=None, **kw):
        emits.append((event_type, dict(data or {})))
        return real_emit(event_type, level, data=data, **kw)

    def note_spy(**fields):
        note_turns.append(dict(fields))
        return real_note(**fields)

    monkeypatch.setattr(telemetry, "emit", emit_spy)
    monkeypatch.setattr(telemetry, "note_turn", note_spy)
    monkeypatch.setattr(agent_mod.telemetry, "emit", emit_spy)
    monkeypatch.setattr(agent_mod.telemetry, "note_turn", note_spy)

    return {"emits": emits, "note_turns": note_turns}


# ===========================================================================
# ITER-01 — while-loop with three exit conditions
# ===========================================================================


@pytest.mark.asyncio
async def test_iter_01_while_loop_exits_on_done(tmp_path: Path) -> None:
    done = _plan(steps=[], confidence=0.9, final_when_done="ok")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=done)])
    result = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    assert result.run.exit_reason == "done"
    assert result.run.iteration_count == 1


@pytest.mark.asyncio
async def test_iter_01_while_loop_exits_on_max_iter(tmp_path: Path) -> None:
    configure(max_iterations=3)
    never_done = _plan(steps=[], confidence=0.9, final_when_done="")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=never_done)] * 3)
    result = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    assert result.run.exit_reason == "max-iter"
    assert result.run.iteration_count == 3
    assert HALTED_MAX_ITER_FINAL in result.final  # "halted: max-iter"


@pytest.mark.asyncio
async def test_iter_01_while_loop_exits_on_budget(
    tmp_path: Path, monkeypatch
) -> None:
    never_done = _plan(steps=[], confidence=0.9, final_when_done="")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=never_done)] * 8)

    real_build = agent_mod._build_iter_rider

    def inflating(**kw):
        import sys
        ctx = sys._getframe(1).f_locals.get("ctx")
        if ctx is not None and kw.get("index", 0) >= 1:
            ctx.tokens_used = ctx.token_budget + 1
        return real_build(**kw)

    monkeypatch.setattr(agent_mod, "_build_iter_rider", inflating)
    result = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub", token_budget=1000,
    )
    assert result.run.exit_reason == "budget"
    assert HALTED_BUDGET_FINAL in result.final


# ===========================================================================
# ITER-02 — iteration N+1 receives iteration N's plan + tool_results
# ===========================================================================


@pytest.mark.asyncio
async def test_iter_02_iter_n_plus_one_receives_prior_results(
    tmp_path: Path,
) -> None:
    tool = _make_tool("fs_read", "PRIOR-RESULT-XYZ")
    iter0 = _plan(
        steps=[{"name": "fs_read", "args": {}, "why": "read"}],
        confidence=0.85, final_when_done="",
    )
    iter1 = _plan(steps=[], confidence=0.9, final_when_done="done")
    provider = FakeStreamingProvider(scripts=[
        _done_script(plan=iter0), _done_script(plan=iter1),
    ])

    await _run_turn_exec(
        "x", tools={"fs_read": tool}, cwd=tmp_path,
        renderer=RecordingRenderer(), provider=provider, model="stub",
    )

    iter1_msgs = provider.stream_calls[1]["messages"]
    flat = "\n".join(_message_content_text(m.get("content", "")) for m in iter1_msgs)
    assert "Tool results for iteration 0:" in flat
    assert "PRIOR-RESULT-XYZ" in flat


# ===========================================================================
# ITER-02 — _substitute_placeholders is gone (grep verification)
# ===========================================================================


def test_iter_02_grep_substitute_placeholders_returns_zero() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            "grep",
            "-rn",
            "--include=*.py",
            "--include=*.voss",
            "_substitute_placeholders",
            str(repo_root / "voss"),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        f"_substitute_placeholders re-introduced:\n{result.stdout}"
    )
    # Also confirm it's not a python module attribute.
    assert not hasattr(agent_mod, "_substitute_placeholders")


# ===========================================================================
# ITER-03 — both providers expose stream() + first-token latency
# ===========================================================================


def test_iter_03_anthropic_openai_stream_exist() -> None:
    assert hasattr(AnthropicOAuthProvider, "stream")
    assert hasattr(OpenAIOAuthProvider, "stream")
    sig_a = inspect.signature(AnthropicOAuthProvider.stream)
    sig_o = inspect.signature(OpenAIOAuthProvider.stream)
    expected = {"messages", "model", "response_format", "tools",
                "temperature", "max_tokens", "timeout"}
    for sig, name in ((sig_a, "Anthropic"), (sig_o, "OpenAI")):
        params = set(sig.parameters) - {"self"}
        assert params == expected, f"{name} stream() params: {params}"


@pytest.mark.asyncio
async def test_iter_03_first_token_under_500ms(tmp_path: Path) -> None:
    """First visible turn signal <=500ms after provider HTTP 200.

    Plan-phase TextDeltas are intentionally NOT rendered (the deltas are
    structured-output JSON; streaming them would leak the schema into chat
    — see the plan loop in agent.py), so the first user-visible signal is
    finalize_stream. Measure its latency instead of stream_delta.
    """
    http_200_t = [0.0]
    plan = _plan(steps=[], confidence=0.9, final_when_done="ok")

    @dataclass
    class TimedProvider:
        def stream(self, **kw):
            http_200_t[0] = time.monotonic()

            async def _gen():
                yield TextDelta(text="hello")  # first token
                yield ParsedPlan(plan=plan)
                yield Usage(prompt_tokens=1, completion_tokens=1, cost_usd=0.0)
                yield Done(stop_reason="end_turn")

            return _gen()

        async def complete(self, **kw):
            from voss_runtime.providers.base import ProviderResponse
            return ProviderResponse(
                text="", model="stub", prompt_tokens=0, completion_tokens=0,
                cost_usd=0.0, raw={}, parsed=None,
            )

        def count_tokens(self, *, text, model):
            return 1

    renderer = RecordingRenderer()
    await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=renderer,
        provider=TimedProvider(), model="stub",
    )
    assert not renderer.deltas, "plan-phase deltas must not be rendered (schema leak)"
    assert renderer.finalize_times, "no finalize_stream emitted"
    latency = renderer.finalize_times[0] - http_200_t[0]
    assert latency <= 0.5, f"first-signal latency {latency:.3f}s > 500ms"


# ===========================================================================
# ITER-04 — interrupt cancels + finalizes <=100ms + exit_reason="interrupt"
# ===========================================================================


@pytest.mark.asyncio
async def test_iter_04_interrupt_finalizes_within_100ms(
    tmp_path: Path, monkeypatch
) -> None:
    release = asyncio.Event()
    plan = _plan(steps=[], confidence=0.9, final_when_done="ok")

    @dataclass
    class HangingProvider:
        def stream(self, **kw):
            async def _gen():
                yield TextDelta(text="planning…")
                await release.wait()
                yield ParsedPlan(plan=plan)
                yield Usage(prompt_tokens=1, completion_tokens=1, cost_usd=0.0)
                yield Done(stop_reason="end_turn")
            return _gen()

        async def complete(self, **kw):
            from voss_runtime.providers.base import ProviderResponse
            return ProviderResponse(
                text="", model="stub", prompt_tokens=0, completion_tokens=0,
                cost_usd=0.0, raw={}, parsed=None,
            )

        def count_tokens(self, *, text, model):
            return 1

    finalize_times: list[float] = []
    note_turns: list[dict] = []
    from voss.harness import recorder as recorder_mod
    real_finalize = recorder_mod.RunRecorder.finalize

    def timed_finalize(self, cwd, cost_usd, *, exit_reason=None):
        finalize_times.append(time.monotonic())
        return real_finalize(self, cwd, cost_usd, exit_reason=exit_reason)

    monkeypatch.setattr(recorder_mod.RunRecorder, "finalize", timed_finalize)

    real_note = telemetry.note_turn

    def note_spy(**fields):
        note_turns.append(dict(fields))
        return real_note(**fields)

    monkeypatch.setattr(telemetry, "note_turn", note_spy)
    monkeypatch.setattr(agent_mod.telemetry, "note_turn", note_spy)

    task = asyncio.create_task(_run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=HangingProvider(), model="stub",
    ))
    await asyncio.sleep(0.05)
    cancel_t = time.monotonic()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert finalize_times, "finalize not called"
    latency = finalize_times[-1] - cancel_t
    assert latency <= 0.1, f"finalize latency {latency:.3f}s > 100ms"
    assert note_turns[-1].get("exit_reason") == "interrupt"


# ===========================================================================
# ITER-05 — confidence gate moves to terminating iteration only
# ===========================================================================


@pytest.mark.asyncio
async def test_iter_05_mid_loop_low_confidence_no_clarify(tmp_path: Path) -> None:
    tool = _make_tool("fs_read", "ok")
    iter0 = _plan(
        steps=[{"name": "fs_read", "args": {}, "why": "x"}],
        confidence=0.40, final_when_done="",
    )
    iter1 = _plan(
        steps=[{"name": "fs_read", "args": {}, "why": "y"}],
        confidence=0.40, final_when_done="",
    )
    iter2 = _plan(steps=[], confidence=0.80, final_when_done="answer")
    provider = FakeStreamingProvider(scripts=[
        _done_script(plan=iter0),
        _done_script(plan=iter1),
        _done_script(plan=iter2),
    ])
    renderer = RecordingRenderer()
    result = await _run_turn_exec(
        "x", tools={"fs_read": tool}, cwd=tmp_path, renderer=renderer,
        provider=provider, model="stub", confidence_threshold=0.60,
    )
    assert result.run.exit_reason == "done"
    assert result.final == "answer"
    assert renderer.clarify_calls == []


@pytest.mark.asyncio
async def test_iter_05_terminating_low_confidence_does_clarify(
    tmp_path: Path,
) -> None:
    plan = _plan(
        steps=[], confidence=0.30, final_when_done="(tentative)",
        open_question="what?",
    )
    provider = FakeStreamingProvider(scripts=[_done_script(plan=plan)])
    renderer = RecordingRenderer()
    result = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=renderer,
        provider=provider, model="stub", confidence_threshold=0.60,
    )
    assert result.run is None
    assert renderer.clarify_calls == [("what?", 0.30)]


# ===========================================================================
# ITER-06 — per-iteration telemetry + note_turn + RunRecord exit_reason
# ===========================================================================


@pytest.mark.asyncio
async def test_iter_06_one_iter_end_event_per_iter(
    tmp_path: Path, telemetry_capture
) -> None:
    tool = _make_tool("fs_read", "ok")
    iter0 = _plan(steps=[{"name": "fs_read", "args": {}, "why": "x"}],
                  confidence=0.85, final_when_done="")
    iter1 = _plan(steps=[{"name": "fs_read", "args": {}, "why": "y"}],
                  confidence=0.85, final_when_done="")
    iter2 = _plan(steps=[], confidence=0.9, final_when_done="done")
    provider = FakeStreamingProvider(scripts=[
        _done_script(plan=iter0),
        _done_script(plan=iter1),
        _done_script(plan=iter2),
    ])
    await _run_turn_exec(
        "x", tools={"fs_read": tool}, cwd=tmp_path,
        renderer=RecordingRenderer(), provider=provider, model="stub",
    )
    ends = [d for (t, d) in telemetry_capture["emits"] if t == "iteration.end"]
    assert len(ends) == 3
    assert [d["iteration_index"] for d in ends] == [0, 1, 2]


@pytest.mark.asyncio
async def test_iter_06_note_turn_carries_iteration_count_and_exit_reason(
    tmp_path: Path, telemetry_capture
) -> None:
    plan = _plan(steps=[], confidence=0.9, final_when_done="ok")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=plan)])
    await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    note = telemetry_capture["note_turns"][-1]
    assert note.get("iteration_count") == 1
    assert note.get("exit_reason") == "done"


def test_iter_06_runrecord_exit_reason_validated() -> None:
    with pytest.raises(ValueError):
        RunRecord(id="x", started_at="a", ended_at="b", exit_reason="quit")
    # Valid values do not raise. Additive history: T2-03 "batch-invariant";
    # 74a328f "timeout"; 6361c51 "error"; a666646 "killed".
    valid = (
        "done",
        "max-iter",
        "budget",
        "interrupt",
        "batch-invariant",
        "timeout",
        "killed",
        "error",
    )
    for reason in valid:
        RunRecord(id="x", started_at="a", ended_at="b", exit_reason=reason)
    assert EXIT_REASONS == frozenset(valid)


# ===========================================================================
# max_iterations default + exact halted strings (criteria 10 + 12)
# ===========================================================================


def test_default_max_iterations_is_8() -> None:
    from voss_runtime import get_config
    assert get_config().max_iterations == 8


@pytest.mark.asyncio
async def test_exact_halted_max_iter_string(tmp_path: Path) -> None:
    configure(max_iterations=2)
    never = _plan(steps=[], confidence=0.9, final_when_done="")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=never)] * 2)
    result = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    assert "halted: max-iter" in result.final  # exact substring


@pytest.mark.asyncio
async def test_no_runtime_error_on_cap(tmp_path: Path) -> None:
    configure(max_iterations=2)
    never = _plan(steps=[], confidence=0.9, final_when_done="")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=never)] * 2)
    # No RuntimeError despite cap hit.
    result = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    assert result.run.exit_reason == "max-iter"


# ===========================================================================
# Exit-reason matrix — all four values reachable
# ===========================================================================


@pytest.mark.asyncio
async def test_exit_reason_matrix_all_four_reachable(
    tmp_path: Path, monkeypatch
) -> None:
    seen: set[str] = set()

    # done
    plan_done = _plan(steps=[], confidence=0.9, final_when_done="ok")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=plan_done)])
    r = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    seen.add(r.run.exit_reason)

    # max-iter
    configure(max_iterations=2)
    never = _plan(steps=[], confidence=0.9, final_when_done="")
    provider = FakeStreamingProvider(scripts=[_done_script(plan=never)] * 2)
    r = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub",
    )
    seen.add(r.run.exit_reason)
    reset_config()

    # budget
    real_build = agent_mod._build_iter_rider
    def inflating(**kw):
        import sys
        ctx = sys._getframe(1).f_locals.get("ctx")
        if ctx is not None and kw.get("index", 0) >= 1:
            ctx.tokens_used = ctx.token_budget + 1
        return real_build(**kw)
    monkeypatch.setattr(agent_mod, "_build_iter_rider", inflating)
    provider = FakeStreamingProvider(scripts=[_done_script(plan=never)] * 8)
    r = await _run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=provider, model="stub", token_budget=1000,
    )
    seen.add(r.run.exit_reason)
    monkeypatch.undo()

    # interrupt
    release = asyncio.Event()

    @dataclass
    class HangingProvider:
        def stream(self, **kw):
            async def _gen():
                yield TextDelta(text="…")
                await release.wait()
                yield ParsedPlan(plan=plan_done)
                yield Done(stop_reason="end_turn")
            return _gen()
        async def complete(self, **kw):
            from voss_runtime.providers.base import ProviderResponse
            return ProviderResponse(
                text="", model="stub", prompt_tokens=0, completion_tokens=0,
                cost_usd=0.0, raw={}, parsed=None,
            )
        def count_tokens(self, *, text, model):
            return 1

    # Capture finalize argument via monkeypatch.
    from voss.harness import recorder as recorder_mod
    real_finalize = recorder_mod.RunRecorder.finalize
    captured_reason: list[str] = []

    def cap_finalize(self, cwd, cost_usd, *, exit_reason=None):
        captured_reason.append(exit_reason or "")
        return real_finalize(self, cwd, cost_usd, exit_reason=exit_reason)

    monkeypatch.setattr(recorder_mod.RunRecorder, "finalize", cap_finalize)

    task = asyncio.create_task(_run_turn_exec(
        "x", tools={}, cwd=tmp_path, renderer=RecordingRenderer(),
        provider=HangingProvider(), model="stub",
    ))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    seen.add(captured_reason[-1])
    assert seen == {"done", "max-iter", "budget", "interrupt"}


# ===========================================================================
# Per-iter PermissionGate fresh check (CONTEXT.md invariant)
# ===========================================================================


@pytest.mark.asyncio
async def test_permission_gate_fresh_per_iteration(
    tmp_path: Path, monkeypatch
) -> None:
    """Each iteration's tool call re-prompts the gate — no session-cached approvals."""
    # PermissionGate._prompt short-circuits to denial on non-tty stdin; the
    # injected prompt_fn only runs in tty mode. Force isatty=True so the
    # test exercises the prompt_fn path.
    import sys as _sys
    monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)

    # Tool entry for fs_edit. Args dict identical between iter 0 and iter 1.
    async def _fs_edit_impl(**kwargs) -> str:
        return "edited"

    desc = ToolDescriptor(
        name="fs_edit",
        description="edit",
        parameters={"type": "object", "properties": {}, "required": []},
        func=_fs_edit_impl,
    )
    tool = ToolEntry(descriptor=desc, is_mutating=True, group="fs")

    iter0 = _plan(
        steps=[{"name": "fs_edit",
                "args": {"path": "foo.py", "old": "x", "new": "y"},
                "why": "rename"}],
        confidence=0.85, final_when_done="",
    )
    iter1 = _plan(
        steps=[{"name": "fs_edit",
                "args": {"path": "foo.py", "old": "x", "new": "y"},
                "why": "rename again"}],
        confidence=0.85, final_when_done="",
    )
    iter2 = _plan(steps=[], confidence=0.9, final_when_done="done")
    provider = FakeStreamingProvider(scripts=[
        _done_script(plan=iter0),
        _done_script(plan=iter1),
        _done_script(plan=iter2),
    ])

    prompt_calls: list[tuple[str, dict]] = []

    def recording_prompt(tool_name: str, args: dict) -> str:
        prompt_calls.append((tool_name, dict(args)))
        return "a"  # allow once (no remember)

    gate = PermissionGate(
        auto_yes=False, mode="edit", prompt_fn=recording_prompt
    )

    await _run_turn_exec(
        "rename across iters",
        tools={"fs_edit": tool},
        cwd=tmp_path,
        renderer=RecordingRenderer(),
        provider=provider,
        model="stub",
        permissions=gate,
    )

    assert len(prompt_calls) == 2, (
        f"expected 2 fresh prompts (one per iter), got {len(prompt_calls)}: "
        f"{prompt_calls}"
    )
    assert all(name == "fs_edit" for name, _ in prompt_calls)
    assert prompt_calls[0][1] == prompt_calls[1][1], (
        "iter 0 and iter 1 args must be identical to prove no session-caching"
    )
