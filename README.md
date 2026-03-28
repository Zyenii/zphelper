# Personal Ops Agent (M1-M5)

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

## Enable Planner Mode
Planner mode adds a bounded LLM planner in front of the existing router. When enabled, the model outputs a structured action plan and the executor runs those actions in order. If planning fails or confidence is too low, the system falls back to the existing rule/intent workflow.

Set `.env` values:
```env
LLM_PLANNER=1
LLM_PLANNER_MODEL=gpt-5-mini
LLM_PLANNER_THRESHOLD=0.75
LLM_PLANNER_MAX_ACTIONS=4
OPENAI_API_KEY=your_key
```

Planner output is returned in `/chat` response state:
- `state.plan`
- `state.plan_confidence`
- `state.plan_reason`
- `state.plan_used`
- `state.memory`

For harder mixed-language commute destinations, optional location extraction fallback can be enabled:
```env
LLM_LOCATION_EXTRACTOR=1
LLM_LOCATION_EXTRACTOR_MODEL=gpt-5-mini
LLM_LOCATION_EXTRACTOR_THRESHOLD=0.75
```

## Long-Term Memory
The repo now includes a lightweight long-term memory store for stable user context.

Configure:
```env
MEMORY_ENABLED=1
MEMORY_STORE_PATH=data/user_memory.json
```

Seed file template:
- `data/user_memory.example.json`

Memory is currently used for:
- planner context (user profile, place aliases, preferences)
- commute resolution:
  - `home_location`
  - `place_aliases`
  - `extra_buffer_minutes`
- checklist personalization:
  - rain / cold thresholds
  - saved prep items for meetings / interviews / presentations

The live memory file is auto-created when missing and is gitignored:
- `data/user_memory.json`

## Tests
```bash
pytest -q
```

## M4 Todo Automation
Intent keywords: `todo`, `add task`, `remind me`, `待办`, `提醒我`.

Required env for real writes:
```env
TODOIST_API_TOKEN=your_todoist_token
TODO_PARSER_MODEL=gpt-5-mini
TODO_CONFIDENCE_THRESHOLD=0.7
TODO_PARSE_RETRIES=2
```

Behavior:
- Parse user text -> strict Todo schema validation.
- Retry up to 2 times on schema/JSON failures.
- Confidence gate: below threshold asks one clarification question and does not write.
- On success, writes to Todoist REST API and returns created task metadata.

Example:
```bash
curl -X POST "http://127.0.0.1:8000/chat" -H "Content-Type: application/json" -d "{\"message\":\"提醒我明天交作业\"}"
```

M4 10-case scaffold:
```bash
python tests/m4_todo_eval_runner.py
```
It prints pass/fail for:
- schema validity
- whether a write would occur given confidence threshold

## M5 Leaving Checklist
Intent keywords: `what should i bring`, `leaving checklist`, `带什么`, `出门清单`.

Flow:
- fetch next event (calendar)
- fetch weather
- fetch ETA/commute recommendation
- deterministic checklist rules + optional LLM enrichment
- strict schema validation with retry

Output fields:
- `checklist.summary`
- `checklist.items`
- `checklist.reasons`
- `checklist.confidence`

Two example outputs:
1. Rainy scenario:
```text
Weekly sync at 2026-03-01T14:00:00+00:00 in Office. Suggested leave time: 2026-03-01T13:20:00+00:00.
Items: [Umbrella, Phone, Wallet, Keys]
```
2. Cold + interview scenario:
```text
Interview loop at 2026-03-01T15:00:00+00:00 in HQ. Suggested leave time: 2026-03-01T14:10:00+00:00.
Items: [Warm coat and gloves, ID / badge, Laptop and charger, Transit card / ride-share app ready]
```

M5 scenario tests:
```bash
pytest -q tests/test_checklist_m5.py
```

## Optional Postgres logging
Set:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
PROMPT_VERSION=v1
```
When configured, parser/checklist/todo-write logs are persisted with:
- prompt_version
- tokens
- latency
- tool success/failure
- validation errors
- confidence

## M7 Observability + Regression
Included in current codebase:
- Unified structured log events (`event` + fields, always with `trace_id`)
- Runtime telemetry in `/chat` response:
  - `state.eval.runtime.llm_calls`
  - `state.eval.runtime.input_tokens`
  - `state.eval.runtime.output_tokens`
  - `state.eval.runtime.total_tokens`
  - `state.eval.runtime.estimated_cost_usd`
  - `state.eval.runtime.retry_count`
  - `state.eval.runtime.llm_latency_ms`
  - `state.eval.runtime.request_latency_ms`
  - `state.eval.runtime.llm_error_count`
- Fixed 10-case regression fixture: `tests/fixtures/golden_m7_v1.json`
- One-click regression runner: `scripts/run_regression.py`

Run one command:
```bash
python scripts/run_regression.py
```

## Agent Evaluation Framework
The repo now includes a staged evaluation harness for the bounded planner-agent.

What it checks per query:
- intent routing correctness
- planned tool-chain correctness
- execution fidelity (`executed_actions` follows `planned_actions`)
- final response consistency with structured state
- required structured fields coverage
- operational metrics:
  - LLM calls
  - total tokens
  - request latency
  - estimated cost

Fixture:
- `tests/fixtures/agent_eval_v1.json`

Runner:
```bash
python scripts/run_agent_eval.py
```

Outputs:
- `artifacts/agent_eval_workflow_baseline.json`
- `artifacts/agent_eval_planner_variant.json` (only when `OPENAI_API_KEY` is available)

Design notes:
- Baseline variant disables planner and evaluates the deterministic workflow path.
- Planner variant enables bounded planning and compares stage-level metrics and end-to-end success.
- This supports A/B evaluation of cost-quality-latency tradeoffs instead of checking final text only.

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
