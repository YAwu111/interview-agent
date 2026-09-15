from fastapi import APIRouter, Depends

from app.access.auth.dependencies import get_current_user
from app.access.auth.oauth import router as oauth_router
from app.access.auth.router import router as auth_router
from app.domains.chat.router import router as chat_router
from app.domains.knowledge.router import router as knowledge_router
from app.domains.resources.router import router as resources_router
from app.domains.settings.router import router as settings_router
from app.telemetry.api.router import router as monitoring_router

api_router = APIRouter(prefix="/api/v1")

# auth 公开；业务域与 monitoring 在聚合处统一注入鉴权（domains/telemetry 不感知 auth）
api_router.include_router(auth_router)
api_router.include_router(oauth_router)

_protected = [Depends(get_current_user)]
api_router.include_router(chat_router, dependencies=_protected)
api_router.include_router(knowledge_router, dependencies=_protected)
api_router.include_router(resources_router, dependencies=_protected)
api_router.include_router(settings_router, dependencies=_protected)
api_router.include_router(monitoring_router, dependencies=_protected)
