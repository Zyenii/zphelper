from __future__ import annotations

from datetime import datetime

from personal_ops_agent.graph.state import AgentState


def _format_weather_output(state: AgentState) -> str | None:
    if state.get("intent") != "weather_summary":
        return None
    weather = state.get("weather", {})
    points = weather.get("points", [])
    if not points:
        return "这个时间段暂无可用天气数据。"

    rain_max = max(int(item.get("rain_probability", 0)) for item in points)
    temp_avg = round(sum(float(item.get("apparent_temperature", 0.0)) for item in points) / len(points), 1)
    wind_max = max(float(item.get("wind_kph", 0.0)) for item in points)

    start = weather.get("window_start")
    end = weather.get("window_end")
    window_text = ""
    try:
        start_dt = datetime.fromisoformat(start).strftime("%m-%d %H:%M") if start else ""
        end_dt = datetime.fromisoformat(end).strftime("%m-%d %H:%M") if end else ""
        if start_dt and end_dt:
            window_text = f"{start_dt} 到 {end_dt}"
    except Exception:
        window_text = ""

    if rain_max >= 60:
        advice = "降雨概率较高，建议带伞并预留出行缓冲。"
    elif rain_max >= 30:
        advice = "有一定降雨可能，建议带折叠伞。"
    else:
        advice = "降雨概率较低。"

    prefix = f"{window_text}：" if window_text else ""
    return f"{prefix}最高降雨概率 {rain_max}%，平均体感温度 {temp_avg}°C，最大风速 {wind_max:.1f} km/h。{advice}"


def final_node(state: AgentState) -> AgentState:
    weather_output = _format_weather_output(state)
    if weather_output:
        return {"output": weather_output}

    if state.get("output"):
        return {"output": state["output"]}

    commute_recommendation = state.get("commute", {}).get("recommendation")
    if commute_recommendation:
        leave_time = commute_recommendation.get("leave_time", "")
        mode = commute_recommendation.get("transport_mode", "unknown")
        destination = commute_recommendation.get("destination", "destination")
        advice = commute_recommendation.get("weather_advice", "")
        return {"output": f"Leave by {leave_time} to {destination} via {mode}. {advice}"}

    schedule_summary = state.get("schedule", {}).get("summary")
    if schedule_summary:
        return {"output": schedule_summary}

    user_message = state.get("user_message", "")
    return {"output": f"OK: {user_message}"}
