"""M9-02 TextualRenderer protocol + ConfidenceBar + BudgetMeter tests."""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from voss.harness.render import (
    PlainRenderer,
    Renderer,
    TtyRenderer,
    make_renderer,
)
from voss.harness.tui.app import VossTUIApp
from voss.harness.tui.renderer import TextualRenderer
from voss.harness.tui.widgets import BudgetMeter, ConfidenceBar


# ----------------------------------------------------------------------
# ConfidenceBar (W4 — locked 16-cell width)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.0, "░░░░░░░░░░ 0.00 "),
        (0.82, "████████░░ 0.82 "),
        (1.0, "██████████ 1.00 "),
    ],
)
def test_confidence_bar_locked_16_cell_render(value: float, expected: str) -> None:
    bar = ConfidenceBar(value=value)
    rendered = bar.render().plain
    assert rendered == expected
    assert len(rendered) == 16


def test_confidence_bar_tier_classes() -> None:
    assert "signal-good" in _spans(ConfidenceBar(value=0.90).render())
    assert "signal-warn" in _spans(ConfidenceBar(value=0.70).render())
    assert "signal-error" in _spans(ConfidenceBar(value=0.30).render())
    # is_final + >= 0.85 → accent
    assert "accent" in _spans(ConfidenceBar(value=0.95, is_final=True).render())
    # is_final + < 0.85 → still signal-warn / signal-error (never accent)
    assert "accent" not in _spans(ConfidenceBar(value=0.60, is_final=True).render())


# ----------------------------------------------------------------------
# BudgetMeter (W5 — em-dash on zero-total)
# ----------------------------------------------------------------------


def test_budget_meter_normal() -> None:
    text = BudgetMeter(used=2100, total=4000).render().plain
    assert text == "▰▰▰▰▰▱▱▱▱▱  2.1k / 4.0k "


def test_budget_meter_warn_tier() -> None:
    spans = _spans(BudgetMeter(used=3000, total=4000).render())
    assert "signal-warn" in spans


def test_budget_meter_error_tier_at_100pct() -> None:
    spans = _spans(BudgetMeter(used=4000, total=4000).render())
    assert "signal-error" in spans


def test_budget_meter_zero_total_renders_em_dash() -> None:
    rendered = BudgetMeter(used=0, total=0).render().plain
    assert "—" in rendered
    assert rendered == "▱▱▱▱▱▱▱▱▱▱  —  "
    assert len(rendered) == 15


def test_budget_meter_zero_total_no_division(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch `int.__truediv__` cannot intercept C-level division; instead
    assert via static-shape check that the zero-total branch returns before
    any division by tracing widget locals."""
    # The zero-total branch returns Text(...) before touching `/`. Render and
    # confirm we got there by content equality.
    rendered = BudgetMeter(used=0, total=0).render().plain
    assert rendered.endswith("—  ")
    # Total = 0 with non-zero used must also stay safe.
    rendered2 = BudgetMeter(used=42, total=0).render().plain
    assert rendered2 == "▱▱▱▱▱▱▱▱▱▱  —  "


# ----------------------------------------------------------------------
# TextualRenderer protocol conformance + behavior
# ----------------------------------------------------------------------


def test_textual_renderer_is_renderer_subtype() -> None:
    renderer = TextualRenderer(app=MagicMock())
    assert isinstance(renderer, Renderer)


def test_textual_renderer_implements_all_protocol_methods() -> None:
    expected = {
        "banner",
        "show_user",
        "show_thinking",
        "show_plan",
        "show_tool_call",
        "show_clarify",
        "show_final",
        "status",
        "show_cognition",
        "show_cognition_overflow",
        "show_warning",
    }
    actual = {
        name
        for name, _ in inspect.getmembers(TextualRenderer, predicate=inspect.isfunction)
    }
    missing = expected - actual
    assert not missing, f"missing protocol methods: {missing}"


@pytest.mark.asyncio
async def test_textual_renderer_show_user_appends_turn() -> None:
    app = VossTUIApp()
    async with app.run_test() as pilot:
        renderer = TextualRenderer(app=pilot.app)
        renderer.show_user("hello")
        await pilot.pause()
        transcript = pilot.app.query_one("#main")
        # TranscriptView mounts a UserBlock per message; flatten to verify.
        assert "hello" in transcript.plain_text()


@pytest.mark.asyncio
async def test_textual_renderer_status_zero_ctx_does_not_raise() -> None:
    app = VossTUIApp()
    async with app.run_test() as pilot:
        renderer = TextualRenderer(app=pilot.app)
        renderer.status(model="m", tokens=1, cost_usd=0.0, ctx_pct=0.0)
        # No exception ⇒ pass


# ----------------------------------------------------------------------
# make_renderer wiring (force_tui + plain regression)
# ----------------------------------------------------------------------


def test_make_renderer_force_tui_returns_textual_renderer() -> None:
    renderer = make_renderer(json_mode=False, plain=False, force_tui=True)
    assert isinstance(renderer, TextualRenderer)


def test_make_renderer_plain_still_returns_plain() -> None:
    renderer = make_renderer(json_mode=False, plain=True)
    assert isinstance(renderer, PlainRenderer)


def test_make_renderer_default_returns_tty_or_plain() -> None:
    """Default user path is unchanged by M9-02 (live swap deferred to M9-07)."""
    renderer = make_renderer(json_mode=False, plain=False, force_tui=False)
    assert isinstance(renderer, (TtyRenderer, PlainRenderer))


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _spans(text) -> set[str]:
    """Collect every style class applied to a rich.text.Text instance."""
    classes: set[str] = set()
    for span in getattr(text, "spans", []):
        classes.add(str(span.style))
    if text.style:
        classes.add(str(text.style))
    return classes
