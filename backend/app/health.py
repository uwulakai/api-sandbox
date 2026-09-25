from fastapi import APIRouter


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/liveness")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}
