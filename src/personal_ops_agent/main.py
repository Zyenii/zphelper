from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request

from personal_ops_agent.api.routes import router
from personal_ops_agent.core.logging import configure_logging, reset_trace_id, set_trace_id
from personal_ops_agent.core.settings import get_settings

settings = get_settings()
configure_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(title="Personal Ops Agent", version="0.1.0")
app.include_router(router)


@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid4())
    token = set_trace_id(trace_id)
    request.state.trace_id = trace_id

    logger.info("request.start %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info("request.end %s %s", request.method, request.url.path)
    finally:
        reset_trace_id(token)

    response.headers["x-trace-id"] = trace_id
    return response
