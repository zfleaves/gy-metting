"""
音频文件服务 API

提供音频文件流式播放，支持前端分段对照。
GET /api/audio/{file_id}
"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.config import get_config
from src.log_utils import get_logger

config = get_config()
logger = get_logger(__name__)

router = APIRouter(prefix="/audio", tags=["音频播放"])


@router.get("/{file_id}")
async def get_audio(file_id: str):
    """
    获取音频文件（支持流式播放）。

    根据上传时返回的 file_id 查找对应的音频文件。
    """
    upload_dir = config.resolve_path(config.UPLOAD_DIR) / "audio"

    # 查找匹配的音频文件（格式可能是 mp3/wav/m4a）
    for fmt in config.allowed_audio_formats_list:
        audio_path = upload_dir / f"{file_id}.{fmt}"
        if audio_path.exists():
            return FileResponse(
                path=str(audio_path),
                media_type=f"audio/{'mpeg' if fmt == 'mp3' else fmt}",
                headers={"Accept-Ranges": "bytes"},
            )

    raise HTTPException(status_code=404, detail=f"音频文件不存在: {file_id}")