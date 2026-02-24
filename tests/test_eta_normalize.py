from personal_ops_agent.connectors.eta import _normalize_place_text


def test_normalize_airport_keyword() -> None:
    assert _normalize_place_text("airport") == "Philadelphia International Airport"
