from fastapi import APIRouter

from backend.api.auth import router as auth_router
from backend.api.healthcheck import router as healthcheck_router
from backend.api.floatingip import router as floatingip_router
from backend.api.server import router as server_router
from backend.api.volume import router as volume_router
from backend.api.flavor import router as flavor_router
from backend.api.image import router as image_router

api_router = APIRouter(prefix='/api')

api_router.include_router(healthcheck_router)
api_router.include_router(auth_router)
api_router.include_router(floatingip_router)
api_router.include_router(server_router)
api_router.include_router(volume_router)
api_router.include_router(flavor_router)
api_router.include_router(image_router)
