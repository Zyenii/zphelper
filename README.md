# Personal Ops Agent (M1 + M2)

## Requirements
- Python 3.11+

## Setup
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
copy .env.example .env    # PowerShell: Copy-Item .env.example .env
pip install -e .[dev]
```

## Run API
```bash
uvicorn personal_ops_agent.main:app --reload
```

## Verify M2 (mock calendar)
- Health:
```bash
curl http://127.0.0.1:8000/health
```
- Chat schedule summary:
```bash
curl -X POST "http://127.0.0.1:8000/chat" -H "Content-Type: application/json" -d "{\"message\":\"what's my schedule today?\"}"
```

The `/chat` response includes:
- `trace_id`
- `intent` (`schedule_summary` for schedule queries)
- `output` (human-readable summary)
- `state.calendar.events`
- `state.schedule.summary`
- `state.schedule.buffer_suggestions`

## Verify M3 (deterministic commute + weather)
Set mock flags in `.env`:
```env
MOCK_WEATHER=1
WEATHER_MODE=mock
WEATHER_FIXTURE_PATH=tests/fixtures/sample_weather.json
MOCK_ETA=1
ETA_MODE=mock
ETA_FIXTURE_PATH=tests/fixtures/sample_eta.json
```

Use real weather (Open-Meteo) by setting:
```env
MOCK_WEATHER=0
WEATHER_MODE=open_meteo
WEATHER_LATITUDE=39.9526
WEATHER_LONGITUDE=-75.1652
WEATHER_FORECAST_HOURS=6
```

Call commute intent:
```bash
curl -X POST "http://127.0.0.1:8000/chat" -H "Content-Type: application/json" -d "{\"message\":\"我几点出发去下一个日程？\"}"
```

M3 response state includes:
- `weather.summary`
- `commute.recommendation.transport_mode`
- `commute.recommendation.leave_time`
- `commute.recommendation.weather_advice`

Weather queries are also supported:
- `今天天气怎么样`
- `明天下午天气怎么样`
- `Can you show weather for this weekend?`

## Enable LLM Time-Window Parsing (lazy fallback)
Time-window parsing for schedule intent is rule-first, and only calls LLM when rules cannot resolve a range.

Set `.env` values:
```env
LLM_TIMEWINDOW=1
LLM_TIMEWINDOW_MODEL=gpt-5-mini
LLM_TIMEWINDOW_THRESHOLD=0.75
DEFAULT_TIMEZONE=America/New_York
OPENAI_API_KEY=your_key
```

Live tests are skipped by default. To run:
```bash
RUN_LLM_LIVE_TEST=1 pytest -q tests/test_timewindow_llm_live.py
```

## Tests
```bash
pytest -q
```

## Enable Google Calendar OAuth Mode
Install OAuth dependencies:
```bash
pip install -e .[google]
```

Set `.env` values:
```env
MOCK_CALENDAR=0
GOOGLE_CALENDAR_MODE=oauth
GOOGLE_CALENDAR_ID=primary
GOOGLE_OAUTH_CLIENT_SECRET_JSON=path/to/client_secret.json
GOOGLE_OAUTH_TOKEN_JSON=path/to/token.json
```

Then run:
```bash
uvicorn personal_ops_agent.main:app --reload
```

First OAuth run will open a browser for consent and save token JSON.
