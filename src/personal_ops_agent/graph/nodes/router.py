from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.router.router import dispatch_intent


def router_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    decision = dispatch_intent(message)
    return {
        "intent": decision.intent,
        "route_confidence": decision.confidence,
        "route_reason": decision.reason,
    }
