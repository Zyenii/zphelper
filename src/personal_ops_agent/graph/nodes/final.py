from personal_ops_agent.graph.state import AgentState


def final_node(state: AgentState) -> AgentState:
    schedule_summary = state.get("schedule", {}).get("summary")
    if schedule_summary:
        return {"output": schedule_summary}

    user_message = state.get("user_message", "")
    return {"output": f"OK: {user_message}"}
