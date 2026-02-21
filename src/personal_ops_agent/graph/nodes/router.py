from personal_ops_agent.graph.state import AgentState

SCHEDULE_KEYWORDS = {
    "schedule",
    "calendar",
    "agenda",
    "today",
    "tomorrow",
    "日程",
    "安排",
    "今天",
    "明天",
}


def router_node(state: AgentState) -> AgentState:
    message = state.get("user_message", "")
    lowered = message.lower()
    if any(keyword in lowered or keyword in message for keyword in SCHEDULE_KEYWORDS):
        return {"intent": "schedule_summary"}
    return {"intent": "unknown"}
