"""
API 路由注册 (DESIGN.md §2.1)

按模块组织路由，统一注册到 /api 前缀下。
"""

from fastapi import APIRouter

from src.api.audio import router as audio_router
from src.api.auth import router as auth_router, user_router
from src.api.documents import router as documents_router
from src.api.meetings import router as meetings_router
from src.api.tasks import router as task_router
from src.api.upload import router as upload_router
from src.api.yuque_source import router as yuque_source_router
from src.api.yuque_records import router as yuque_records_router
from src.api.yuque_image_proxy import router as yuque_image_proxy_router
from src.api.llm_sources import router as llm_sources_router
from src.api.minutes import router as minutes_router
from src.api.preferences import router as preferences_router

router = APIRouter()

router.include_router(upload_router)
router.include_router(task_router)
router.include_router(audio_router)
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(documents_router)
router.include_router(meetings_router)
router.include_router(yuque_source_router)
router.include_router(yuque_records_router)
router.include_router(yuque_image_proxy_router)
router.include_router(llm_sources_router)
router.include_router(minutes_router)
router.include_router(preferences_router)