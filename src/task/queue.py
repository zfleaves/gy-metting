"""
异步任务队列 (DESIGN.md §3.6)

内存队列 + 数据库状态持久化。
- 任务提交 → 返回 task_id
- 状态机：pending → processing → completed/failed
- 支持并发控制、超时、进度回调
"""

import asyncio
import json
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

from src.config import get_config
from src.log_utils import get_logger, LogTimer
from src.storage.db import SessionLocal
from src.storage.models import Task, TaskStatus, TaskType

logger = get_logger(__name__)

# 任务处理器类型：接收 task_id 和参数，返回结果
TaskHandler = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Any]]


class TaskManager:
    """
    异步任务管理器。

    用法:
        manager = TaskManager()
        manager.register_handler(TaskType.ASR, asr_handler)
        await manager.start()
        task_id = await manager.submit(TaskType.ASR, {"audio_path": "/tmp/audio.mp3"})
    """

    def __init__(self, max_concurrent: Optional[int] = None):
        config = get_config()
        self.max_concurrent = max_concurrent or config.MAX_CONCURRENT_TASKS
        self.timeout_minutes = config.TASK_TIMEOUT_MINUTES
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._handlers: Dict[TaskType, TaskHandler] = {}
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    # ============================================================
    # 处理器注册
    # ============================================================

    def register_handler(self, task_type: TaskType, handler: TaskHandler) -> None:
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info("注册任务处理器: %s", task_type.value)

    # ============================================================
    # 任务提交
    # ============================================================

    async def submit(
        self,
        task_type: TaskType,
        params: Optional[Dict[str, Any]] = None,
        meeting_id: Optional[str] = None,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> str:
        """
        提交任务。

        Args:
            task_type: 任务类型
            params: 任务参数（JSON 可序列化）
            meeting_id: 关联的会议 ID（可选）
            user_id: 关联的用户 ID（可选）
            name: 任务名称（可选，默认取上传文件名）

        Returns:
            task_id: 任务 ID

        Raises:
            ValueError: 任务类型未注册处理器
        """
        if task_type not in self._handlers:
            raise ValueError(f"任务类型 {task_type.value} 未注册处理器")

        # 创建数据库记录
        db = SessionLocal()
        try:
            task = Task(
                type=task_type,
                status=TaskStatus.PENDING,
                params_json=json.dumps(params) if params else None,
                meeting_id=meeting_id,
                user_id=user_id,
                name=name,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id
        finally:
            db.close()

        # 入队
        await self._queue.put(task_id)
        logger.info("任务已提交: id=%s, type=%s, queue_size=%d",
                     task_id, task_type.value, self._queue.qsize())

        return task_id

    # ============================================================
    # 启动与停止
    # ============================================================

    async def start(self) -> None:
        """启动 worker 协程"""
        if self._running:
            return

        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.max_concurrent)
        ]
        logger.info("任务管理器启动: workers=%d", self.max_concurrent)

    async def stop(self) -> None:
        """停止所有 worker"""
        self._running = False
        # 等待所有 worker 结束
        for w in self._workers:
            w.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("任务管理器已停止")

    # ============================================================
    # Worker
    # ============================================================

    async def _worker(self, name: str) -> None:
        """Worker 协程：从队列取任务并执行"""
        logger.info("Worker %s 启动", name)

        while self._running:
            try:
                # 带超时的出队，以便检查 _running 状态
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            async with self._semaphore:
                try:
                    await self._process(task_id, name)
                except Exception:
                    logger.error("Worker %s 处理任务 %s 时异常", name, task_id, exc_info=True)
                finally:
                    self._queue.task_done()

        logger.info("Worker %s 退出", name)

    async def _process(self, task_id: str, worker_name: str) -> None:
        """处理单个任务"""
        # 更新状态为 processing
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error("任务不存在: %s", task_id)
                return

            task.status = TaskStatus.PROCESSING
            task.progress = 0.05
            task.started_at = datetime.now(timezone.utc)
            db.commit()

            handler = self._handlers.get(task.type)
            if not handler:
                self._fail_task(db, task, f"未注册的处理器: {task.type.value}")
                return

            params = json.loads(task.params_json) if task.params_json else {}

        finally:
            db.close()

        # 执行处理器
        with LogTimer(logger, f"任务 {task_id} ({task.type.value})"):
            try:
                result = await asyncio.wait_for(
                    handler(task_id, params),
                    timeout=self.timeout_minutes * 60,
                )
                self._complete_task(task_id, result)
            except asyncio.TimeoutError:
                self._fail_task_by_id(task_id, f"任务超时 ({self.timeout_minutes} 分钟)")
            except asyncio.CancelledError:
                self._fail_task_by_id(task_id, "任务被取消")
                raise
            except Exception as e:
                self._fail_task_by_id(task_id, str(e))
                logger.error("任务 %s 失败: %s\n%s", task_id, e, traceback.format_exc())

    # ============================================================
    # 状态更新
    # ============================================================

    def _complete_task(self, task_id: str, result: Any) -> None:
        """标记任务完成"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.completed_at = datetime.now(timezone.utc)
                if isinstance(result, str):
                    task.result_summary = result[:2000]
                elif isinstance(result, dict):
                    # 大字段（segments）不存入 DB，只存摘要
                    summary = {k: v for k, v in result.items() if k != "segments"}
                    task.result_summary = json.dumps(summary, ensure_ascii=False)[:2000]
                    if "result_path" in result:
                        task.result_path = result["result_path"]
                db.commit()
                logger.info("任务 %s 完成", task_id)
        finally:
            db.close()

    def _fail_task_by_id(self, task_id: str, error: str) -> None:
        """通过 ID 标记任务失败"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                self._fail_task(db, task, error)
        finally:
            db.close()

    def _fail_task(self, db, task: Task, error: str) -> None:
        """标记任务失败"""
        task.status = TaskStatus.FAILED
        task.error_message = error[:1000]
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("任务 %s 失败: %s", task.id, error)

    # ============================================================
    # 查询
    # ============================================================

    @staticmethod
    def get_task(task_id: str) -> Optional[Dict[str, Any]]:
        """查询任务状态"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return None
            return _task_to_dict(task)
        finally:
            db.close()

    @staticmethod
    def list_tasks(
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Dict[str, Any]]:
        """列出任务"""
        db = SessionLocal()
        try:
            q = db.query(Task)
            if status:
                q = q.filter(Task.status == status)
            if task_type:
                q = q.filter(Task.type == task_type)
            q = q.order_by(Task.created_at.desc()).offset(offset).limit(limit)
            return [_task_to_dict(t) for t in q.all()]
        finally:
            db.close()


def _task_to_dict(task: Task) -> Dict[str, Any]:
    return {
        "id": task.id,
        "name": task.name,
        "type": task.type.value if task.type else None,
        "status": task.status.value if task.status else None,
        "progress": task.progress,
        "result_summary": task.result_summary,
        "result_path": task.result_path,
        "error_message": task.error_message,
        "meeting_id": task.meeting_id,
        "user_id": task.user_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# 全局单例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def list_tasks_by_user(
    user_id: str,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    """按用户过滤任务列表"""
    db = SessionLocal()
    try:
        q = db.query(Task).filter(Task.user_id == user_id)
        if status:
            q = q.filter(Task.status == status)
        if task_type:
            q = q.filter(Task.type == task_type)
        q = q.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        return [_task_to_dict(t) for t in q.all()]
    finally:
        db.close()