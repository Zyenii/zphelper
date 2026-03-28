from __future__ import annotations

from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.todo.todoist_tool import TodoistError, list_todoist_tasks


def _build_todo_summary(tasks: list[dict]) -> str:
    if not tasks:
        return "You have no visible Todoist tasks right now."

    lines = [f"You have {len(tasks)} todo item(s):"]
    for task in tasks:
        due_text = f" due {task['due']}" if task.get("due") else ""
        lines.append(f"- P{task.get('priority', 2)} {task.get('title', '')}{due_text}")
    return "\n".join(lines)


def todo_read_node(state: AgentState) -> AgentState:
    try:
        tasks = [item.model_dump() for item in list_todoist_tasks(trace_id=state.get("trace_id"), limit=10)]
    except TodoistError as exc:
        error_message = str(exc)
        return {
            "todo": {"tasks": [], "error": error_message},
            "output": f"Unable to read Todoist tasks: {error_message}",
        }

    summary = _build_todo_summary(tasks)
    return {
        "todo": {"tasks": tasks, "summary": summary},
        "output": summary,
    }
