"""S0.4 — instructions prompt slice + overflow event (AC-S0-3, AC-S0-4)."""
from __future__ import annotations

from pathlib import Path

from voss.harness import instructions as instr
from voss.harness.agent import _compose_instructions_block, _compose_system_blocks


class _StubRenderer:
    def __init__(self) -> None:
        self.overflow: list[dict] = []

    def show_instructions_overflow(self, *, instructions_tokens: int, budget: int = 4000,
                                   truncated: list[str] | None = None) -> None:
        self.overflow.append({"tokens": instructions_tokens, "budget": budget, "truncated": truncated})


def test_all_renderers_have_method() -> None:
    from voss.harness.render import CompactRenderer, JsonRenderer, PlainRenderer, TtyRenderer
    from voss.harness.server.renderer import EventBusRenderer
    from voss.harness.tui.renderer import TextualRenderer

    for cls in (TtyRenderer, CompactRenderer, PlainRenderer, JsonRenderer, EventBusRenderer, TextualRenderer):
        assert hasattr(cls, "show_instructions_overflow"), cls


def test_ac_s0_4_block_order() -> None:
    blocks = _compose_system_blocks(
        voss_md_block="VOSS",
        cognition_text="COG",
        instructions_text="INSTR",
        principles_text="PRIN",
        project_index_text="IDX",
        pinned_memory_text="PIN",
        code_recall_text="RECALL",
        prior_context_text="PRIOR",
        loop_system="LOOP",
    )
    assert [b["text"] for b in blocks] == [
        "VOSS", "INSTR", "COG", "PRIN", "IDX", "PIN", "RECALL", "PRIOR", "LOOP",
    ]


def test_empty_instructions_omitted() -> None:
    blocks = _compose_system_blocks(
        voss_md_block="VOSS", cognition_text="COG", prior_context_text="", loop_system="LOOP",
    )
    assert [b["text"] for b in blocks] == ["VOSS", "COG", "LOOP"]


def test_block_renders_heading_and_files(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")
    body = _compose_instructions_block(instr.load(tmp_path))
    assert body.startswith("## Instructions")
    assert "### AGENTS.md" in body
    assert "Use pnpm." in body


def test_no_files_renders_nothing(tmp_path: Path) -> None:
    assert _compose_instructions_block(instr.load(tmp_path)) == ""


def test_ac_s0_3_overflow_event(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("rule\n" * 30_000, encoding="utf-8")
    r = _StubRenderer()
    bundle = instr.load(tmp_path, config={"budget_tokens": 4000, "per_file_tokens": 4000})
    _compose_instructions_block(bundle, budget=4000, renderer=r)
    assert r.overflow == [{"tokens": bundle.tokens, "budget": 4000, "truncated": ["AGENTS.md"]}]


def test_server_event_model_round_trips() -> None:
    from voss.harness.server.events import AgentEventAdapter, InstructionsOverflow

    ev = InstructionsOverflow(instructions_tokens=5000, truncated=["AGENTS.md"])
    parsed = AgentEventAdapter.validate_json(ev.model_dump_json())
    assert parsed.type == "instructions_overflow"
    assert parsed.budget == 4000


def test_overflow_emitted_even_when_nothing_fits(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("rule\n" * 500, encoding="utf-8")
    r = _StubRenderer()
    bundle = instr.load(tmp_path, config={"budget_tokens": 50, "per_file_tokens": 50})
    assert _compose_instructions_block(bundle, budget=50, renderer=r) == ""
    assert r.overflow == [{"tokens": 0, "budget": 50, "truncated": ["AGENTS.md"]}]
