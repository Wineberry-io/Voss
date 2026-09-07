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


_ABORT_PRONE_NATIVE = frozenset({
    "torch", "onnxruntime", "sentence_transformers", "tokenizers",
})
_EXIT_DIAG_NATIVE = _ABORT_PRONE_NATIVE | frozenset({
    "grpc", "chromadb", "hnswlib", "transformers", "posthog",
    "opentelemetry", "watchdog", "textual", "litellm",
})


def _snapshot_sys_modules() -> list[str]:
    import sys

    try:
        return list(sys.modules)
    except RuntimeError:
        return []


def _abort_prone_native_loaded(names: list[str] | None = None) -> bool:
    loaded = set(names if names is not None else _snapshot_sys_modules())
    return bool(loaded & _ABORT_PRONE_NATIVE)


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    snapshot_plugin = None
    original_save_svg_diffs = None
    try:
        import pytest_textual_snapshot as snapshot_mod
    except ImportError:
        snapshot_mod = None
    else:
        snapshot_plugin = snapshot_mod
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
        if snapshot_plugin is not None and original_save_svg_diffs is not None:
            snapshot_plugin.save_svg_diffs = original_save_svg_diffs
        _report_exit_state()
        # Torch/onnxruntime abort in Py_Finalize ("terminate called without an
        # active exception") once a background index build has loaded them.
        # Coverage and snapshot plugins have already written; skip C++ teardown.
        if os.environ.get("VOSS_EXIT_DIAG") or _abort_prone_native_loaded():
            os._exit(exitstatus)


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
    names = _snapshot_sys_modules()
    native = [
        m for m in sorted(names)
        if m.split(".")[0] in _EXIT_DIAG_NATIVE and "." not in m
    ]
    lines.append(f"[exit-diag] native-ish top-level modules loaded: {native}")
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()
