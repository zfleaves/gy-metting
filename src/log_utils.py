"""
结构化日志模块 (DESIGN.md §7.1)

JSON 格式日志，包含 request_id、操作类型、耗时等关键字段。
支持控制台输出（开发）和文件输出（生产）。
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# 当前请求的 request_id（协程安全）
_request_id: ContextVar[str] = ContextVar("request_id", default="")

# 当前操作名称
_operation: ContextVar[str] = ContextVar("operation", default="")


def set_request_id(rid: Optional[str] = None) -> str:
    """设置当前上下文的 request_id，返回设置的值"""
    rid = rid or uuid.uuid4().hex[:12]
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    return _request_id.get()


def set_operation(op: str) -> None:
    _operation.set(op)


def get_operation() -> str:
    return _operation.get()


class JsonFormatter(logging.Formatter):
    """将日志格式化为 JSON 行"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # 附加上下文信息
        req_id = get_request_id()
        if req_id:
            log_entry["request_id"] = req_id

        op = get_operation()
        if op:
            log_entry["operation"] = op

        # 附加自定义字段
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data

        # 异常信息
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    初始化日志系统。

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径（可选，不传则只输出到控制台）
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handler
    root_logger.handlers.clear()

    # 控制台 handler（开发可读格式）
    console_handler = logging.StreamHandler(sys.stdout)
    if level.upper() == "DEBUG":
        # 开发模式：可读格式
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    else:
        # 生产模式：JSON 格式
        console_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(console_handler)

    # 文件 handler（JSON 格式）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)

    # 降低第三方库日志噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger"""
    return logging.getLogger(name)


class LogTimer:
    """上下文管理器，自动记录操作耗时"""

    def __init__(self, logger: logging.Logger, operation: str, **extra):
        self.logger = logger
        self.operation = operation
        self.extra = extra
        self.start: float = 0

    def __enter__(self):
        self.start = time.perf_counter()
        set_operation(self.operation)
        self.logger.debug("开始 %s", self.operation)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start) * 1000
        log_method = self.logger.error if exc_type else self.logger.info
        log_method(
            "%s %s (%.1fms)",
            self.operation,
            "失败" if exc_type else "完成",
            duration_ms,
            extra={"duration_ms": round(duration_ms, 1), **self.extra},
        )
        set_operation("")
        return False  # 不吞异常