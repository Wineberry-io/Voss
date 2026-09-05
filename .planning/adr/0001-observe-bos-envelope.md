# ADR 0001: Observe events use the BOS3 envelope

**Date:** 2026-09-05
**Status:** Accepted
**Plan:** `.planning/CANVAS-OBSERVE-INSTRUCTIONS-PLAN.md` §0 decision 3

## Context

The Observe brief (OBS-03) proposes a fresh event envelope: `event_id`, `event_type`, `occurred_at`, `received_at`, `caused_by_event_id`, `run_id`, `origin`, `repository_state_id`, `evidence_refs`. BOS3 (`.planning/BOS-EVENT-SCHEMA.md`, `.planning/schemas/bos-events.schema.json`) already defines a bitemporal, append-only envelope with `event_id`, `event_type`, `category`, `event_time`, `ingest_time`, `trace_id`, `parent_event_id`, `caused_by`, `actor`, `source_ref`, `external_identity_ref`, `payload`. The two overlap on every load-bearing field. BOS today is projection-only: `bos_events.py` reads existing records and never receives live events.

## Decision

Observe events are a BOS category. There is no second envelope.

| Brief field | BOS field |
|---|---|
| `occurred_at` | `event_time` |
| `received_at` | `ingest_time` (assigned at write, never source-carried) |
| `caused_by_event_id` | `caused_by` |
| `origin` | `actor` (`developer` / `voss` / `external` / `unknown`) |
| `adapter_id`, `adapter_session_id` | `source_ref = {source: "adapter", ref: adapter_session_id}` plus `payload.adapter_id` |
| `run_id` | `trace_id` join when a harness run exists; else payload |
| `repository_id`, `worktree_id`, `repository_state_id`, `command_id`, `evidence_refs` | `payload` (enumerated per event type) |

Event types: `command.started`, `command.completed`, `command.failed`, `test.failed` under `category="command"`; later `git.diff.changed`, `git.branch.changed`. Findings are BOS4 decisions. Dismiss and resolve write BOS5 outcome labels.

Observe's SQLite store is the operational index; the BOS ledger (`bos_ledger.py`) receives every persisted Observe event through a new live-emit path that assigns `ingest_time` and appends. BOS stays append-only; Observe never mutates ledger rows.

## Consequences

- Observe is the first live BOS emitter. BOS4/BOS5 tooling and the LEM corpus get real developer events without a translation layer.
- `bos_events.py` gains an emit path and must keep the "never write back to sources" rule: Observe rows are the source, the ledger is the projection.
- Contract generation follows the existing pydantic → `contracts/*.schema.json` path; the Observe models extend the BOS envelope model rather than redefining it.
- Security invariants from BOS3 apply to Observe payloads: no secrets, no file contents in file-category payloads, redaction before durable write.
