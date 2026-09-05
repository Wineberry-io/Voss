"""O4-03 Task 2: Reviewer-A tests — ORVW-01..03, ORVW-08, ORVW-09.

Tests mock run_turn and judge_run via dependency injection (run_turn_fn,
judge_run_fn) rather than scripting the full provider interaction. This
tests the ReviewerA CONTRACT (idea in, verdict out, fresh memory), not
run_turn's internals.
"""
from __future__ import annotations

from types import SimpleNamespace


from voss.eval.judge import Verdict
from voss.harness.agent import TurnResult
from voss.harness.board.reviewer_a import ReviewerA
from voss.harness.board.verdict import Reviewer
from voss.harness.permissions import PermissionGate


# --- Fakes -------------------------------------------------------------------

class _NullRenderer:
    """Minimal Renderer stand-in for tests."""
    def status(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def tool_call(self, *a, **kw): pass
    def tool_result(self, *a, **kw): pass
    def stream_text(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def step(self, *a, **kw): pass
    def done(self, *a, **kw): pass


class _FakeProvider:
    """Minimal ModelProvider stand-in for ReviewerA construction."""
    async def complete(self, **kw):
        raise NotImplementedError("should not be called in mock tests")
    def count_tokens(self, **kw):
        return 1


def _make_turn_result(
    tool_results: list[str] | None = None,
    final: str = "",
) -> TurnResult:
    """Build a TurnResult with minimal required fields."""
    plan = SimpleNamespace(
        confidence=0.9, steps=[], open_question=None,
        assumptions=[], decisions=[], risks=[],
    )
    return TurnResult(
        plan=plan,
        confidence=0.9,
        final=final,
        tool_results=tool_results or [],
        cost_usd=0.0,
        run=None,
    )


def _make_card(**overrides):
    defaults = {
        "original_idea": "Build a REST API for user management",
        "acceptance_criteria": "Users can CRUD",
        "artifact": "def create_user(): pass",
        "artifact_text": "def create_user(): pass",
        "file_diff": "+def create_user(): pass",
        "a_verification_summary": "",
        "domain": "code",
        "node_id": "test-node",
        "column": "InReview",
        "risk_tier": "med",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _base_gate() -> PermissionGate:
    return PermissionGate(mode="edit", auto_yes=True)


# --- Tests -------------------------------------------------------------------

class TestAUsesOriginalIdea:
    """ORVW-01: A derives bar from original idea, not EM AC."""

    def test_a_uses_original_idea(self, tmp_path):
        recorded_tasks: list[str] = []

        async def fake_run_turn(task, **kwargs):
            recorded_tasks.append(task)
            return _make_turn_result(tool_results=["test output [exit 0]"])

        a = ReviewerA(
            provider=_FakeProvider(),
            model="test-model",
            cwd=tmp_path,
            renderer=_NullRenderer(),
            base_gate=_base_gate(),
            run_turn_fn=fake_run_turn,
        )
        card = _make_card(original_idea="Build a REST API for user management")
        a.review(card)

        assert len(recorded_tasks) == 1
        task_text = recorded_tasks[0]
        assert "Build a REST API" in task_text
        assert "em_plan" not in task_text.lower()
        assert "engineering manager" not in task_text.lower()
        assert "DoD" not in task_text


class TestAAuthorsTestFile:
    """ORVW-02: A authors tests for code cards; exit code is verdict."""

    def test_a_authors_test_file_pass(self, tmp_path):
        async def fake_run_turn(task, **kwargs):
            return _make_turn_result(tool_results=["Running tests... [exit 0]"])

        a = ReviewerA(
            provider=_FakeProvider(), model="m", cwd=tmp_path,
            renderer=_NullRenderer(), base_gate=_base_gate(),
            run_turn_fn=fake_run_turn,
        )
        v = a.review(_make_card(domain="code"))
        assert v.verdict == "pass"
        assert v.conf == 1.0
        assert v.source == "A"

    def test_a_authors_test_file_fail(self, tmp_path):
        async def fake_run_turn(task, **kwargs):
            return _make_turn_result(tool_results=["FAILED [exit 1]"])

        a = ReviewerA(
            provider=_FakeProvider(), model="m", cwd=tmp_path,
            renderer=_NullRenderer(), base_gate=_base_gate(),
            run_turn_fn=fake_run_turn,
        )
        v = a.review(_make_card(domain="code"))
        assert v.verdict == "fail"
        assert v.conf == 0.0
        assert v.source == "A"


class TestAAiCardEval:
    """ORVW-03: A uses judge_run for AI cards (rubric → Verdict)."""

    def test_a_ai_card_eval(self, tmp_path):
        async def fake_run_turn(task, **kwargs):
            return _make_turn_result(final="PASS if output is coherent")

        async def fake_judge_run(**kwargs):
            return Verdict(verdict="pass", confidence=0.85, rationale="good"), "pass"

        a = ReviewerA(
            provider=_FakeProvider(), model="m", cwd=tmp_path,
            renderer=_NullRenderer(), base_gate=_base_gate(),
            run_turn_fn=fake_run_turn,
            judge_run_fn=fake_judge_run,
        )
        v = a.review(_make_card(domain="ai"))
        assert v.verdict == "pass"
        assert v.conf == 0.85
        assert v.source == "A"
        assert v.tier == "strong"


class TestAMemoryFreshPerCard:
    """ORVW-08: EpisodicMemory is fresh per review() call, no cross-card bleed."""

    def test_a_memory_fresh_per_card(self, tmp_path):
        histories = []

        async def fake_run_turn(task, *, history=None, **kwargs):
            # Record the history object to verify it's fresh each time.
            histories.append(history)
            return _make_turn_result(tool_results=["[exit 0]"])

        a = ReviewerA(
            provider=_FakeProvider(), model="m", cwd=tmp_path,
            renderer=_NullRenderer(), base_gate=_base_gate(),
            run_turn_fn=fake_run_turn,
        )
        a.review(_make_card(original_idea="Idea ONE"))
        a.review(_make_card(original_idea="Idea TWO"))

        assert len(histories) == 2
        # Different EpisodicMemory instances — no cross-card bleed.
        assert histories[0] is not histories[1]
        # Both are fresh (empty — no prior turns).
        assert len(histories[0].turns) == 0
        assert len(histories[1].turns) == 0


class TestAImplementsProtocol:
    """ORVW-09: ReviewerA is a valid instance of the Reviewer Protocol."""

    def test_a_implements_protocol(self, tmp_path):
        a = ReviewerA(
            provider=_FakeProvider(), model="m", cwd=tmp_path,
            renderer=_NullRenderer(), base_gate=_base_gate(),
        )
        assert isinstance(a, Reviewer)
