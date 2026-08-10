"""
AI 智能会议纪要轻量化中台 — 入口文件

用法:
    python main.py              # 启动 HTTP API 服务（开发模式）
    uvicorn src.app:create_app --factory --reload  # 等价命令

基于 DESIGN.md V1.1
"""

import sys
from pathlib import Path

# 确保 src 在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    """启动 FastAPI 服务"""
    import uvicorn
    from src.config import get_config

    config = get_config()
    uvicorn.run(
        "src.app:create_app",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()