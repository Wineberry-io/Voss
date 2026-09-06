"""VSEM-03 RED tests: background build never blocks the first round-trip.

A gate on the embedding function holds the build mid-flight so the tests can
observe the not-ready window deterministically (threading.Event, no sleeps as
synchronization).
"""
from __future__ import annotations

import threading
import time

import pytest

from .conftest import write_fixture_repo


@pytest.fixture
def gated_embed(monkeypatch):
    """Embedding function that blocks until .release() — pins the not-ready window."""
    try:
        from chromadb.utils import embedding_functions
    except Exception:
        pytest.skip("chromadb DefaultEmbeddingFunction unavailable")

    gate = threading.Event()

    # NOT a DefaultEmbeddingFunction subclass — chroma 1.5.9 _embed() bypasses
    # DefaultEmbeddingFunction instances (see test_incremental.CountingEmbed).
    class GatedEmbed(embedding_functions.EmbeddingFunction):
        def __init__(self) -> None:
            self._inner = embedding_functions.DefaultEmbeddingFunction()

        def __call__(self, input):  # noqa: A002 — chroma's param name
            gate.wait(timeout=60.0)
            return self._inner(input)

    fn = GatedEmbed()
    fn.release = gate.set  # type: ignore[attr-defined]

    from voss_runtime.memory.semantic import SemanticMemory

    monkeypatch.setattr(SemanticMemory, "_embedding_function", lambda self: fn)
    return fn


def _prepared_repo(tmp_path):
    write_fixture_repo(tmp_path)

    from voss.harness.code.index import build_index

    build_index(tmp_path)
    return tmp_path


def _release_and_join(service, gated_embed):
    gated_embed.release()
    thread = getattr(service, "_thread", None)
    if thread is not None:
        thread.join(timeout=30.0)
        assert not thread.is_alive(), "background build thread must finish promptly"


def test_first_roundtrip_not_blocked(tmp_path, gated_embed):
    """Session-start path returns before is_ready(): ensure_background_build
    must hand back control while embedding is still gated."""
    repo = _prepared_repo(tmp_path)

    from voss.harness.code.semantic_index import CodeIndexService

    svc = CodeIndexService(repo, session_id="test-session")
    started = time.monotonic()
    try:
        svc.ensure_background_build()
        elapsed = time.monotonic() - started

        assert elapsed < 2.0, "ensure_background_build must not wait for the build"
        assert not svc.is_ready(), "build is gated — service cannot be ready yet"

    finally:
        _release_and_join(svc, gated_embed)
    assert svc.is_ready(), "released build must reach ready"


def test_degraded_before_ready(tmp_path, gated_embed):
    """Query before ready returns degraded hits (BM25 path), not an error."""
    repo = _prepared_repo(tmp_path)

    from voss.harness.code.semantic_index import CodeIndexService

    svc = CodeIndexService(repo, session_id="test-session")
    try:
        svc.ensure_background_build()
        assert not svc.is_ready()

        hits = svc.query("retry backoff delay", top_k=5)

        assert isinstance(hits, list), "pre-ready query must return a hit list, not raise"
        for hit in hits:
            assert hit.source, "degraded hits still carry a source marker"
            assert hit.locator
    finally:
        _release_and_join(svc, gated_embed)
