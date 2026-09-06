"""VXMEM-06 RED tests for non-blocking, read-only external recall builds."""
from __future__ import annotations

import hashlib
import shutil
import threading
import time

import pytest

from .conftest import write_config_toml


@pytest.fixture
def gated_embed(monkeypatch):
    """Embedding function that blocks until `.release()` is called."""
    try:
        from chromadb.utils import embedding_functions
    except Exception:
        pytest.skip("chromadb DefaultEmbeddingFunction unavailable")

    gate = threading.Event()

    class GatedEmbed(embedding_functions.EmbeddingFunction):
        def __init__(self) -> None:
            self._inner = embedding_functions.DefaultEmbeddingFunction()

        def __call__(self, input):  # noqa: A002 - chroma's parameter name
            gate.wait(timeout=60.0)
            return self._inner(input)

    fn = GatedEmbed()
    fn.release = gate.set  # type: ignore[attr-defined]

    from voss_runtime.memory.semantic import SemanticMemory

    monkeypatch.setattr(SemanticMemory, "_embedding_function", lambda self: fn)
    return fn


def _copy_and_configure(tmp_path, monkeypatch, fixture_vault_path):
    vault = tmp_path / "recall_vault"
    shutil.copytree(fixture_vault_path, vault)
    source = {"name": "docs", "path": str(vault), "glob": "**/*.md"}
    write_config_toml(tmp_path, monkeypatch, [source])
    return vault, source


def _snapshot_files(root):
    snapshot = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        snapshot[str(path.relative_to(root))] = (
            hashlib.sha256(data).hexdigest(),
            path.stat().st_mtime_ns,
        )
    return snapshot


def _release_and_join(service, gated_embed):
    gated_embed.release()
    thread = getattr(service, "_thread", None)
    if thread is not None:
        thread.join(timeout=30.0)
        assert not thread.is_alive(), "background build thread must finish promptly"


def test_session_does_not_block(tmp_path, monkeypatch, fixture_vault_path, gated_embed):
    """VXMEM-06: background build returns before embedding completes."""
    _vault, _source = _copy_and_configure(tmp_path, monkeypatch, fixture_vault_path)

    from voss.harness.recall.external_index import ExternalRecallService

    svc = ExternalRecallService(tmp_path, session_id="test-session")
    started = time.monotonic()
    try:
        svc.ensure_background_build()
        elapsed = time.monotonic() - started

        assert elapsed < 1.0, "ensure_background_build must not wait on Chroma"
        assert not svc.is_ready(), "gated embed keeps the build in not-ready state"
        thread = getattr(svc, "_thread", None)
        assert thread is not None
        assert thread.daemon is True
    finally:
        _release_and_join(svc, gated_embed)


def test_degraded_before_ready(tmp_path, monkeypatch, fixture_vault_path, gated_embed):
    """VXMEM-06: queries before ready degrade to BM25 lists, not exceptions."""
    _vault, _source = _copy_and_configure(tmp_path, monkeypatch, fixture_vault_path)

    from voss.harness.recall.external_index import ExternalRecallService

    svc = ExternalRecallService(tmp_path, session_id="test-session")
    try:
        svc.ensure_background_build()
        assert not svc.is_ready()
        hits_per_source = svc.query_all("installation quickstart setup", top_k=5)

        assert isinstance(hits_per_source, list)
        assert len(hits_per_source) == 1
        assert hits_per_source[0], "BM25 degradation should still find fixture docs"
        assert any("getting-started.md" in h.locator for h in hits_per_source[0])
    finally:
        _release_and_join(svc, gated_embed)


def test_source_files_readonly(tmp_path, monkeypatch, fixture_vault_path, fake_embed_fn):
    """VXMEM-06: ingest and recall never mutate configured source files."""
    vault, _source = _copy_and_configure(tmp_path, monkeypatch, fixture_vault_path)
    before = _snapshot_files(vault)

    from voss.harness.recall.external_index import ExternalRecallService

    svc = ExternalRecallService(tmp_path, session_id="test-session")
    svc.ensure_background_build()
    thread = getattr(svc, "_thread", None)
    if thread is not None:
        thread.join(timeout=30.0)
        assert not thread.is_alive(), "fixture build should finish promptly"
    svc.query_all("chunk boundary heading", top_k=5)

    assert _snapshot_files(vault) == before
