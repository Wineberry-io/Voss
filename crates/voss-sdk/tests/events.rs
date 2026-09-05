use serde_json::json;
use voss_sdk::types::events::{AgentEvent, ServerConnected, SessionIdle};

#[test]
fn agent_event_deserializes_by_type_tag() {
    let event: AgentEvent =
        serde_json::from_value(json!({"type": "stream.delta", "text": "hi"})).unwrap();

    match event {
        AgentEvent::StreamDelta(payload) => {
            assert_eq!(payload.text, "hi");
            assert_eq!(payload.v, 1);
        }
        other => panic!("expected stream delta, got {other:?}"),
    }
}

#[test]
fn agent_event_serializes_with_wire_type() {
    let event = AgentEvent::SessionIdle(SessionIdle {
        session_id: "s1".into(),
        v: 1,
    });

    let value = serde_json::to_value(event).unwrap();
    assert_eq!(value["type"], "session.idle");
    assert_eq!(value["session_id"], "s1");
}

#[test]
fn agent_event_exhaustive_match_includes_control_variant() {
    let event = AgentEvent::ServerConnected(ServerConnected { v: 1 });
    let name = match event {
        AgentEvent::ServerConnected(_) => "server.connected",
        AgentEvent::SessionIdle(_) => "session.idle",
        AgentEvent::PermissionUpdated(_) => "permission.updated",
        AgentEvent::BannerEvent(_) => "banner",
        AgentEvent::UserEvent(_) => "user",
        AgentEvent::ThinkingEvent(_) => "thinking",
        AgentEvent::PlanEvent(_) => "plan",
        AgentEvent::ToolEvent(_) => "tool",
        AgentEvent::ClarifyEvent(_) => "clarify",
        AgentEvent::FinalEvent(_) => "final",
        AgentEvent::StreamDelta(_) => "stream.delta",
        AgentEvent::StreamFinalize(_) => "stream.finalize",
        AgentEvent::StatusEvent(_) => "status",
        AgentEvent::CognitionLoaded(_) => "cognition_loaded",
        AgentEvent::CognitionOverflow(_) => "cognition_overflow",
        AgentEvent::PrinciplesOverflow(_) => "principles_overflow",
        AgentEvent::InstructionsOverflow(_) => "instructions_overflow",
        AgentEvent::WarningEvent(_) => "warning",
        AgentEvent::ProbableEvent(_) => "probable",
        AgentEvent::BudgetUpdated(_) => "budget.updated",
        AgentEvent::ConfidenceUpdated(_) => "confidence.updated",
        AgentEvent::GateUpdated(_) => "gate.updated",
        AgentEvent::SwarmAssign(_) => "swarm.assign",
        AgentEvent::SwarmWorkerDone(_) => "swarm.worker_done",
        AgentEvent::SwarmGate(_) => "swarm.gate",
        AgentEvent::SwarmNeedsOperator(_) => "swarm.needs_operator",
        AgentEvent::SwarmComplete(_) => "swarm.complete",
    };

    assert_eq!(name, "server.connected");
}
