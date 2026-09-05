"""Harness config persistence (~/.config/voss/config.toml).

Today the only key is [harness] preferred_model, set by the REPL /model
slash command. Kept narrow on purpose — anything richer goes under .voss/ in M2.

T1-04 added an [agent] section reader / writer for max_iterations (default
8). [agent] was picked over [loop] because it leaves room for future agent-
loop neighbors (confidence_threshold, timeout, etc.) without renaming.
"""
from __future__ import annotations

import os
import re
import tomllib
import warnings
from pathlib import Path

from voss_runtime._config import RuntimeConfig


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "voss" / "config.toml"


_RESERVED_SOURCE_NAMES = frozenset({"code", "memory", "global"})

_HARNESS_BLOCK = re.compile(r"^\[harness\][^\[]*", re.MULTILINE)
_AGENT_BLOCK = re.compile(r"^\[agent\][^\[]*", re.MULTILINE)
_EVAL_BLOCK = re.compile(r"^\[eval\][^\[]*", re.MULTILINE)
_TOOLS_BLOCK = re.compile(r"^\[tools\][^\[]*", re.MULTILINE)
# V18 VOPT-06: packing profile block. `[context]` does not collide with any
# existing section (verified — only harness/agent/eval/tools/net.rate_limits/
# model_tiers exist).
_CONTEXT_BLOCK = re.compile(r"^\[context\][^\[]*", re.MULTILINE)
_MEMORY_BLOCK = re.compile(r"^\[memory\][^\[]*", re.MULTILINE)
_INSTRUCTIONS_BLOCK = re.compile(r"^\[instructions\][^\[]*", re.MULTILINE)
_BILLING_BLOCK = re.compile(r"^\[billing\][^\[]*", re.MULTILINE)
# T3-04: PITFALL 6 — escape the dot. Un-escaped `r"^\[net.rate_limits\]"`
# also matches `[netXrate_limits]` (any single char), corrupting the
# bucket config. The escape is load-bearing.
_NET_RATE_BLOCK = re.compile(r"^\[net\.rate_limits\][^\[]*", re.MULTILINE)
_MODEL_TIERS_BLOCK = re.compile(r"^\[model_tiers\][^\[]*", re.MULTILINE)
# `web_fetch = "60/min"` — quoted string form.
_RATE_STR = re.compile(r'^\s*(\w+)\s*=\s*"(\d+)/min"\s*$', re.MULTILINE)
# `web_fetch = { rate = 60, burst = 120 }` — one-line inline-table form.
_RATE_TABLE = re.compile(r"^\s*(\w+)\s*=\s*\{([^}]+)\}\s*$", re.MULTILINE)
# Inside-braces kv (rate / burst only).
_RATE_TABLE_KV = re.compile(r"\s*(rate|burst)\s*=\s*(\d+)\s*,?")
_KV = re.compile(r'^\s*(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"\s*$', re.MULTILINE)
# Bare (unquoted) right-hand values for [tools] keys like
# `allow_net = true`. The existing _KV regex only matches double-quoted
# strings; TOML booleans are bare, so they need their own matcher.
# The pattern captures any non-whitespace token after `=`; get_allow_net
# validates 'true' / 'false' and warns on anything else.
_KV_BARE = re.compile(r"^\s*(\w+)\s*=\s*([^\s\"#]+)\s*$", re.MULTILINE)
# `[billing]` keys are auth-source names such as `claude-agent`; allow hyphens.
_KV_DASHED = re.compile(r'^\s*([\w-]+)\s*=\s*"((?:[^"\\]|\\.)*)"\s*$', re.MULTILINE)


def _parse_harness_section(text: str) -> dict[str, str]:
    m = _HARNESS_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    return {k: v for k, v in _KV.findall(block)}


def _parse_agent_section(text: str) -> dict[str, str]:
    m = _AGENT_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    return {k: v for k, v in _KV.findall(block)}


def _parse_eval_section(text: str) -> dict[str, str]:
    m = _EVAL_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    return {k: v for k, v in _KV.findall(block)}


