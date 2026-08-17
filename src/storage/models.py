"""
数据库模型 (DESIGN.md §3.6 + §7.1)

任务表、会议表、快照表、输出表。
大字段（文本内容）采用文件存储，数据库只存路径。
"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.storage.db import Base


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# 枚举类型
# ============================================================

class TaskStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, PyEnum):
    ASR = "asr"                # 语音转写
    MINUTES = "minutes"        # 纪要生成
    YUQUE_PULL = "yuque_pull"  # 语雀拉取


# ============================================================
# 用户模型
# ============================================================

class UserRole(str, PyEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class User(Base):
    """用户"""

    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=_new_id)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    tasks = relationship("Task", back_populates="user")


# ============================================================
# 任务模型
# ============================================================

class Task(Base):
    """异步任务 — 核心状态机 (DESIGN.md §3.6)"""

    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, default=_new_id)
    name = Column(String(200), nullable=True)  # 任务名称（默认取上传文件名）
    type = Column(Enum(TaskType), nullable=False, index=True)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)

    # 输入参数（JSON 字符串）
    params_json = Column(Text, nullable=True)

    # 进度（0.0 ~ 1.0）
    progress = Column(Float, default=0.0)

    # 结果摘要
    result_summary = Column(Text, nullable=True)
    # 详细结果文件路径（大内容存文件）
    result_path = Column(String(500), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 关联会议（可选，纪要任务关联）
    meeting_id = Column(String(32), ForeignKey("meetings.id"), nullable=True, index=True)

    # 关联用户
    user_id = Column(String(32), ForeignKey("users.id"), nullable=True, index=True)

    meeting = relationship("Meeting", back_populates="tasks")
    user = relationship("User", back_populates="tasks")


# ============================================================
# 会议模型
# ============================================================

class Meeting(Base):
    """会议记录 (DESIGN.md §3.5)"""

    __tablename__ = "meetings"

    id = Column(String(32), primary_key=True, default=_new_id)
    title = Column(String(200), nullable=False, index=True)
    meeting_type = Column(String(50), nullable=False, default="需求评审")  # 需求评审/技术评审/周会

    # 业务背景（用户输入）
    background = Column(Text, nullable=True)
    # 自定义提示词
    custom_prompt = Column(Text, nullable=True)

    # 音频文件路径
    audio_path = Column(String(500), nullable=True)
    # ASR 转写文本文件路径（大字段存文件）
    transcript_path = Column(String(500), nullable=True)
    # 转写文本预览（前 500 字，用于列表展示）
    transcript_preview = Column(Text, nullable=True)

    # 参考文档快照 ID 列表（JSON 数组字符串）
    snapshot_ids_json = Column(Text, nullable=True)

    # AI 输出：Markdown 纪要路径
    minutes_md_path = Column(String(500), nullable=True)
    # AI 输出：JSON 结构化数据路径
    minutes_json_path = Column(String(500), nullable=True)

    # 钉钉推送状态
    dingtalk_sent = Column(String(20), default="pending")  # pending/sent/failed/not_configured

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    tasks = relationship("Task", back_populates="meeting")


# ============================================================
# 快照模型
# ============================================================

class Snapshot(Base):
    """参考文档快照 (DESIGN.md §3.2.1)"""

    __tablename__ = "snapshots"

    id = Column(String(32), primary_key=True, default=_new_id)
    source_type = Column(String(20), nullable=False, index=True)  # yuque | local
    source_url = Column(String(500), nullable=True)  # 语雀 URL 或本地文件名
    title = Column(String(200), nullable=False)

    # 快照内容文件路径
    content_path = Column(String(500), nullable=False)
    # 原始数据文件路径（语雀 JSON 原始响应）
    raw_path = Column(String(500), nullable=True)

    # 文件大小（字节）
    size_bytes = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


# ============================================================
# 语雀来源模型
# ============================================================

class YuqueSource(Base):
    """语雀来源配置 — 用户级，不同 token 对应不同知识库"""

    __tablename__ = "yuque_sources"

    id = Column(String(32), primary_key=True, default=_new_id)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # 来源名称，如"冲鸭"
    yuque_url = Column(String(500), nullable=False)  # 知识库 URL
    token = Column(String(200), nullable=False)  # 语雀 API Token
    session = Column(String(200), nullable=True)  # _yuque_session Cookie
    ctoken = Column(String(200), nullable=True)   # yuque_ctoken Cookie
    exclude = Column(Text, nullable=True)  # 排除关键词 JSON 数组
    attachment_types = Column(Text, nullable=True)  # 附件类型 JSON 数组
    embed_types = Column(Text, nullable=True)  # 嵌入类型 JSON 数组
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ============================================================
# 语雀拉取记录模型
# ============================================================

class YuquePullRecord(Base):
    """语雀拉取记录 — 每次拉取需求的操作记录"""

    __tablename__ = "yuque_pull_records"

    id = Column(String(32), primary_key=True, default=_new_id)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    source_id = Column(String(32), ForeignKey("yuque_sources.id"), nullable=False)
    source_name = Column(String(100), nullable=False)  # 来源名称（冗余，方便列表展示）
    requirement_id = Column(String(100), nullable=False, index=True)  # 需求号
    matched_title = Column(String(200), nullable=True)  # 匹配的 TITLE 节点名
    total = Column(Integer, default=0)  # 总文档数
    success = Column(Integer, default=0)  # 成功数
    failed = Column(Integer, default=0)  # 失败数
    results_json = Column(Text, nullable=True)  # 结果 JSON 字符串
    status = Column(String(20), default="success")  # success / partial / failed
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)