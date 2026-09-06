"""NET-07 acceptance tests for TokenBucket + [net.rate_limits] loader.

test_mcp_bypasses_bucket stays skipped; T3-05 un-skips when
NetSession.acquire is wired and the MCP-bypass invariant is testable
against a real session.
"""

from __future__ import annotations

import pytest

from voss.harness import config as harness_config
from voss.harness.config import (
    _NET_RATE_BLOCK,
    get_net_rate_limits,
)
from voss.harness.rate_limit import (
    DEFAULT_SPECS,
    TokenBucket,
    make_default_bucket,
)


@pytest.fixture
def xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# NET-07a/b: exhaustion + replenish (deterministic-clock).
# ---------------------------------------------------------------------------


def _patch_clock(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(
        "voss.harness.rate_limit.time.monotonic", lambda: clock[0]
    )
    return clock


def test_bucket_exhaustion(monkeypatch) -> None:
    """NET-07a: burst drains; next acquire returns retry_after ≈ 1s at 60/min."""
    clock = _patch_clock(monkeypatch)
    bucket = TokenBucket(rate_per_min=60, burst=60)
    assert clock[0] == 0.0

    for _ in range(60):
        ok, retry = bucket.acquire()
        assert ok is True
        assert retry == 0.0

    ok, retry = bucket.acquire()
    assert ok is False
    assert retry > 0.0
    assert retry == pytest.approx(1.0, abs=0.05)


def test_replenish(monkeypatch) -> None:
    """NET-07b: tokens regenerate at rate_per_min/60 per second; burst caps refill."""
    clock = _patch_clock(monkeypatch)
    bucket = TokenBucket(rate_per_min=60, burst=60)

    for _ in range(60):
        bucket.acquire()
    ok, _ = bucket.acquire()
    assert ok is False

    # 1.0s gives exactly 1 token back.
    clock[0] += 1.0
    ok, retry = bucket.acquire()
    assert ok is True
    assert retry == 0.0

    # 30s gives 30 tokens but burst caps at 60; we already drained, so the
    # bucket caps at 30 here. Draining those 30 succeeds; the 31st fails.
    clock[0] += 30.0
    for _ in range(30):
        ok, _ = bucket.acquire()
        assert ok is True
    ok, retry = bucket.acquire()
    assert ok is False
    assert retry > 0.0


# ---------------------------------------------------------------------------
# Module guards.
# ---------------------------------------------------------------------------


def test_spec_defaults() -> None:
    assert DEFAULT_SPECS == {"web_fetch": (30, 30), "web_search": (10, 10)}


def test_factory_isolation() -> None:
    """RESEARCH Pitfall 7: each call returns a fresh bucket instance."""
    b1 = make_default_bucket("web_fetch")
    b2 = make_default_bucket("web_fetch")
    assert b1 is not b2
    assert b1.rate_per_min == 30
    assert b1.burst == 30


def test_factory_unknown_tool_raises() -> None:
    with pytest.raises(KeyError):
        make_default_bucket("unknown_tool")


def test_invalid_rate_raises() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate_per_min=0, burst=10)
    with pytest.raises(ValueError):
        TokenBucket(rate_per_min=60, burst=0)


# ---------------------------------------------------------------------------
# NET-07c/d: [net.rate_limits] TOML — string + table form.
# ---------------------------------------------------------------------------


def test_toml_override_string(xdg) -> None:
    """NET-07c: `web_fetch = "60/min"` → {rate: 60, burst: 60}."""
    p = harness_config.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "[net.rate_limits]\n"
        'web_fetch = "60/min"\n'
        'web_search = "5/min"\n'
    )
    result = get_net_rate_limits()
    assert result == {
        "web_fetch": {"rate": 60, "burst": 60},
        "web_search": {"rate": 5, "burst": 5},
    }


def test_toml_override_table(xdg) -> None:
    """NET-07d: `web_fetch = { rate = 60, burst = 120 }` → parsed."""
    p = harness_config.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "[net.rate_limits]\n"
        "web_fetch = { rate = 60, burst = 120 }\n"
        "web_search = { rate = 10, burst = 20 }\n"
    )
    result = get_net_rate_limits()
    assert result == {
        "web_fetch": {"rate": 60, "burst": 120},
        "web_search": {"rate": 10, "burst": 20},
    }


def test_toml_dot_regex_correctness(xdg) -> None:
    """Pitfall 6: `[netXrate_limits]` adjacent section must NOT match."""
    p = harness_config.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "[net.rate_limits]\n"
        'web_fetch = "60/min"\n'
        "\n"
        "[netXrate_limits]\n"
        'foo = "bad"\n'
    )
    result = get_net_rate_limits()
    assert result == {"web_fetch": {"rate": 60, "burst": 60}}
    # Direct regex proof.
    assert _NET_RATE_BLOCK.search("[net.rate_limits]\nweb_fetch = \"60/min\"")
    assert not _NET_RATE_BLOCK.search("[netXrate_limits]\nfoo = 1")


def test_toml_warns_on_bad_table(xdg) -> None:
    """Bogus table content emits RuntimeWarning and omits the key."""
    p = harness_config.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[net.rate_limits]\nweb_fetch = { rate = oops }\n")
    with pytest.warns(RuntimeWarning, match="invalid"):
        result = get_net_rate_limits()
    assert "web_fetch" not in result


# ---------------------------------------------------------------------------
# NET-07e: MCP bypass — T3-05 wires NetSession + MCP-bypass invariant.
# ---------------------------------------------------------------------------


def test_mcp_bypasses_bucket() -> None:
    """NET-07e / D-16: MCP-namespaced names (server__tool) skip the bucket.

    Exhaust the web_fetch bucket, then prove a `__`-namespaced tool name
    still returns (True, 0.0) every time — MCP traffic is never throttled.
    """
    from voss.harness.net import NetSession

    session = NetSession(rate_overrides={"web_fetch": {"rate": 1, "burst": 1}})
    ok, _ = session.acquire("web_fetch")
    assert ok is True
    ok, _ = session.acquire("web_fetch")
    assert ok is False  # bucket exhausted

    for _ in range(100):
        ok, retry = session.acquire("filesystem__read_text_file")
        assert ok is True
        assert retry == 0.0
