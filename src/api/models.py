"""
RAG 模型管理 API (Embedding / Reranker)

支持 CRUD + 激活切换 + 连接测试。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import RagModel

logger = get_logger(__name__)

router = APIRouter(prefix="/models", tags=["RAG 模型"])


class RagModelCreate(BaseModel):
    name: str
    model_type: str  # "embedding" or "reranker"
    provider: str = "dashscope"
    base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    api_key: str
    model: str


class RagModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _to_dict(m: RagModel) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "model_type": m.model_type,
        "provider": m.provider,
        "base_url": m.base_url,
        "api_key": m.api_key[:8] + "***" if m.api_key else "",
        "model": m.model,
        "is_active": m.is_active == "1",
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("")
async def list_models(
    request: Request,
    model_type: Optional[str] = None,
):
    """列出 RAG 模型配置"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        q = db.query(RagModel).filter(RagModel.user_id == user["user_id"])
        if model_type:
            q = q.filter(RagModel.model_type == model_type)
        models = q.order_by(RagModel.created_at.desc()).all()
        return [_to_dict(m) for m in models]
    finally:
        db.close()


@router.post("")
async def create_model(request: Request, body: RagModelCreate):
    """添加 RAG 模型"""
    user = _get_user(request)
    if not body.name.strip() or not body.api_key.strip() or not body.model.strip():
        raise HTTPException(status_code=400, detail="名称、API Key 和模型不能为空")
    if body.model_type not in ("embedding", "reranker"):
        raise HTTPException(status_code=400, detail="模型类型必须是 embedding 或 reranker")

    db = SessionLocal()
    try:
        m = RagModel(
            user_id=user["user_id"],
            name=body.name.strip(),
            model_type=body.model_type,
            provider=body.provider.strip() or "dashscope",
            base_url=body.base_url.strip() or "https://dashscope.aliyuncs.com/api/v1",
            api_key=body.api_key.strip(),
            model=body.model.strip(),
        )
        # 第一个自动激活
        existing = (
            db.query(RagModel)
            .filter(RagModel.user_id == user["user_id"], RagModel.model_type == body.model_type)
            .count()
        )
        if existing == 0:
            m.is_active = "1"

        db.add(m)
        db.commit()
        db.refresh(m)
        logger.info("RAG 模型已添加: %s (%s - %s)", m.name, m.model_type, m.model)
        return _to_dict(m)
    finally:
        db.close()


@router.put("/{model_id}")
async def update_model(request: Request, model_id: str, body: RagModelUpdate):
    """更新 RAG 模型"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(RagModel).filter(RagModel.id == model_id, RagModel.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="模型不存在")

        if body.name is not None:
            m.name = body.name.strip()
        if body.provider is not None:
            m.provider = body.provider.strip()
        if body.base_url is not None:
            m.base_url = body.base_url.strip()
        if body.api_key is not None:
            m.api_key = body.api_key.strip()
        if body.model is not None:
            m.model = body.model.strip()

        db.commit()
        return {"updated": True, "id": model_id}
    finally:
        db.close()


@router.delete("/{model_id}")
async def delete_model(request: Request, model_id: str):
    """删除 RAG 模型"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(RagModel).filter(RagModel.id == model_id, RagModel.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="模型不存在")
        db.delete(m)
        db.commit()
        logger.info("RAG 模型已删除: %s", m.name)
        return {"deleted": True, "id": model_id}
    finally:
        db.close()


@router.post("/{model_id}/activate")
async def activate_model(request: Request, model_id: str):
    """激活指定 RAG 模型"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(RagModel).filter(RagModel.id == model_id, RagModel.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 取消同类型所有激活
        db.query(RagModel).filter(
            RagModel.user_id == user["user_id"],
            RagModel.model_type == m.model_type,
        ).update({RagModel.is_active: "0"})
        m.is_active = "1"
        db.commit()
        logger.info("RAG 模型已激活: %s (%s)", m.name, m.model_type)
        return {"activated": True, "id": model_id, "name": m.name}
    finally:
        db.close()


@router.post("/{model_id}/test")
async def test_model(request: Request, model_id: str):
    """测试 RAG 模型连接"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(RagModel).filter(RagModel.id == model_id, RagModel.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="模型不存在")

        error_detail = None
        if m.model_type == "embedding":
            from src.llm.embedding import DashScopeEmbedding
            adapter = DashScopeEmbedding(api_key=m.api_key, model=m.model, base_url=m.base_url, provider=m.provider)
            ok, error_detail = await adapter.test_connection()
        elif m.model_type == "reranker":
            from src.llm.reranker import DashScopeReranker
            adapter = DashScopeReranker(api_key=m.api_key, model=m.model, base_url=m.base_url, provider=m.provider)
            ok, error_detail = await adapter.test_connection()
        else:
            raise HTTPException(status_code=400, detail="不支持的模型类型")

        return {
            "success": ok,
            "message": "连接成功" if ok else f"连接失败: {error_detail}",
        }
    finally:
        db.close()