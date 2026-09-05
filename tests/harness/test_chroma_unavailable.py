"""MemoryStore behavior when chromadb is unavailable.

The harness must not crash if `chromadb` is unimportable. `_maybe_chroma`
returns None; `recall` falls back to BM25 search; `write_*` paths return
without crashing.

Uses the existing `chroma_disabled_env` fixture from tests/harness/conftest.py.
"""
from __future__ import annotations

from pathlib import Path


from voss.harness.memory_store import MemoryStore


def test_maybe_chroma_returns_none_when_disabled(
    chroma_disabled_env: None, tmp_voss_repo: Path
) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    chroma = store._maybe_chroma()
    assert chroma is None


def test_recall_returns_list_when_chroma_disabled(
    chroma_disabled_env: None, tmp_voss_repo: Path
) -> None:
    """recall must fall back to BM25 search, returning a list (possibly empty)."""
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    store.write_turn(role="user", content="hello world", session_id="s1", turn_idx=0)
    store.write_turn(
        role="assistant",
        content="unrelated deployment checklist",
        session_id="s1",
        turn_idx=1,
    )
    hits = store.recall("hello", top_k=5)
    assert isinstance(hits, list)
    # BM25 fallback should match the seeded turn.
    assert any("hello" in (h.excerpt or "") for h in hits), [h.excerpt for h in hits]


def test_write_turn_no_crash_when_chroma_disabled(
    chroma_disabled_env: None, tmp_voss_repo: Path
) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s2")
    # Must not raise — chroma side-effect is best-effort.
    store.write_turn(role="user", content="indexing test", session_id="s2", turn_idx=0)
    turns_dir = tmp_voss_repo / ".voss" / "memory" / "turns"
    assert any(turns_dir.glob("s2.jsonl")) or any(turns_dir.iterdir()), (
        "turn JSONL not written"
    )


def test_recall_empty_store_returns_empty_list(
    chroma_disabled_env: None, tmp_voss_repo: Path
) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s3")
    hits = store.recall("anything", top_k=5)
    assert hits == [], hits
