"""
语雀图片代理 API

语雀文档中的图片托管在 cdn.nlark.com，需要带 Yuque Cookie 才能访问。
本代理转发图片请求，附加 Yuque 认证凭据。
"""

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from src.config import get_config
from src.log_utils import get_logger

config = get_config()
logger = get_logger(__name__)

router = APIRouter(tags=["语雀图片代理"])


@router.get("/yuque-image-proxy")
async def yuque_image_proxy(url: str = Query(..., description="原始图片 URL")):
    """代理语雀图片，附加 Yuque Cookie 认证"""
    if not url:
        raise HTTPException(status_code=400, detail="url 参数不能为空")

    # 构建请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (gy-meeting)",
        "Referer": "https://www.yuque.com/",
    }
    cookie = ""
    if config.YUQUE_SESSION:
        cookie += f"_yuque_session={config.YUQUE_SESSION}; "
    if config.YUQUE_CTOKEN:
        cookie += f"yuque_ctoken={config.YUQUE_CTOKEN}; "
    if cookie:
        headers["Cookie"] = cookie.rstrip("; ")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            logger.warning("图片代理失败: url=%s status=%d", url, resp.status_code)
            raise HTTPException(status_code=resp.status_code, detail="图片加载失败")

        content_type = resp.headers.get("content-type", "image/png")
        return Response(content=resp.content, media_type=content_type)

    except httpx.TimeoutException:
        logger.error("图片代理超时: %s", url)
        raise HTTPException(status_code=504, detail="图片加载超时")
    except Exception as e:
        logger.error("图片代理异常: %s — %s", url, e)
        raise HTTPException(status_code=500, detail=f"图片代理失败: {e}")