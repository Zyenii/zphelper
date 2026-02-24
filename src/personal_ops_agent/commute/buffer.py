from __future__ import annotations


def compute_buffer_minutes(weather_state: dict, eta_state: dict, event_importance: str | None = None) -> tuple[int, dict]:
    points = weather_state.get("points", [])
    rain_prob_max_pct = max((float(item.get("rain_probability", 0)) for item in points), default=0.0)
    rain_prob_max = rain_prob_max_pct / 100.0

    base_prep = 7
    add_parking = 3
    add_weather = 5 if rain_prob_max >= 0.4 else 0
    add_peak = 5 if bool(eta_state.get("peak", False)) else 0
    add_importance = 3 if event_importance == "high" else 0

    total = base_prep + add_parking + add_weather + add_peak + add_importance
    total = max(5, min(25, total))
    breakdown = {
        "base_prep": base_prep,
        "add_parking": add_parking,
        "add_weather": add_weather,
        "add_peak": add_peak,
        "add_importance": add_importance,
        "total": total,
    }
    return total, breakdown
