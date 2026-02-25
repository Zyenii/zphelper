from personal_ops_agent.graph.nodes.schedule_summarize import schedule_summarize_node


def test_schedule_summary_includes_todo_lines(monkeypatch) -> None:
    monkeypatch.setattr(
        "personal_ops_agent.graph.nodes.schedule_summarize.list_todoist_tasks",
        lambda trace_id, limit=5: [
            type("T", (), {"model_dump": lambda self: {"task_id": "1", "title": "Submit report", "due": "2026-02-26", "priority": 4, "url": None}})(),  # noqa: E501
            type("T", (), {"model_dump": lambda self: {"task_id": "2", "title": "Buy milk", "due": None, "priority": 2, "url": None}})(),
        ],
    )

    state = {
        "trace_id": "t1",
        "calendar": {
            "events": [
                {
                    "id": "e1",
                    "title": "Standup",
                    "start": "2026-02-25T13:00:00+00:00",
                    "end": "2026-02-25T13:30:00+00:00",
                }
            ]
        },
    }
    result = schedule_summarize_node(state)
    summary = result["schedule"]["summary"]
    assert "Todo reminders (2)" in summary
    assert "Submit report" in summary
    assert isinstance(result["schedule"]["todos"], list)
    assert len(result["schedule"]["todos"]) == 2