def _parse_tools_section(text: str) -> dict[str, str]:
    """Return `[tools]` keys. Booleans go through _KV_BOOL (no quotes);
    quoted-string values would go through _KV. allow_net is boolean only."""
    m = _TOOLS_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    out: dict[str, str] = {}
    for k, v in _KV.findall(block):
        out[k] = v
    for k, v in _KV_BARE.findall(block):
        # Don't overwrite a quoted-string match with a stray bare token
        # (e.g. when a value coincidentally lacks quotes).
        out.setdefault(k, v)
    return out


def _parse_context_section(text: str) -> dict[str, str]:
    """Return `[context]` keys. Numbers/booleans are bare (_KV_BARE);
    quoted strings also accepted (_KV wins on collision)."""
    m = _CONTEXT_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    out: dict[str, str] = {}
    for k, v in _KV.findall(block):
        out[k] = v
    for k, v in _KV_BARE.findall(block):
        out.setdefault(k, v)
    return out


def _parse_memory_section(text: str) -> dict[str, str]:
    """Return `[memory]` keys, including bare booleans like global=false."""
    m = _MEMORY_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    out: dict[str, str] = {}
    for k, v in _KV.findall(block):
        out[k] = v
    for k, v in _KV_BARE.findall(block):
        out.setdefault(k, v)
    return out


_TRAILING_COMMENT = re.compile(r'(?<![\w"])\s*#.*$', re.MULTILINE)
_QUOTED_LINE = re.compile(r'^\s*[\w-]+\s*=\s*"(?:[^"\\]|\\.)*"\s*(#.*)?$', re.MULTILINE)


def _strip_comments(block: str) -> str:
    """Drop `# ...` trailers so `key = 6000 # note` parses as `key = 6000`."""
    out: list[str] = []
    for line in block.splitlines():
        m = _QUOTED_LINE.match(line)
        if m and m.group(1):
            line = line[: line.rfind("#")].rstrip()
        elif '"' not in line:
            line = _TRAILING_COMMENT.sub("", line)
        out.append(line)
    return "\n".join(out)


def _parse_bare_section(block_re: re.Pattern[str], text: str) -> dict[str, str]:
    m = block_re.search(text)
    if not m:
        return {}
    block = _strip_comments(m.group(0))
    out: dict[str, str] = {}
    for k, v in _KV.findall(block):
        out[k] = v
    for k, v in _KV_BARE.findall(block):
        out.setdefault(k, v)
    return out


def _read_config_text() -> str:
    p = config_path()
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


INSTRUCTIONS_DEFAULTS: dict = {
    "enabled": True,
    "budget_tokens": 4000,
    "per_file_tokens": 2000,
    "read_global": False,
}


def get_instructions_config() -> dict:
    """Resolve `[instructions]` (AGENTS.md / CLAUDE.md loading) with defaults."""
    raw = _parse_bare_section(_INSTRUCTIONS_BLOCK, _read_config_text())
    out = dict(INSTRUCTIONS_DEFAULTS)
    for key in ("enabled", "read_global"):
        v = raw.get(key)
        if v is None:
            continue
        n = v.strip().lower()
        if n in ("true", "false"):
            out[key] = n == "true"
        else:
            warnings.warn(
                f"[instructions] {key} = {v!r} is not a boolean; using default",
                RuntimeWarning,
                stacklevel=2,
            )
    for key in ("budget_tokens", "per_file_tokens"):
        v = raw.get(key)
        if v is None:
            continue
        try:
            n_int = int(v)
            if n_int <= 0:
                raise ValueError
            out[key] = n_int
        except (TypeError, ValueError):
            warnings.warn(
                f"[instructions] {key} = {v!r} is not a positive integer; using default",
                RuntimeWarning,
                stacklevel=2,
            )
    return out


BILLING_KINDS = ("subscription", "metered", "unknown")
_BILLING_DEFAULTS: dict[str, str] = {
    "claude-agent": "subscription",
    "codex-oauth": "subscription",
    "env-anthropic": "metered",
    "voss-anthropic": "metered",
    "env-openai": "metered",
    "voss-openai": "metered",
    "codex": "metered",
}


