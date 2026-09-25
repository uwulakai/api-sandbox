import asyncio
import json
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def load_config() -> dict[str, Any]:
    raw = os.environ.get("MOCK_CONFIG_JSON", "{\"endpoints\": []}")
    return json.loads(raw)


config = load_config()
app = FastAPI(title="API Sandbox Mock Runtime", docs_url=None, redoc_url=None)


@app.get("/_internal/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def handle_request(request: Request, path: str) -> JSONResponse:
    request_path = request.url.path or "/"
    method = request.method.upper()
    endpoint = next(
        (
            item
            for item in config.get("endpoints", [])
            if item.get("enabled", True)
            and item.get("method", "").upper() == method
            and item.get("path") == request_path
        ),
        None,
    )
    if endpoint is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Mock endpoint not found"},
        )

    delay_ms = int(endpoint.get("delay_ms", 0))
    if delay_ms:
        await asyncio.sleep(delay_ms / 1000)

    return JSONResponse(
        status_code=int(endpoint.get("status_code", 200)),
        content=endpoint.get("response_body"),
        headers=endpoint.get("response_headers") or {},
    )
