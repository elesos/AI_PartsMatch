from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.responses import ApiResponse, success
from app.services.cache import CacheService, get_cache

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=ApiResponse[dict[str, str]], summary="Liveness probe")
async def health() -> dict:
    return success({"status": "healthy"})


@router.get("/api/v1/health", response_model=ApiResponse[dict[str, str]], summary="Service version")
async def version_health() -> dict:
    settings = get_settings()
    return success({"status": "healthy", "service": settings.app_name, "version": settings.version})


@router.get("/api/v1/health/dependencies", response_model=ApiResponse[dict[str, str]], summary="Dependency readiness probe")
async def dependency_health(cache: CacheService = Depends(get_cache)) -> dict:
    redis_status = "connected" if await cache.ping() else "unavailable"
    return success({"redis": redis_status})
