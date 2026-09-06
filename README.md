<div align="center">

<img src="site/branding/voss-mark-ignite-2048.png" alt="Voss" width="96" />

# Voss

**A language for confidence-aware, budget-bounded LLM programs.**

[![CI](https://github.com/voss-lang/voss/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/voss-lang/voss/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/voss-lang/voss/branch/master/graph/badge.svg)](https://codecov.io/gh/voss-lang/voss)
[![npm version](https://img.shields.io/npm/v/@vosslang/cli.svg)](https://www.npmjs.com/package/@vosslang/cli)
[![npm downloads](https://img.shields.io/npm/dm/@vosslang/cli.svg)](https://www.npmjs.com/package/@vosslang/cli)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Node 18+](https://img.shields.io/badge/node-18+-brightgreen.svg)](https://nodejs.org/)

</div>

Voss makes probabilistic values, context windows, and per-call budgets first-class so that AI-augmented code is auditable and predictable instead of vibes-based.

Voss v0.1 ships as a Python harness plus the `.voss` workflow-control language. A native Rust shell is preserved in `crates/` as a frozen spike and stays out of the v0.1 ship path — npm (M6) distributes the same Python harness with a vendored interpreter.

## What is .voss

.voss is an **AI workflow control** layer that compiles to readable Python. It is a complement to Python, not a replacement: write your data structures, business logic, and integrations in Python as usual, and reach for .voss when you need first-class control over LLM-shaped concerns.

First-class primitives:

- Probable values + confidence gates: `let intent: probable<string> = ask(...)` with `if intent @ p >= 0.80 { ... }`
- Context budgets: `ctx(budget: 4000 tokens) { include ... yield ask(...) }` and `within budget(tokens: N, latency: Ts) { ... } fallback { ... }`
- Semantic routing: `match userMessage { case similar("angry customer") => ... case _ => ... }`
- Agents, spawn, gather: `spawn Researcher(topic)` + `gather(researchers, timeout: 60s)`
- Memory primitives: `memory.episodic(capacity: N turns)`, `memory.semantic(source: "...")`, `memory.working(capacity: N)`
- Recovery + imports: `try { ... } catch e { ... }` and `use voss_runtime::tools::tool`

See the [`samples/`](samples/) directory for the three canonical programs, and [`docs/voss-vs-python.md`](docs/voss-vs-python.md) for side-by-side comparisons against the raw-Python equivalents.

## Install

### Recommended: npm

```bash
npm i -g @vosslang/cli
```

Brings the Voss CLI with a vendored Python 3.12 + the v0.1 voss wheel + all dependencies. Zero manual Python setup. Works on macOS (arm64, x64), Linux (x64, arm64), and Windows (x64). After install run `voss doctor` to verify provider credentials, the vendored Python, and config paths.

### Alternative: pip

If you already manage Python 3.11+ yourself, install from PyPI:

```bash
pip install voss
```

Semantic memory (`memory.semantic`, `match similar(...)`) is an optional extra — it pulls torch + sentence-transformers + chromadb:

```bash
pip install 'voss[search]'
```

### Container image

Voss also publishes a CLI container image to GitHub Container Registry:

```bash
docker pull ghcr.io/voss-lang/voss:latest
docker run --rm ghcr.io/voss-lang/voss:latest --help
```

Mount a repo into `/workspace` when running project-scoped commands:

```bash
docker run --rm -v "$PWD:/workspace" ghcr.io/voss-lang/voss:latest doctor
```

First run — verify the install and check provider auth, git, and config paths:

```bash
voss doctor
```

Explore the canonical programs in [`samples/`](samples/) and run a representative harness command:

```bash
voss check samples/classify.voss
voss compile samples/classify.voss
voss do "summarize this repo"
```

Core harness commands: `voss doctor`, `voss do`, `voss chat`, `voss edit`, `voss sessions`, `voss resume` (see [.planning/HARNESS-PLAN.md](.planning/HARNESS-PLAN.md) §2.2 for the full surface).

Optionally opt into the compiled harness with `VOSS_HARNESS=compiled` by populating the local harness cache after install. The default Python harness path works without this step.

```bash
voss compile voss/harness/agent/
```

### Development install

```bash
pip install -e ".[dev]"
```

### Roadmap notes

`npm i -g @vosslang/cli` ships v0.1 with M6 (the npm wrapper bundles a pinned Python 3.12 + the v0.1 wheel; `pip install voss` remains supported). A native Rust shell and Homebrew distribution stay deferred until dogfood signals demand them.

## First run · `voss login`

The first time you run `voss` with no credentials configured, an interactive
sign-in wizard launches automatically. You can also re-run it any time with
`voss login` or `/login` inside the REPL.

```text
╭ voss · sign in ──────────────────────────────────────────╮
│ reason: no credentials found                              │
│                                                           │
│   1  Claude Code OAuth      [ready]                       │
│   2  Codex / ChatGPT OAuth  [needs `codex` CLI]           │
│   3  Paste an API key       [Anthropic or OpenAI]         │
│   q  Quit                                                 │
╰───────────────────────────────────────────────────────────╯
choice [1/2/3/q]:
```

Three paths:

- **Claude Code OAuth** — spawns the `claude` CLI so you can run `/login` inside it,
  then polls `~/.claude/.credentials.json` for the new tokens.
- **Codex / ChatGPT OAuth** — runs `codex login`, then polls `~/.codex/auth.json`.
- **Paste an API key** — Anthropic or OpenAI. The key is stored in the OS
  keychain via [`keyring`](https://pypi.org/project/keyring/) (macOS Keychain,
  Windows Credential Locker, Linux Secret Service). Remove it later with
  `voss logout anthropic` or `voss logout openai`.

Resolution order under `--auth=auto`: voss-stored keychain creds → env vars
(`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) → Claude Code OAuth → Codex auth.
Keychain wins so a forgotten shell export does not silently shadow the key
you set in the wizard.

In non-interactive contexts (CI, piped stdin) the wizard is skipped and
voss exits 2 with the original credential-missing error — set the env vars
or pre-populate the keychain for scripted use.

## Quickstart

The runtime exposes `ProbableValue`, `ContextScope`, `BudgetScope`, `SemanticMatcher`, `VossAgent`, `gather`, `@tool`, and the three memory primitives. See:

- [`examples/raw_python/classify.py`](examples/raw_python/classify.py) — PRD §7.1, confidence-gated classification
- [`examples/raw_python/support.py`](examples/raw_python/support.py) — PRD §7.2, semantic routing + ContextScope fallback
- [`examples/raw_python/research.py`](examples/raw_python/research.py) — PRD §7.3, agent swarm with `gather` + `run_with_budget` fallback

```python
import asyncio
from voss_runtime import ContextScope, ProbableValue

async def classify(text: str) -> str:
    async with ContextScope(token_budget=1000) as ctx:
        await ctx.add(f"Classify: {text}")
        intent: ProbableValue = await ctx.ask(
            "Return only the intent label.", return_type=ProbableValue
        )
        return intent.value if intent @ 0.80 else "unknown"

print(asyncio.run(classify("I want to cancel my subscription")))
```

## Tests

Default (stub providers, hermetic, fast):

```bash
pytest -q -m "not live"
```

With coverage:

```bash
pytest -q -m "not live" --cov=voss_runtime --cov-report=term-missing
```

Live mode (real Anthropic / OpenAI / Ollama — requires API keys + Ollama service):

```bash
pytest -q -m live
```

Live mode runs nightly in CI; stub mode runs on every PR.

## Project Docs

- [PRD.md](PRD.md) — full language specification
- [docs/sdk.md](docs/sdk.md) — embedding Voss in Python apps: `voss_runtime` + `voss.harness` public API contract
- [docs/voss-vs-python.md](docs/voss-vs-python.md) — side-by-side .voss vs raw Python with LOC counts
- [.planning/PROJECT.md](.planning/PROJECT.md) — core value, constraints
- [.planning/REQUIREMENTS.md](.planning/REQUIREMENTS.md) — RUN/GRAM/ANLY/GEN/CLI requirements
- [.planning/ROADMAP.md](.planning/ROADMAP.md) — seven-phase delivery plan (M0–M6)
