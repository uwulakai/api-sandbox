from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import initialize_database
from app.entities.mocks.router import router as mocks_router
from app.entities.users.router import router as auth_router
from app.health import router as health_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield


def create_app() -> FastAPI:
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
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(mocks_router, prefix="/api/v1")
    return app


app = create_app()
