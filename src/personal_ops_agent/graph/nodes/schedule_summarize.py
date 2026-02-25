from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from personal_ops_agent.graph.state import AgentState
from personal_ops_agent.todo.todoist_tool import TodoistError, list_todoist_tasks


class BufferSuggestion(BaseModel):
    type: str
    between: list[str] | None = None
    events: list[str] | None = None
    gap_minutes: int | None = None
    start: str | None = None
    end: str | None = None
    minutes: int | None = None
    recommendation: str


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _event_time_text(event: dict) -> str:
    if event.get("is_all_day"):
        return "All day"
    start = _parse_iso(event["start"]).strftime("%H:%M")
    end = _parse_iso(event["end"]).strftime("%H:%M")
    return f"{start}-{end}"


def _build_summary(events: list[dict]) -> str:
    if not events:
        return "No events found for this time window."

    lines = [f"You have {len(events)} event(s):"]
    for event in events:
        location = f" @ {event['location']}" if event.get("location") else ""
        lines.append(f"- {_event_time_text(event)} {event['title']}{location}")
    return "\n".join(lines)


def _build_todo_lines(todos: list[dict]) -> list[str]:
    if not todos:
        return []
    lines = [f"Todo reminders ({len(todos)}):"]
    for todo in todos:
        due_text = f" due {todo['due']}" if todo.get("due") else ""
        lines.append(f"- P{todo.get('priority', 2)} {todo.get('title', '')}{due_text}")
    return lines


def _build_buffer_suggestions(events: list[dict]) -> list[dict]:
    suggestions: list[BufferSuggestion] = []
    ordered = sorted(events, key=lambda item: _parse_iso(item["start"]))

    for current, nxt in zip(ordered, ordered[1:]):
        current_end = _parse_iso(current["end"])
        next_start = _parse_iso(nxt["start"])
        gap_minutes = int((next_start - current_end).total_seconds() // 60)

        if gap_minutes < 0:
            suggestions.append(
                BufferSuggestion(
                    type="conflict",
                    events=[current["id"], nxt["id"]],
                    recommendation="These events overlap.",
                )
            )
            continue

        if gap_minutes < 15:
            suggestions.append(
                BufferSuggestion(
                    type="buffer",
                    between=[current["id"], nxt["id"]],
                    gap_minutes=gap_minutes,
                    recommendation=(
                        f"Consider adding 15 min buffer between {current['title']} and {nxt['title']}."
                    ),
                )
            )

        if gap_minutes >= 60:
            suggestions.append(
                BufferSuggestion(
                    type="free_slot",
                    start=current_end.isoformat(),
                    end=next_start.isoformat(),
                    minutes=gap_minutes,
                    recommendation="You have a free slot that could be used for deep work or rest.",
                )
            )

    return [item.model_dump(exclude_none=True) for item in suggestions]


def schedule_summarize_node(state: AgentState) -> AgentState:
    calendar_state = state.get("calendar", {})
    events = calendar_state.get("events", [])
    error_message = calendar_state.get("error")

    if error_message:
        summary = f"Unable to read calendar: {error_message}"
        return {"schedule": {"summary": summary, "buffer_suggestions": []}}

    summary = _build_summary(events)
    suggestions = _build_buffer_suggestions(events)
    todos: list[dict] = []
    todo_error: str | None = None
    try:
        todos = [item.model_dump() for item in list_todoist_tasks(trace_id=state.get("trace_id"), limit=5)]
    except TodoistError as exc:
        todo_error = str(exc)

    todo_lines = _build_todo_lines(todos)
    if todo_lines:
        summary = f"{summary}\n\n" + "\n".join(todo_lines)

    schedule_state: dict[str, object] = {"summary": summary, "buffer_suggestions": suggestions, "todos": todos}
    if todo_error:
        schedule_state["todo_error"] = todo_error
    return {"schedule": schedule_state}
