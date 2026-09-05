"""Protocol event models (HYBRID-REFACTOR-PLAN H1.2).

Pydantic v2 discriminated union mirroring the wire contract in
`.planning/PROTOCOL.md` §6. Each member's `type` literal is BOTH the SSE
`event:` name and the serde discriminator. The core 13 mirror the existing
`JsonRenderer` emit shapes (`voss/harness/render.py:493-567`) field-for-field
so the server emits exactly what the harness already produces; the rest are
Voss-native additions (`probable`/`budget`/`confidence`) and server-only
control events (`server.connected`, `permission.updated`, `session.idle`).

Serialize per-event with `.model_dump_json()`. Parse an unknown event with
`AgentEventAdapter.validate_json(...)`.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

PROTOCOL_VERSION = 1


class _Base(BaseModel):
    """Shared envelope. `v` is the protocol version (PROTOCOL.md §1)."""

    model_config = ConfigDict(extra="ignore")
    v: int = PROTOCOL_VERSION


# --- control (server-only) -------------------------------------------------


class ServerConnected(_Base):
    type: Literal["server.connected"] = "server.connected"


class SessionIdle(_Base):
    type: Literal["session.idle"] = "session.idle"
    session_id: str


class PermissionUpdated(_Base):
    type: Literal["permission.updated"] = "permission.updated"
    id: str
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    dimension: str = "tool"  # tool | confidence | budget


# --- core 13 (mirror JsonRenderer) ----------------------------------------


class BannerEvent(_Base):
    type: Literal["banner"] = "banner"
    model: str
    cwd: str
    git: str


class UserEvent(_Base):
    type: Literal["user"] = "user"
    task: str


class ThinkingEvent(_Base):
    type: Literal["thinking"] = "thinking"
    label: str


class PlanStep(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class PlanEvent(_Base):
    type: Literal["plan"] = "plan"
    confidence: float
    steps: list[PlanStep] = Field(default_factory=list)
    cost_usd: float


class ToolEvent(_Base):
    type: Literal["tool"] = "tool"
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    state: str  # ok | error | pending


class ClarifyEvent(_Base):
    type: Literal["clarify"] = "clarify"
    question: str
    confidence: float


class FinalEvent(_Base):
    type: Literal["final"] = "final"
    text: str
    confidence: float
    cost_usd: float


class StreamDelta(_Base):
    type: Literal["stream.delta"] = "stream.delta"
    text: str


class StreamFinalize(_Base):
    type: Literal["stream.finalize"] = "stream.finalize"
    role: str
    confidence: float | None = None
    cost_usd: float | None = None
    timestamp: str | None = None
    # NOTE: accumulated_text is intentionally dropped (matches JsonRenderer).


class StatusEvent(_Base):
    type: Literal["status"] = "status"
    model: str
    tokens: int
    cost_usd: float
    ctx_pct: float


class CognitionLoaded(_Base):
    type: Literal["cognition_loaded"] = "cognition_loaded"
    architecture_tokens: int
    constraints_count: int
    plans_loaded: int = 0
    decisions_loaded: int = 0


class CognitionOverflow(_Base):
    type: Literal["cognition_overflow"] = "cognition_overflow"
    architecture_tokens: int
    budget: int = 6000


class PrinciplesOverflow(_Base):
    type: Literal["principles_overflow"] = "principles_overflow"
    principles_tokens: int
    budget: int = 1000


class InstructionsOverflow(_Base):
    type: Literal["instructions_overflow"] = "instructions_overflow"
    instructions_tokens: int
    budget: int = 4000
    truncated: list[str] = Field(default_factory=list)


class WarningEvent(_Base):
    type: Literal["warning"] = "warning"
    message: str


# --- Voss-native (additive) ------------------------------------------------


class Alternative(BaseModel):
    text: str
    probability: float


class ProbableEvent(_Base):
    type: Literal["probable"] = "probable"
    text: str
    probability: float
    alternatives: list[Alternative] = Field(default_factory=list)


class BudgetUpdated(_Base):
    type: Literal["budget.updated"] = "budget.updated"
    session_id: str
    spent: float
    limit: float
    remaining: float
    unit: Literal["tokens", "usd"] = "tokens"


class ConfidenceUpdated(_Base):
    type: Literal["confidence.updated"] = "confidence.updated"
    session_id: str
    message_id: str | None = None
    score: float


class GateUpdated(_Base):
    type: Literal["gate.updated"] = "gate.updated"
    session_id: str
    gate: str
    decision: str


# --- swarm (V25 VSWARM-02) -------------------------------------------------
# First-class swarm event plane (D-03). Every model carries `swarm_id` so V24's
# swarmReconcile can consume them directly off the existing SSE bus.


class _SwarmBase(_Base):
    """Swarm events fan out to EVERY session queue (app.py `_emit_swarm_event`),
    so a single logical event is delivered N times — once per swarm member. `eid`
    is generated ONCE at construction and shared across all fan-out copies (the
    same instance is enqueued to every queue), giving consumers a stable key to
    dedup the broadcast duplicates without dropping genuine later re-events."""

    eid: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])


class SwarmAssign(_SwarmBase):
    type: Literal["swarm.assign"] = "swarm.assign"
    swarm_id: str
    task_id: str
    session_id: str  # builder session that owns this task
    owned_files: list[str] = Field(default_factory=list)
    role: str


class SwarmWorkerDone(_SwarmBase):
    type: Literal["swarm.worker_done"] = "swarm.worker_done"
    swarm_id: str
    task_id: str
    session_id: str
    summary: str | None = None


class SwarmGate(_SwarmBase):
    type: Literal["swarm.gate"] = "swarm.gate"
    swarm_id: str
    task_id: str
    gate_type: str  # "ownership_denied" | "reviewer_reject"
    detail: str


class SwarmNeedsOperator(_SwarmBase):
    type: Literal["swarm.needs_operator"] = "swarm.needs_operator"
    swarm_id: str
    task_id: str
    session_id: str
    tool_name: str
    path: str | None = None  # the denied file path


class SwarmComplete(_SwarmBase):
    type: Literal["swarm.complete"] = "swarm.complete"
    swarm_id: str
    task_count: int
    summary: str | None = None


# --- discriminated union ---------------------------------------------------

AgentEvent = Annotated[
    Union[
        ServerConnected,
        SessionIdle,
        PermissionUpdated,
        BannerEvent,
        UserEvent,
        ThinkingEvent,
        PlanEvent,
        ToolEvent,
        ClarifyEvent,
        FinalEvent,
        StreamDelta,
        StreamFinalize,
        StatusEvent,
        CognitionLoaded,
        CognitionOverflow,
        PrinciplesOverflow,
        InstructionsOverflow,
        WarningEvent,
        ProbableEvent,
        BudgetUpdated,
        ConfidenceUpdated,
        GateUpdated,
        SwarmAssign,
        SwarmWorkerDone,
        SwarmGate,
        SwarmNeedsOperator,
        SwarmComplete,
    ],
    Field(discriminator="type"),
]

AgentEventAdapter: TypeAdapter[AgentEvent] = TypeAdapter(AgentEvent)


class EventEnvelope(BaseModel):
    """OpenAPI schema anchor (H1.14).

    Forced into the OpenAPI components so a typed client codegens a tagged
    enum over the full event union, even though no route returns it directly.
    """

    event: AgentEvent
