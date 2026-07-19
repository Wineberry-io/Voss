use crate::types::events::AgentEvent;

/// A lossy UI-facing projection of the canonical [`AgentEvent`] union.
#[derive(Debug, Clone, PartialEq)]
pub enum UiProjection {
    Connected,
    User(String),
    Thinking(String),
    Plan {
        confidence: f64,
        steps: Vec<String>,
    },
    Tool {
        name: String,
        state: String,
    },
    StreamDelta(String),
    StreamFinalize,
    Final {
        text: String,
        confidence: f64,
    },
    Clarify {
        question: String,
        confidence: f64,
    },
    Status {
        model: String,
        tokens: i64,
        cost_usd: f64,
        ctx_pct: f64,
    },
    Permission {
        id: String,
        tool_name: String,
    },
    Warning(String),
    SessionIdle,
}

impl TryFrom<&AgentEvent> for UiProjection {
    type Error = ();

    fn try_from(event: &AgentEvent) -> Result<Self, Self::Error> {
        match event {
            AgentEvent::ServerConnected(_) => Ok(UiProjection::Connected),
            AgentEvent::UserEvent(event) => Ok(UiProjection::User(event.task.clone())),
            AgentEvent::ThinkingEvent(event) => Ok(UiProjection::Thinking(event.label.clone())),
            AgentEvent::PlanEvent(event) => Ok(UiProjection::Plan {
                confidence: event.confidence,
                steps: event.steps.iter().map(|step| step.name.clone()).collect(),
            }),
            AgentEvent::ToolEvent(event) => Ok(UiProjection::Tool {
                name: event.name.clone(),
                state: event.state.clone(),
            }),
            AgentEvent::StreamDelta(event) => Ok(UiProjection::StreamDelta(event.text.clone())),
            AgentEvent::StreamFinalize(_) => Ok(UiProjection::StreamFinalize),
            AgentEvent::FinalEvent(event) => Ok(UiProjection::Final {
                text: event.text.clone(),
                confidence: event.confidence,
            }),
            AgentEvent::ClarifyEvent(event) => Ok(UiProjection::Clarify {
                question: event.question.clone(),
                confidence: event.confidence,
            }),
            AgentEvent::StatusEvent(event) => Ok(UiProjection::Status {
                model: event.model.clone(),
                tokens: event.tokens,
                cost_usd: event.cost_usd,
                ctx_pct: event.ctx_pct,
            }),
            AgentEvent::PermissionUpdated(event) => Ok(UiProjection::Permission {
                id: event.id.clone(),
                tool_name: event.tool_name.clone(),
            }),
            AgentEvent::WarningEvent(event) => Ok(UiProjection::Warning(event.message.clone())),
            AgentEvent::SessionIdle(_) => Ok(UiProjection::SessionIdle),
            AgentEvent::BannerEvent(_) => Err(()),
            AgentEvent::CognitionLoaded(_) => Err(()),
            AgentEvent::CognitionOverflow(_) => Err(()),
            AgentEvent::PrinciplesOverflow(_) => Err(()),
            AgentEvent::ProbableEvent(_) => Err(()),
            AgentEvent::BudgetUpdated(_) => Err(()),
            AgentEvent::ConfidenceUpdated(_) => Err(()),
            AgentEvent::GateUpdated(_) => Err(()),
            AgentEvent::SwarmAssign(_)
            | AgentEvent::SwarmCandidateReady(_)
            | AgentEvent::SwarmCandidatesReady(_)
            | AgentEvent::SwarmWorkerDone(_)
            | AgentEvent::SwarmGate(_)
            | AgentEvent::SwarmNeedsOperator(_)
            | AgentEvent::SwarmComplete(_) => Err(()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::UiProjection;
    use crate::types::events::*;

    fn object(value: serde_json::Value) -> serde_json::Map<String, serde_json::Value> {
        match value {
            serde_json::Value::Object(map) => map,
            _ => panic!("expected JSON object"),
        }
    }

    #[test]
    fn projection_server_connected() {
        let event = AgentEvent::ServerConnected(ServerConnected { v: 1 });

        assert_eq!(UiProjection::try_from(&event), Ok(UiProjection::Connected));
    }

    #[test]
    fn projection_user() {
        let event = AgentEvent::UserEvent(UserEvent {
            v: 1,
            task: "build".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::User("build".into()))
        );
    }

    #[test]
    fn projection_thinking() {
        let event = AgentEvent::ThinkingEvent(ThinkingEvent {
            v: 1,
            label: "planning".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Thinking("planning".into()))
        );
    }

    #[test]
    fn projection_plan_uses_step_names() {
        let event = AgentEvent::PlanEvent(PlanEvent {
            v: 1,
            confidence: 0.9,
            steps: vec![
                PlanStep {
                    name: "read".into(),
                    args: object(serde_json::json!({"path":"README.md"})),
                },
                PlanStep {
                    name: "write".into(),
                    args: serde_json::Map::new(),
                },
            ],
            cost_usd: 0.01,
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Plan {
                confidence: 0.9,
                steps: vec!["read".into(), "write".into()],
            })
        );
    }

    #[test]
    fn projection_tool() {
        let event = AgentEvent::ToolEvent(ToolEvent {
            v: 1,
            name: "shell".into(),
            args: serde_json::Map::new(),
            summary: "ran".into(),
            state: "ok".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Tool {
                name: "shell".into(),
                state: "ok".into(),
            })
        );
    }

    #[test]
    fn projection_stream_delta() {
        let event = AgentEvent::StreamDelta(StreamDelta {
            v: 1,
            text: "hi".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::StreamDelta("hi".into()))
        );
    }

    #[test]
    fn projection_stream_finalize() {
        let event = AgentEvent::StreamFinalize(StreamFinalize {
            v: 1,
            role: "assistant".into(),
            confidence: Some(0.9),
            cost_usd: Some(0.01),
            timestamp: Some("now".into()),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::StreamFinalize)
        );
    }

    #[test]
    fn projection_final() {
        let event = AgentEvent::FinalEvent(FinalEvent {
            v: 1,
            text: "done".into(),
            confidence: 0.8,
            cost_usd: 0.02,
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Final {
                text: "done".into(),
                confidence: 0.8,
            })
        );
    }

    #[test]
    fn projection_clarify() {
        let event = AgentEvent::ClarifyEvent(ClarifyEvent {
            v: 1,
            question: "which one?".into(),
            confidence: 0.6,
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Clarify {
                question: "which one?".into(),
                confidence: 0.6,
            })
        );
    }

    #[test]
    fn projection_status() {
        let event = AgentEvent::StatusEvent(StatusEvent {
            v: 1,
            model: "model".into(),
            tokens: 42,
            cost_usd: 0.03,
            ctx_pct: 0.4,
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Status {
                model: "model".into(),
                tokens: 42,
                cost_usd: 0.03,
                ctx_pct: 0.4,
            })
        );
    }

    #[test]
    fn projection_permission() {
        let event = AgentEvent::PermissionUpdated(PermissionUpdated {
            v: 1,
            id: "p1".into(),
            tool_name: "edit".into(),
            args: serde_json::Map::new(),
            dimension: "tool".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Permission {
                id: "p1".into(),
                tool_name: "edit".into(),
            })
        );
    }

    #[test]
    fn projection_warning() {
        let event = AgentEvent::WarningEvent(WarningEvent {
            v: 1,
            message: "careful".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::Warning("careful".into()))
        );
    }

    #[test]
    fn projection_session_idle() {
        let event = AgentEvent::SessionIdle(SessionIdle {
            v: 1,
            session_id: "s".into(),
        });

        assert_eq!(
            UiProjection::try_from(&event),
            Ok(UiProjection::SessionIdle)
        );
    }

    #[test]
    fn projection_banner_is_unmapped() {
        let event = AgentEvent::BannerEvent(BannerEvent {
            v: 1,
            model: "m".into(),
            cwd: ".".into(),
            git: "clean".into(),
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_cognition_loaded_is_unmapped() {
        let event = AgentEvent::CognitionLoaded(CognitionLoaded {
            v: 1,
            architecture_tokens: 100,
            constraints_count: 2,
            plans_loaded: 1,
            decisions_loaded: 1,
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_cognition_overflow_is_unmapped() {
        let event = AgentEvent::CognitionOverflow(CognitionOverflow {
            v: 1,
            architecture_tokens: 7000,
            budget: 6000,
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_principles_overflow_is_unmapped() {
        let event = AgentEvent::PrinciplesOverflow(PrinciplesOverflow {
            v: 1,
            principles_tokens: 1500,
            budget: 1000,
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_probable_is_unmapped() {
        let event = AgentEvent::ProbableEvent(ProbableEvent {
            v: 1,
            text: "maybe".into(),
            probability: 0.7,
            alternatives: vec![Alternative {
                text: "other".into(),
                probability: 0.3,
            }],
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_budget_updated_is_unmapped() {
        let event = AgentEvent::BudgetUpdated(BudgetUpdated {
            v: 1,
            session_id: "s".into(),
            spent: 1.0,
            limit: 10.0,
            remaining: 9.0,
            unit: Unit::Usd,
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_confidence_updated_is_unmapped() {
        let event = AgentEvent::ConfidenceUpdated(ConfidenceUpdated {
            v: 1,
            session_id: "s".into(),
            message_id: Some("m".into()),
            score: 0.8,
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }

    #[test]
    fn projection_gate_updated_is_unmapped() {
        let event = AgentEvent::GateUpdated(GateUpdated {
            v: 1,
            session_id: "s".into(),
            gate: "review".into(),
            decision: "pass".into(),
        });

        assert_eq!(UiProjection::try_from(&event), Err(()));
    }
}
