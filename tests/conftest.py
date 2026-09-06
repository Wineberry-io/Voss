"""Top-level test fixtures shared across the whole suite.

Test isolation for leaked provider API keys: `voss.harness.auth` injects
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` into `os.environ` when it resolves
keyring credentials (so downstream LiteLLM / SDKs work without bespoke wiring).
In tests that resolve a stub credential, that export leaks into the *process*
environment and persists across tests in the same pytest worker. A leaked
`OPENAI_API_KEY` then routes every chroma-backed subsystem (memory recall,
code index, external recall) onto the OpenAI embedder instead of the offline
SentenceTransformer fallback — which 401s (and can hang) under a fake key.

This autouse fixture snapshots and restores both keys around every test so an
auth-resolving test cannot poison a later embedding-dependent test.
"""
from __future__ import annotations

import os

import pytest

_LEAK_PRONE_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def _restore_provider_env() -> None:
    saved = {k: os.environ.get(k) for k in _LEAK_PRONE_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    try:
        import pytest_textual_snapshot as snapshot_plugin
    except ImportError:
        yield
        return

    original_save_svg_diffs = snapshot_plugin.save_svg_diffs

    def save_svg_diffs_without_environment(diffs, report_session, num_snapshots_passing):
        for diff in diffs:
            diff.environment = {}
        return original_save_svg_diffs(
            diffs, report_session, num_snapshots_passing
        )

    snapshot_plugin.save_svg_diffs = save_svg_diffs_without_environment
    try:
        yield
    finally:
        snapshot_plugin.save_svg_diffs = original_save_svg_diffs
        _drain_index_builds()
        _report_exit_state()


_INDEX_BUILD_TARGETS = {"CodeIndexService._build_loop", "ExternalRecallService._build_loop"}
_INDEX_BUILD_JOIN_S = 120.0


def _drain_index_builds() -> None:
    """Join background index builders before interpreter teardown.

    make_toolset() starts CodeIndexService / ExternalRecallService builds on
    daemon threads that load sentence-transformers. A daemon thread frozen
    inside torch while Python finalizes makes the process abort with
    'terminate called without an active exception' after pytest has already
    reported success. Waiting for the in-flight builds keeps the exit clean.
    Each thread gets its own bounded join so a leaked fake clock cannot
    shorten the wait.
    """
    import sys
    import threading

    builders = [
        t
        for t in threading.enumerate()
        if getattr(getattr(t, "_target", None), "__qualname__", None) in _INDEX_BUILD_TARGETS
        or t.name.endswith("(_build_loop)")
    ]
    for t in builders:
        t.join(timeout=_INDEX_BUILD_JOIN_S)
    if os.environ.get("VOSS_EXIT_DIAG"):
        still = [t.name for t in builders if t.is_alive()]
        sys.stderr.write(f"[exit-diag] drained {len(builders)} index builders; still alive: {still}\n")


def _report_exit_state() -> None:
    if not os.environ.get("VOSS_EXIT_DIAG"):
        return
    import sys
    import threading

    lines = ["[exit-diag] live threads:"]
    for t in threading.enumerate():
        target = getattr(t, "_target", None)
        where = f"{getattr(target, '__module__', '?')}.{getattr(target, '__qualname__', '?')}" if target else "?"
        lines.append(f"  {t.name} daemon={t.daemon} alive={t.is_alive()} target={where}")
    native = [m for m in sorted(sys.modules) if m.split(".")[0] in {
        "torch", "onnxruntime", "grpc", "chromadb", "hnswlib", "sentence_transformers",
        "tokenizers", "transformers", "posthog", "opentelemetry", "watchdog", "textual", "litellm",
    } and "." not in m]
    lines.append(f"[exit-diag] native-ish top-level modules loaded: {native}")
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()
