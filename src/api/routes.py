"""
API 路由注册 (DESIGN.md §2.1)

按模块组织路由，统一注册到 /api 前缀下。
"""

from fastapi import APIRouter

from src.api.audio import router as audio_router
from src.api.auth import router as auth_router, user_router
from src.api.tasks import router as task_router
from src.api.upload import router as upload_router

router = APIRouter()

router.include_router(upload_router)
router.include_router(task_router)
router.include_router(audio_router)
router.include_router(auth_router)
router.include_router(user_router)