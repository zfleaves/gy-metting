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
# 任务模型
# ============================================================

class Task(Base):
    """异步任务 — 核心状态机 (DESIGN.md §3.6)"""

    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, default=_new_id)
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

    meeting = relationship("Meeting", back_populates="tasks")


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