def get_provider_billing(source: str) -> str:
    """Billing kind for an auth `Resolution.source`: subscription | metered | unknown.

    `[billing]` in config.toml overrides the built-in table, keyed by source name.
    """
    m = _BILLING_BLOCK.search(_read_config_text())
    raw = dict(_KV_DASHED.findall(_strip_comments(m.group(0)))).get(source) if m else None
    if raw is not None:
        n = raw.strip().lower()
        if n in BILLING_KINDS:
            return n
        warnings.warn(
            f"[billing] {source} = {raw!r} is not one of {BILLING_KINDS}; using default",
            RuntimeWarning,
            stacklevel=2,
        )
    return _BILLING_DEFAULTS.get(source, "unknown")


def load_harness_config() -> dict[str, str]:
    """Return the `[harness]` section as a dict. Missing file -> {}."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    return _parse_harness_section(text)


def load_agent_config() -> dict[str, str]:
    """Return the `[agent]` section as a dict. Missing file / section -> {}."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    return _parse_agent_section(text)


def load_context_config() -> dict[str, str]:
    """Return the `[context]` section as a dict. Missing file / section -> {}."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    return _parse_context_section(text)


def load_eval_config() -> dict[str, str]:
    """Return the `[eval]` section as a dict. Missing file / section -> {}."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    return _parse_eval_section(text)


def load_tools_config() -> dict[str, str]:
    """Return the `[tools]` section as a dict. Missing file / section -> {}."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    return _parse_tools_section(text)


def _parse_net_rate_limits_section(text: str) -> dict[str, dict[str, int]]:
    """Parse `[net.rate_limits]` → ``{tool: {"rate": int, "burst": int}}``.

    Accepts the SPEC's two forms:
      - string: ``web_fetch = "60/min"`` (burst defaults to rate)
      - table:  ``web_fetch = { rate = 60, burst = 120 }``

    Bogus rows emit RuntimeWarning and are omitted (caller falls back to
    rate_limit.DEFAULT_SPECS).
    """
    m = _NET_RATE_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    result: dict[str, dict[str, int]] = {}
    for name, rate in _RATE_STR.findall(block):
        try:
            r = int(rate)
            result[name] = {"rate": r, "burst": r}
        except ValueError:
            warnings.warn(
                f"[net.rate_limits] {name} string form invalid: {rate!r}",
                RuntimeWarning,
                stacklevel=2,
            )
    for name, inner in _RATE_TABLE.findall(block):
        kv = dict(_RATE_TABLE_KV.findall(inner))
        try:
            r = int(kv["rate"])
            b = int(kv.get("burst", r))
            result[name] = {"rate": r, "burst": b}
        except (KeyError, ValueError):
            warnings.warn(
                f"[net.rate_limits] {name} table form invalid: {inner!r}",
                RuntimeWarning,
                stacklevel=2,
            )
            result.pop(name, None)
    return result


def get_net_rate_limits() -> dict[str, dict[str, int]]:
    """Resolve `[net.rate_limits]` overrides; missing file / section -> {}."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    return _parse_net_rate_limits_section(text)


# V3 (VTEAM-08): tier alias -> concrete model id. This dict is the ONLY place
# concrete model NAME strings live for the team compiler; team.py references the
# three tier keywords and resolves through get_model_tiers(). Ids target the
# anthropic provider (model_catalog.TARGET_PROVIDERS[0]).
_DEFAULT_MODEL_TIERS: dict[str, str] = {
    "strong": "claude-opus-4-8",
    "cheap": "claude-haiku-4-5",
    "fast": "claude-haiku-4-5",
}


def _parse_model_tiers_section(text: str) -> dict[str, str]:
    """Parse `[model_tiers]` quoted-string entries → ``{tier: model_id}``."""
    m = _MODEL_TIERS_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    return {k: v for k, v in _KV.findall(block)}


