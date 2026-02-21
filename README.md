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
