from __future__ import annotations

from personal_ops_agent.graph.state import AgentState


def weather_summarize_node(state: AgentState) -> AgentState:
    weather_state = state.get("weather", {})
    summary = weather_state.get("summary", "")
    points = weather_state.get("points", [])
    if not summary:
        if points:
            max_rain = max(int(item.get("rain_probability", 0)) for item in points)
            max_wind = max(float(item.get("wind_kph", 0.0)) for item in points)
            summary = f"Weather in selected window: rain max {max_rain}%, wind max {max_wind:.1f}kph."
        else:
            summary = "No weather data available for the selected window."
    return {"weather": {**weather_state, "summary": summary}, "output": summary}