def get_model_tiers() -> dict[str, str]:
    """Resolve tier alias -> concrete model id.

    Returns the built-in `_DEFAULT_MODEL_TIERS` shallow-merged under any
    `[model_tiers]` overrides in `config.toml`. Missing file / section -> the
    built-in defaults. Mirrors `get_net_rate_limits` shape (plain dict accessor).
    """
    merged = dict(_DEFAULT_MODEL_TIERS)
    p = config_path()
    if not p.exists():
        return merged
    try:
        text = p.read_text()
    except OSError:
        return merged
    merged.update(_parse_model_tiers_section(text))
    return merged


# --- V19-06 (VSEM-07/08): index_enrich role + [code_recall] section ----------
#
# Example config:
#   [model_tiers]
#   index_enrich = "ollama/gpt-oss"        # Ollama-local default (D-12);
#                                          # Haiku-class alternate: "claude-haiku-4-5"
#   [code_recall]
#   enrich_profile = true
#   enrich_budget_tokens = 50000
#   inject = true
#
# Absent index_enrich → enrichment unavailable even with enrich_profile=true
# (fail-closed, D-06 — NEVER falls back to the session model).

_CODE_RECALL_BLOCK = re.compile(r"^\[code_recall\][^\[]*", re.MULTILINE)
_CODE_RECALL_BOOL = re.compile(r"^\s*(enrich_profile|inject)\s*=\s*(true|false)\s*$", re.MULTILINE | re.IGNORECASE)
_CODE_RECALL_INT = re.compile(r"^\s*(enrich_budget_tokens)\s*=\s*(\d+)\s*$", re.MULTILINE)

_DEFAULT_CODE_RECALL: dict = {
    "enrich_profile": False,  # OFF by default (VSEM-07)
    "enrich_budget_tokens": 0,  # 0 = no enrichment spend allowed
    "inject": True,  # V19-05 auto-injection off-switch
}


def get_index_enrich_model() -> str | None:
    """Configured index_enrich model id, or None (fail-closed — D-06)."""
    return get_model_tiers().get("index_enrich")


def _parse_code_recall_section(text: str) -> dict:
    m = _CODE_RECALL_BLOCK.search(text)
    if not m:
        return {}
    block = m.group(0)
    out: dict = {}
    for key, raw in _CODE_RECALL_BOOL.findall(block):
        out[key] = raw.lower() == "true"
    for key, raw in _CODE_RECALL_INT.findall(block):
        out[key] = int(raw)
    return out


def get_code_recall_config() -> dict:
    """Resolve the `[code_recall]` section over fail-closed defaults.

    Missing file / section → defaults (enrich_profile False, budget 0,
    inject True). Never raises.
    """
    merged = dict(_DEFAULT_CODE_RECALL)
    p = config_path()
    if not p.exists():
        return merged
    try:
        text = p.read_text()
    except OSError:
        return merged
    merged.update(_parse_code_recall_section(text))
    return merged


