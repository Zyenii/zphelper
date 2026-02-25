from __future__ import annotations

from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.eval.metrics import get_regression_snapshot
from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.todo.schemas import TodoDraft
from personal_ops_agent.todo.todoist_tool import TodoistError, create_todoist_task


def todo_write_node(state: AgentState) -> AgentState:
    settings = get_settings()
    draft_raw = state.get("todo", {}).get("draft")
    if not isinstance(draft_raw, dict):
        return {"output": "Unable to parse todo draft.", "todo": {"write": {"success": False}}}

    draft = TodoDraft.model_validate(draft_raw)
    if draft.confidence < settings.TODO_CONFIDENCE_THRESHOLD:
        question = (
            f"我解析到待办草稿：'{draft.title}'"
            f"{f'，截止 {draft.due}' if draft.due else ''}。"
            "请确认是否创建？"
        )
        return {
            "output": question,
            "todo": {
                "draft": draft.model_dump(),
                "write": {"success": False, "blocked_by_confidence": True, "clarification_question": question},
            },
            "eval": {"todo_regression": get_regression_snapshot()},
        }

    try:
        created = create_todoist_task(draft, trace_id=state.get("trace_id"))
    except TodoistError as exc:
        return {
            "output": f"Todo creation failed: {exc}",
            "todo": {"draft": draft.model_dump(), "write": {"success": False, "error": str(exc)}},
            "eval": {"todo_regression": get_regression_snapshot()},
        }

    return {
        "output": f"Created todo '{draft.title}'.",
        "todo": {
            "draft": draft.model_dump(),
            "write": {"success": True, "task": created.model_dump()},
        },
        "eval": {"todo_regression": get_regression_snapshot()},
    }
