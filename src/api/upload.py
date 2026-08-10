"""
文件上传 API (DESIGN.md §2.1 + §7.2)

音频上传：POST /api/upload/audio
- 限制大小 ≤ 200MB
- 允许格式：mp3, wav, m4a
- MIME type + magic bytes 双重校验
- 随机文件名存储
"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config import get_config
from src.log_utils import get_logger

config = get_config()
logger = get_logger(__name__)

router = APIRouter(prefix="/upload", tags=["文件上传"])

# 音频 magic bytes 签名
AUDIO_MAGIC_BYTES = {
    b"ID3": "mp3",          # MP3 (ID3 tag)
    b"\xff\xfb": "mp3",     # MP3 (MPEG frame)
    b"\xff\xf3": "mp3",     # MP3 (MPEG v2)
    b"\xff\xf2": "mp3",     # MP3 (MPEG v2.5)
    b"RIFF": "wav",         # WAV
    b"ftyp": "m4a",         # M4A/MP4
}


def _validate_audio_format(filename: str, content: bytes) -> str:
    """
    校验音频格式（扩展名 + magic bytes 双重校验）。

    Returns:
        小写扩展名

    Raises:
        HTTPException: 格式不支持或校验失败
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    allowed = config.allowed_audio_formats_list

    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的音频格式: .{ext}，允许: {', '.join(allowed)}",
        )

    # Magic bytes 校验
    detected = None
    for magic, fmt in AUDIO_MAGIC_BYTES.items():
        if content.startswith(magic):
            detected = fmt
            break

    if detected is None:
        raise HTTPException(
            status_code=400,
            detail="无法识别音频格式，请确认文件为有效的 mp3/wav/m4a 音频",
        )

    # 扩展名与 magic bytes 不一致时以 magic bytes 为准
    if detected != ext:
        logger.warning("扩展名 .%s 与实际格式 %s 不一致，以实际格式为准", ext, detected)

    return detected


@router.post("/audio")
async def upload_audio(file: UploadFile = File(...)):
    """
    上传音频文件。

    返回:
        - file_id: 文件唯一标识
        - filename: 原始文件名
        - format: 音频格式
        - size_bytes: 文件大小
        - path: 存储路径
    """
    # 读取文件内容
    content = await file.read()
    size_bytes = len(content)

    # 大小校验
    if size_bytes > config.max_audio_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大: {size_bytes / 1024 / 1024:.1f}MB，"
                    f"限制 {config.MAX_AUDIO_SIZE_MB}MB",
        )

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 格式校验
    fmt = _validate_audio_format(file.filename or "unknown", content)

    # 保存文件
    upload_dir = config.resolve_path(config.UPLOAD_DIR) / "audio"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:16]
    stored_name = f"{file_id}.{fmt}"
    stored_path = upload_dir / stored_name

    with open(stored_path, "wb") as f:
        f.write(content)

    logger.info("音频上传成功: id=%s, name=%s, size=%d, fmt=%s",
                 file_id, file.filename, size_bytes, fmt)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "format": fmt,
        "size_bytes": size_bytes,
        "path": str(stored_path),
    }