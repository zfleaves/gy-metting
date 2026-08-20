"""
FastAPI 应用工厂 (DESIGN.md §2.1 接入层)

创建 FastAPI 实例，注册中间件、路由、生命周期事件。
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from src.config import get_config
from src.log_utils import get_logger, set_request_id, setup_logging

config = get_config()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期：启动时初始化资源，关闭时清理"""
    logger.info("gy-meeting v%s 启动中...", __import__("src").__version__)
    logger.info("环境: %s", "DEBUG" if config.DEBUG else "PRODUCTION")
    logger.info("ASR 引擎: %s", config.ASR_ENGINE)
    logger.info("LLM 提供商: %s (%s)", config.LLM_PROVIDER, config.LLM_MODEL)
    logger.info("数据库: %s", config.DATABASE_URL)

    # 初始化数据库
    from src.storage.db import init_db
    init_db()
    logger.info("数据库初始化完成")

    # 初始化默认管理员
    from src.api.auth import init_default_admin
    init_default_admin()

    # 注册 ASR 任务处理器
    from src.asr.task_handler import register_asr_handler
    register_asr_handler()

    # 启动任务管理器
    from src.task.queue import get_task_manager
    task_manager = get_task_manager()
    await task_manager.start()
    logger.info("任务管理器已启动")

    yield

    await task_manager.stop()
    logger.info("gy-meeting 关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""

    # 初始化日志
    setup_logging(
        level="DEBUG" if config.DEBUG else config.LOG_LEVEL,
    )

    app = FastAPI(
        title="gy-meeting",
        version=__import__("src").__version__,
        description="AI 智能会议纪要轻量化中台",
        lifespan=lifespan,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID 中间件
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or set_request_id()
        set_request_id(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    # JWT 认证中间件
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        from src.api.auth import PUBLIC_PATHS, decode_token
        request.state.user = None

        # 公开接口跳过认证
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # 提取 token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload:
                request.state.user = {
                    "user_id": payload["user_id"],
                    "username": payload["username"],
                    "role": payload["role"],
                }

        return await call_next(request)

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("未处理的异常: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误", "error": str(exc) if config.DEBUG else None},
        )

    # 注册路由
    from src.api.routes import router as api_router
    app.include_router(api_router, prefix="/api")

    # 健康检查
    @app.get("/health")
    async def health_check():
        """健康检查端点 (DESIGN.md §7.1)"""
        import shutil
        disk_usage = shutil.disk_usage(config.resolve_path(config.DATA_DIR))
        free_mb = disk_usage.free / (1024 * 1024)
        return {
            "status": "ok",
            "version": __import__("src").__version__,
            "db": "connected",
            "disk_free_mb": round(free_mb, 1),
        }

    # 前端静态文件目录
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"

    # 测试页面路由（必须在 SPA 中间件之前注册）
    test_html = frontend_dir / "recorder-test.html"
    if test_html.exists():
        @app.get("/recorder-test")
        async def recorder_test():
            return FileResponse(str(test_html))

    from fastapi.staticfiles import StaticFiles
    if frontend_dir.exists():
        assets_dir = frontend_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # SPA fallback 中间件：非 /api 非 /health 的 GET 404 返回 index.html
        @app.middleware("http")
        async def spa_middleware(request: Request, call_next):
            response = await call_next(request)
            path = request.url.path
            if response.status_code == 404 and request.method == "GET":
                if not path.startswith("/api/") and path != "/health":
                    index_path = frontend_dir / "index.html"
                    if index_path.exists():
                        return FileResponse(str(index_path))
            return response

    return app