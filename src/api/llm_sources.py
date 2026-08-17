"""
LLM 来源管理 API

管理多个 LLM 配置（provider、API Key、model 等），支持切换激活。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import LlmSource

logger = get_logger(__name__)

router = APIRouter(prefix="/llm-sources", tags=["LLM 来源"])


class LlmSourceCreate(BaseModel):
    name: str
    provider: str = "openai"
    base_url: str = ""
    api_key: str
    model: str
    temperature: Optional[str] = "0.3"
    max_tokens: Optional[str] = "4096"


class LlmSourceUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[str] = None


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _source_to_dict(s: LlmSource) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "provider": s.provider,
        "base_url": s.base_url,
        "api_key": s.api_key[:8] + "***" if s.api_key else "",
        "model": s.model,
        "temperature": s.temperature or "0.3",
        "max_tokens": s.max_tokens or "4096",
        "is_active": s.is_active == "1",
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def list_sources(request: Request):
    """列出当前用户的 LLM 来源"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        sources = (
            db.query(LlmSource)
            .filter(LlmSource.user_id == user["user_id"])
            .order_by(LlmSource.created_at.desc())
            .all()
        )
        return [_source_to_dict(s) for s in sources]
    finally:
        db.close()


@router.post("")
async def create_source(request: Request, body: LlmSourceCreate):
    """添加 LLM 来源"""
    user = _get_user(request)
    if not body.name.strip() or not body.api_key.strip() or not body.model.strip():
        raise HTTPException(status_code=400, detail="名称、API Key 和模型不能为空")

    db = SessionLocal()
    try:
        source = LlmSource(
            user_id=user["user_id"],
            name=body.name.strip(),
            provider=body.provider.strip() or "openai",
            base_url=body.base_url.strip(),
            api_key=body.api_key.strip(),
            model=body.model.strip(),
            temperature=body.temperature or "0.3",
            max_tokens=body.max_tokens or "4096",
        )
        # 第一个添加的自动设为激活
        existing = db.query(LlmSource).filter(LlmSource.user_id == user["user_id"]).count()
        if existing == 0:
            source.is_active = "1"

        db.add(source)
        db.commit()
        db.refresh(source)
        logger.info("LLM 来源已添加: %s (%s)", source.name, source.provider)
        return _source_to_dict(source)
    finally:
        db.close()


@router.put("/{source_id}")
async def update_source(request: Request, source_id: str, body: LlmSourceUpdate):
    """更新 LLM 来源"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        source = (
            db.query(LlmSource)
            .filter(LlmSource.id == source_id, LlmSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")

        if body.name is not None:
            source.name = body.name.strip()
        if body.provider is not None:
            source.provider = body.provider.strip()
        if body.base_url is not None:
            source.base_url = body.base_url.strip()
        if body.api_key is not None:
            source.api_key = body.api_key.strip()
        if body.model is not None:
            source.model = body.model.strip()
        if body.temperature is not None:
            source.temperature = body.temperature
        if body.max_tokens is not None:
            source.max_tokens = body.max_tokens

        db.commit()
        return {"updated": True, "id": source_id}
    finally:
        db.close()


@router.delete("/{source_id}")
async def delete_source(request: Request, source_id: str):
    """删除 LLM 来源"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        source = (
            db.query(LlmSource)
            .filter(LlmSource.id == source_id, LlmSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")

        was_active = source.is_active == "1"
        db.delete(source)
        db.commit()

        # 如果删除的是激活的，自动激活另一个
        if was_active:
            remaining = (
                db.query(LlmSource)
                .filter(LlmSource.user_id == user["user_id"])
                .order_by(LlmSource.created_at.desc())
                .first()
            )
            if remaining:
                remaining.is_active = "1"
                db.commit()

        logger.info("LLM 来源已删除: %s", source.name)
        return {"deleted": True, "id": source_id}
    finally:
        db.close()


@router.post("/{source_id}/activate")
async def activate_source(request: Request, source_id: str):
    """激活指定 LLM 来源（取消其他来源的激活状态）"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        source = (
            db.query(LlmSource)
            .filter(LlmSource.id == source_id, LlmSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")

        # 取消所有激活
        db.query(LlmSource).filter(LlmSource.user_id == user["user_id"]).update(
            {LlmSource.is_active: "0"}
        )
        # 激活目标
        source.is_active = "1"
        db.commit()
        logger.info("LLM 来源已激活: %s", source.name)
        return {"activated": True, "id": source_id, "name": source.name}
    finally:
        db.close()