from fastapi import APIRouter

from app.core.config import settings
from app.core.events import bus

router = APIRouter(tags=["sistema"])


@router.get("/health", summary="Verificação de saúde")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "sse_subscribers": bus.subscriber_count,
    }
