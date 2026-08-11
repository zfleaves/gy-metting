"""
认证与用户管理 API

- POST /api/auth/login  — 登录
- GET  /api/auth/me     — 当前用户
- GET  /api/users       — 用户列表（admin+）
- POST /api/users       — 创建用户（admin+）
- DELETE /api/users/{id}— 删除用户（super_admin）
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import get_config
from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import User, UserRole

logger = get_logger(__name__)
config = get_config()

router = APIRouter(prefix="/auth", tags=["认证"])
user_router = APIRouter(prefix="/users", tags=["用户管理"])
security = HTTPBearer(auto_error=False)

# JWT 配置
JWT_SECRET = config.SECRET_KEY
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# 公开接口（无需认证）
PUBLIC_PATHS = {"/health", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}


# ============================================================
# 工具函数
# ============================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    """从请求中提取当前用户信息"""
    return getattr(request.state, "user", None)


def require_admin(request: Request):
    """要求 admin 以上权限"""
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_super_admin(request: Request):
    """要求 super_admin 权限"""
    user = get_current_user(request)
    if not user or user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return user


# ============================================================
# 认证端点
# ============================================================

@router.post("/login")
async def login(body: dict):
    """登录"""
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_token(user.id, user.username, user.role.value)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role.value,
            },
        }
    finally:
        db.close()


@router.get("/me")
async def me(request: Request):
    """当前用户信息"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


# ============================================================
# 用户管理端点
# ============================================================

@user_router.get("")
async def list_users(request: Request):
    """用户列表（admin+）"""
    require_admin(request)
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role.value,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    finally:
        db.close()


@user_router.post("")
async def create_user(body: dict, request: Request):
    """创建用户（admin+）"""
    require_admin(request)
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    role = body.get("role", "user")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 个字符")
    if role not in ("super_admin", "admin", "user"):
        raise HTTPException(status_code=400, detail="无效的角色")

    # 只有 super_admin 能创建 super_admin
    current = get_current_user(request)
    if role == "super_admin" and current["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="只有超级管理员能创建超级管理员")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="用户名已存在")

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole(role),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info("用户创建: %s (role=%s)", username, role)
        return {"id": user.id, "username": user.username, "role": user.role.value}
    finally:
        db.close()


@user_router.delete("/{user_id}")
async def delete_user(user_id: str, request: Request):
    """删除用户（super_admin）"""
    require_super_admin(request)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == UserRole.SUPER_ADMIN:
            # 检查是否还有其他 super_admin
            count = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).count()
            if count <= 1:
                raise HTTPException(status_code=400, detail="不能删除最后一个超级管理员")

        username = user.username
        db.delete(user)
        db.commit()
        logger.info("用户删除: %s", username)
        return {"deleted": True, "username": username}
    finally:
        db.close()


# ============================================================
# 初始化默认管理员
# ============================================================

def init_default_admin():
    """首次启动创建默认超级管理员"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if not existing:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role=UserRole.SUPER_ADMIN,
            )
            db.add(admin)
            db.commit()
            logger.info("默认超级管理员已创建: admin / admin123")
    finally:
        db.close()