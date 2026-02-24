import os
from datetime import datetime, timezone

import pytest

from personal_ops_agent.connectors.eta import get_eta
from personal_ops_agent.core.settings import get_settings


def test_google_eta_live() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    if not (
        os.getenv("RUN_LIVE_TEST") == "1"
        and settings.ETA_PROVIDER == "google"
        and (settings.GOOGLE_ROUTES_API_KEY or settings.ROUTES_API)
    ):
        pytest.skip("Requires RUN_LIVE_TEST=1, ETA_PROVIDER=google and Google Routes key.")

    eta = get_eta(
        depart_time=datetime.now(timezone.utc),
        origin_text="Philadelphia City Hall",
        destination_text="New York Penn Station",
    )
    assert isinstance(eta.get("eta_minutes"), int)
    assert eta["eta_minutes"] > 0