def get_recall_sources() -> list[dict]:
    """Resolve configured external recall sources from `[[recall.sources]]`."""
    p = config_path()
    if not p.exists():
        return []
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warnings.warn(
            f"could not parse recall sources from {p}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return []

    sources = data.get("recall", {}).get("sources", [])
    if not isinstance(sources, list):
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        path = str(raw.get("path", "")).strip()
        glob = str(raw.get("glob", "**/*.md")).strip() or "**/*.md"
        if name in _RESERVED_SOURCE_NAMES:
            reserved = ", ".join(sorted(_RESERVED_SOURCE_NAMES))
            raise ValueError(f"recall source name {name!r} is reserved ({reserved})")
        if name in seen:
            raise ValueError(f"duplicate recall source name: {name}")
        seen.add(name)
        out.append({"name": name, "path": path, "glob": glob})
    return out


def get_global_memory_enabled() -> bool:
    """Return True unless config.toml sets `[memory] global = false`."""
    p = config_path()
    if not p.exists():
        return True
    try:
        text = p.read_text()
    except OSError:
        return True
    raw = _parse_memory_section(text).get("global")
    if raw is None:
        return True
    normalized = raw.strip().lower()
    if normalized == "false":
        return False
    if normalized == "true":
        return True
    warnings.warn(
        f"[memory] global = {raw!r} is not a boolean; defaulting to enabled",
        RuntimeWarning,
        stacklevel=2,
    )
    return True


def get_max_iterations() -> int:
    """Resolve agent.max_iterations, falling back to RuntimeConfig default."""
    default = RuntimeConfig().max_iterations
    cfg = load_agent_config()
    raw = cfg.get("max_iterations")
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        warnings.warn(
            f"[agent] max_iterations = {raw!r} is not an integer; "
            f"falling back to default {default}",
            RuntimeWarning,
            stacklevel=2,
        )
        return default


DEFAULT_MAX_TURNS = 15
DEFAULT_JUDGE_MODEL = "gpt-5.5-mini"


def get_eval_max_turns() -> int:
    """Resolve eval.max_turns, falling back to DEFAULT_MAX_TURNS."""
    default = DEFAULT_MAX_TURNS
    cfg = load_eval_config()
    raw = cfg.get("max_turns")
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        warnings.warn(
            f"[eval] max_turns = {raw!r} is not an integer; "
            f"falling back to default {default}",
            RuntimeWarning,
            stacklevel=2,
        )
        return default


def get_eval_judge_model() -> str:
    """Resolve eval.judge_model, falling back to DEFAULT_JUDGE_MODEL."""
    return load_eval_config().get("judge_model", DEFAULT_JUDGE_MODEL)


def get_max_parallel_reads() -> int:
    """Resolve [agent] max_parallel_reads with range validation (T2-02, PAR-05).

    Range 1-32 inclusive. Missing key returns the RuntimeConfig default
    silently. Out-of-range or non-int values fall back to the default
    (get_config().max_parallel_reads) and emit a RuntimeWarning naming the
    offending value.
    """
    from voss_runtime import get_config

    default = get_config().max_parallel_reads
    cfg = load_agent_config()
    raw = cfg.get("max_parallel_reads")
    if raw is None:
        return default
    try:
        n = int(raw)
    except (TypeError, ValueError):
        warnings.warn(
            f"[agent] max_parallel_reads = {raw!r} is not an integer; "
            f"falling back to default {default}",
            RuntimeWarning,
            stacklevel=2,
        )
        return default
    if not (1 <= n <= 32):
        warnings.warn(
            f"[agent] max_parallel_reads = {n} out of range 1-32; "
            f"falling back to default {default}",
            RuntimeWarning,
            stacklevel=2,
        )
        return default
    return n


def get_allow_net() -> bool:
    """Resolve [tools] allow_net, falling back to RuntimeConfig default (False).

    Accepts exact 'true' / 'false' (case-insensitive). Any other value emits
    RuntimeWarning and falls back to the default. NET-05a/b acceptance.
    """
    default = RuntimeConfig().allow_net
    cfg = load_tools_config()
    raw = cfg.get("allow_net")
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    warnings.warn(
        f"[tools] allow_net = {raw!r} is not a boolean; "
        f"falling back to default {default}",
        RuntimeWarning,
        stacklevel=2,
    )
    return default


def get_packing_profile():
    """Resolve the V18 [context] packing profile (VOPT-06).

    Missing file / section / keys fall back to the conservative
    PackingProfile defaults (recent_full_k=8). Bad values warn and
    default — never raise.
    """
    from voss.harness.context_allocator import PackingProfile

    defaults = PackingProfile()
    profile = PackingProfile()
    cfg = load_context_config()

    def _warn(message: str) -> None:
        warnings.warn(message, RuntimeWarning, stacklevel=3)

    def _coerce(key: str, cast, current):
        raw = cfg.get(key)
        if raw is None:
            return current
        try:
            return cast(raw)
        except (TypeError, ValueError):
            _warn(
                f"[context] {key} = {raw!r} is not a {cast.__name__}; "
                f"falling back to default {current}"
            )
            return current

    profile.recent_full_k = _coerce("recent_full_k", int, profile.recent_full_k)
    profile.digest_cutoff_m = _coerce("digest_cutoff_m", int, profile.digest_cutoff_m)
    profile.high_water = _coerce("high_water", float, profile.high_water)
    profile.low_water = _coerce("low_water", float, profile.low_water)

    raw_enabled = cfg.get("enabled")
    if raw_enabled is not None:
        normalized = raw_enabled.strip().lower()
        if normalized == "true":
            profile.enabled = True
        elif normalized == "false":
            profile.enabled = False
        else:
            _warn(
                f"[context] enabled = {raw_enabled!r} is not a boolean; "
                f"falling back to default {profile.enabled}"
            )
    if profile.recent_full_k < 1:
        _warn(
            f"[context] recent_full_k = {profile.recent_full_k!r} must be >= 1; "
            f"falling back to default {defaults.recent_full_k}"
        )
        profile.recent_full_k = defaults.recent_full_k
    if profile.digest_cutoff_m < profile.recent_full_k:
        _warn(
            f"[context] digest_cutoff_m = {profile.digest_cutoff_m!r} must be "
            f">= recent_full_k ({profile.recent_full_k}); falling back to "
            f"default {defaults.digest_cutoff_m}"
        )
        profile.digest_cutoff_m = defaults.digest_cutoff_m
    if not (0 < profile.low_water < profile.high_water <= 1):
        _warn(
            "[context] watermarks must satisfy 0 < low_water < high_water <= 1; "
            "falling back to defaults"
        )
        profile.low_water = defaults.low_water
        profile.high_water = defaults.high_water
    return profile


def _write_harness(updates: dict[str, str | None]) -> Path:
    """Merge `updates` into the `[harness]` block (None value removes a key).

    Preserves other harness keys and other config sections — unlike a naive
    block-replace, so `preferred_model` and `preferred_provider` coexist.
    """
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text() if p.exists() else ""

    current = _parse_harness_section(existing)
    for key, value in updates.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value

    body = "".join(f'{k} = "{v}"\n' for k, v in current.items())
    new_block = "[harness]\n" + body
    if _HARNESS_BLOCK.search(existing):
        new_text = _HARNESS_BLOCK.sub(lambda _m: new_block, existing, count=1)
    elif existing.strip():
        new_text = existing.rstrip() + "\n\n" + new_block
    else:
        new_text = new_block

    p.write_text(new_text)
    p.chmod(0o600)
    return p


def set_preferred_model(name: str) -> Path:
    """Persist `[harness] preferred_model`. Clears any routed `preferred_provider`
    (legacy raw-string switch via /model has no catalog route)."""
    return _write_harness({"preferred_model": name, "preferred_provider": None})


def set_preferred_auth(pref: str) -> Path:
    """Persist `[harness] auth` — the default credential source used when no
    explicit --auth is given (e.g. "codex" so plain `voss chat` uses the
    subscription regardless of exported API-key env vars)."""
    return _write_harness({"auth": pref})


def set_preferred_routed(model_id: str, provider_id: str) -> Path:
    """Persist a catalog-routed selection: `preferred_model` (catalog model id)
    + `preferred_provider` (models.dev provider id). Boot rebuilds the provider
    from these via the model router."""
    return _write_harness(
        {"preferred_model": model_id, "preferred_provider": provider_id}
    )


def set_max_iterations(n: int) -> Path:
    """Persist `[agent] max_iterations = "<n>"`. Preserves [harness] section."""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text() if p.exists() else ""

    new_block = f'[agent]\nmax_iterations = "{n}"\n'
    if _AGENT_BLOCK.search(existing):
        new_text = _AGENT_BLOCK.sub(new_block, existing, count=1)
    elif existing.strip():
        new_text = existing.rstrip() + "\n\n" + new_block
    else:
        new_text = new_block

    p.write_text(new_text)
    p.chmod(0o600)
    return p
