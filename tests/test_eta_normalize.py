from personal_ops_agent.connectors.eta import _candidate_addresses, _normalize_place_text


def test_normalize_airport_keyword() -> None:
    assert _normalize_place_text("airport") == "Philadelphia International Airport"


def test_candidate_addresses_adds_us_suffix_for_airport() -> None:
    candidates = _candidate_addresses("airport")
    assert "Philadelphia International Airport" in candidates
    assert "Philadelphia International Airport, USA" in candidates
