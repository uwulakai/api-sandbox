from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import initialize_database
from app.entities.mocks.router import router as mocks_router
from app.entities.users.router import router as auth_router
from app.health import router as health_router


logger = logging.getLogger("api_sandbox.api")


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger("api_sandbox").setLevel(level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "API startup started: version=%s database_driver=%s",
        settings.app_version,
        settings.database_url.split(":", maxsplit=1)[0],
    )
    try:
        await initialize_database()
    except Exception:
        logger.exception("API startup failed during database initialization")
        raise

    logger.info("API startup completed")
    try:
        yield
    finally:
        logger.info("API shutdown started")
        from app.core.database import engine

        await engine.dispose()
        logger.info("API shutdown completed")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="API Sandbox Backend",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        started_at = perf_counter()
        logger.info(
            "HTTP request started: request_id=%s method=%s path=%s client=%s",
            request_id,
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (perf_counter() - started_at) * 1000
            logger.exception(
                "HTTP request failed: request_id=%s method=%s path=%s duration_ms=%.2f client=%s",
                request_id,
                request.method,
                request.url.path,
                elapsed_ms,
                request.client.host if request.client else "unknown",
            )
            raise

        elapsed_ms = (perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "HTTP request completed: request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request.client.host if request.client else "unknown",
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled API exception: request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(mocks_router, prefix="/api/v1")
    return app


app = create_app()
