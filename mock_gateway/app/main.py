import logging
import os
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


logger = logging.getLogger("api_sandbox.mock_gateway")

RUNTIME_PORT = int(os.getenv("MOCK_RUNTIME_PORT", "8080"))
RUNTIME_CONTAINER_PREFIX = os.getenv(
    "MOCK_RUNTIME_CONTAINER_PREFIX",
    "api-sandbox-mock-",
)
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        # The preflight check below rejects removed runtimes quickly. Keep the
        # read timeout long enough for the supported 60-second mock delay.
        timeout=httpx.Timeout(connect=2.0, read=65.0, write=30.0, pool=2.0),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=1.0,
        ),
        follow_redirects=False,
    )
    logger.info(
        "Mock gateway startup completed: runtime_port=%s container_prefix=%s",
        RUNTIME_PORT,
        RUNTIME_CONTAINER_PREFIX,
    )
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        logger.info("Mock gateway shutdown completed")


app = FastAPI(
    title="API Sandbox Mock Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


def runtime_container_name(mock_id: str) -> str:
    return f"{RUNTIME_CONTAINER_PREFIX}{mock_id}"


def forwarded_request_headers(request: Request, request_id: str) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
        and key.lower() not in {"host", "content-length"}
    }
    headers["X-Request-ID"] = request_id
    headers["X-Forwarded-Host"] = request.headers.get("host", "")
    headers["X-Forwarded-Proto"] = request.headers.get(
        "x-forwarded-proto",
        request.url.scheme,
    )
    # A runtime container can disappear while the gateway is reusing a pooled
    # connection. Closing the upstream connection avoids stale keep-alive
    # sockets when a mock is recreated with the same name.
    headers["Connection"] = "close"
    return headers


def response_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
        and key.lower() not in {"content-length", "content-encoding"}
    }


async def runtime_is_healthy(request: Request, mock_id: str) -> bool:
    """Distinguish a missing runtime from a slow endpoint response."""
    health_url = f"http://{runtime_container_name(mock_id)}:{RUNTIME_PORT}/_internal/health"
    try:
        response = await request.app.state.http_client.get(
            health_url,
            headers={"Connection": "close"},
            timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0),
        )
    except httpx.HTTPError:
        return False
    return response.status_code == 200


async def proxy_request(
    request: Request,
    mock_id: str,
    path: str,
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started_at = perf_counter()

    try:
        UUID(mock_id)
    except ValueError:
        logger.info(
            "Mock route rejected: request_id=%s method=%s path=%s reason=invalid_mock_id",
            request_id,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=404,
            content={"detail": "Mock server not found", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    target_path = f"/{path}" if path else "/"
    target_url = f"http://{runtime_container_name(mock_id)}:{RUNTIME_PORT}{target_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    if not await runtime_is_healthy(request, mock_id):
        elapsed_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "Mock request target unavailable before forwarding: request_id=%s mock_id=%s "
            "duration_ms=%.2f",
            request_id,
            mock_id,
            elapsed_ms,
        )
        return JSONResponse(
            status_code=404,
            content={"detail": "Mock server not found or not running", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    body = await request.body()
    logger.info(
        "Mock request forwarding: request_id=%s method=%s public_path=%s target=%s",
        request_id,
        request.method,
        request.url.path,
        target_url,
    )

    try:
        upstream_response = await request.app.state.http_client.request(
            request.method,
            target_url,
            headers=forwarded_request_headers(request, request_id),
            content=body,
        )
    except (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadError,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
        httpx.PoolTimeout,
    ) as exc:
        elapsed_ms = (perf_counter() - started_at) * 1000
        runtime_healthy = await runtime_is_healthy(request, mock_id)
        status_code = 504 if runtime_healthy else 404
        detail = "Mock server timed out" if runtime_healthy else "Mock server not found or not running"
        logger.warning(
            "Mock request upstream failure: request_id=%s mock_id=%s runtime_healthy=%s "
            "status=%s duration_ms=%.2f error_type=%s error=%s",
            request_id,
            mock_id,
            runtime_healthy,
            status_code,
            elapsed_ms,
            type(exc).__name__,
            exc,
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail, "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
    except httpx.HTTPError:
        logger.exception(
            "Mock request proxy failed: request_id=%s mock_id=%s",
            request_id,
            mock_id,
        )
        return JSONResponse(
            status_code=502,
            content={"detail": "Mock server proxy error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "Mock request completed: request_id=%s mock_id=%s status=%s duration_ms=%.2f",
        request_id,
        mock_id,
        upstream_response.status_code,
        elapsed_ms,
    )
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers={**response_headers(upstream_response), "X-Request-ID": request_id},
        media_type=None,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route(
    "/{mock_id}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def proxy_root(request: Request, mock_id: str) -> Response:
    return await proxy_request(request, mock_id, "")


@app.api_route(
    "/{mock_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def proxy_path(request: Request, mock_id: str, path: str) -> Response:
    return await proxy_request(request, mock_id, path)
