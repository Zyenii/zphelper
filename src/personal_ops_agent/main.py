from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from personal_ops_agent.api.routes import router
from personal_ops_agent.core.logging import configure_logging, log_event, reset_trace_id, set_trace_id
from personal_ops_agent.core.settings import get_settings
from personal_ops_agent.core.telemetry import reset_runtime_stats, restore_runtime_stats

settings = get_settings()
configure_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(title="Personal Ops Agent", version="0.1.0")
app.include_router(router)

_STATIC_DIR = Path(__file__).resolve().parent / "web"
app.mount("/web", StaticFiles(directory=str(_STATIC_DIR)), name="web")


@app.get("/")
def web_ui() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid4())
    token = set_trace_id(trace_id)
    stats_token = reset_runtime_stats()
    request.state.trace_id = trace_id

    log_event(logger, "request.start", method=request.method, path=request.url.path)
    try:
        response = await call_next(request)
        log_event(logger, "request.end", method=request.method, path=request.url.path)
    finally:
        restore_runtime_stats(stats_token)
        reset_trace_id(token)

    response.headers["x-trace-id"] = trace_id
    return response
