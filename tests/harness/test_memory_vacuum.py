"""M8-06 vacuum command tests."""
from __future__ import annotations

import json
import stat
from pathlib import Path


from voss.harness.memory_store import MemoryStore


def _notes_dir(repo: Path) -> Path:
    return repo / ".voss" / "memory" / "notes"


def _turns_dir(repo: Path) -> Path:
    return repo / ".voss" / "memory" / "turns"


def test_vacuum_reclaims_tombstoned_bytes(tmp_voss_repo: Path) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    for text in ("first note body", "second note body", "third note body"):
        store.write_note(text, session_id="s1")

    n_files_before = len(list(_notes_dir(tmp_voss_repo).glob("*.md")))
    assert n_files_before == 3

    forgotten = store.forget("note:*", confirm=True)
    assert forgotten == 3
    tomb = tmp_voss_repo / ".voss" / "memory" / ".tombstones.jsonl"
    assert tomb.exists() and tomb.read_text().count("\n") == 3

    reclaimed = store.vacuum()
    assert reclaimed > 0
    assert len(list(_notes_dir(tmp_voss_repo).glob("*.md"))) == 0


def test_vacuum_deletes_tombstoned_files(tmp_voss_repo: Path) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    store.write_note("one", session_id="s1")
    store.write_note("two", session_id="s1")

    store.forget("note:*", confirm=True)
    store.vacuum()

    assert not list(_notes_dir(tmp_voss_repo).glob("*.md"))
    tomb = tmp_voss_repo / ".voss" / "memory" / ".tombstones.jsonl"
    assert tomb.exists()
    assert tomb.read_text() == ""


def test_vacuum_compacts_jsonl_turn_lines(tmp_voss_repo: Path) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    for idx in range(5):
        store.write_turn(
            role="user",
            content=f"turn body {idx}",
            session_id="s1",
            turn_idx=idx,
        )
    jsonl = _turns_dir(tmp_voss_repo) / "s1.jsonl"
    assert len([ln for ln in jsonl.read_text().splitlines() if ln.strip()]) == 5

    forgotten = store.forget("turn:s1:002", confirm=True)
    assert forgotten == 1

    store.vacuum()

    lines = [ln for ln in jsonl.read_text().splitlines() if ln.strip()]
    assert len(lines) == 4
    kept_idxs = sorted(json.loads(ln)["turn_idx"] for ln in lines)
    assert kept_idxs == [0, 1, 3, 4]

    mode = stat.S_IMODE(jsonl.stat().st_mode)
    assert mode == 0o600


def test_vacuum_removes_empty_jsonl_after_full_tombstone(tmp_voss_repo: Path) -> None:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s2")
    for idx in range(2):
        store.write_turn(
            role="user",
            content=f"turn {idx}",
            session_id="s2",
            turn_idx=idx,
        )
    jsonl = _turns_dir(tmp_voss_repo) / "s2.jsonl"
    assert jsonl.exists()

    store.forget("turn:s2:*", confirm=True)
    store.vacuum()

    assert not jsonl.exists()
