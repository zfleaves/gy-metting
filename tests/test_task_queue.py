"""测试异步任务队列"""

import asyncio
import pytest
from src.task.queue import TaskManager, get_task_manager
from src.storage.models import TaskType, TaskStatus


# 测试用处理器
async def _echo_handler(task_id: str, params: dict) -> dict:
    await asyncio.sleep(0.05)
    msg = params.get("msg", "") if isinstance(params, dict) else ""
    return {"echo": msg, "task_id": task_id}


async def _fail_handler(task_id: str, params: dict) -> dict:
    raise ValueError("test error")


class TestTaskManager:
    """任务队列测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.manager = TaskManager(max_concurrent=2)
        self.manager.register_handler(TaskType("asr"), _echo_handler)
        self.manager.register_handler(TaskType("yuque_pull"), _fail_handler)

    @pytest.mark.asyncio
    async def test_submit_and_complete(self):
        """提交任务并等待完成"""
        await self.manager.start()
        try:
            task_id = await self.manager.submit(
                TaskType("asr"),
                params={"msg": "hello"},
            )
            assert task_id

            # 等待任务完成（轮询）
            for _ in range(10):
                await asyncio.sleep(0.1)
                task = self.manager.get_task(task_id)
                if task["status"] in ("completed", "failed"):
                    break

            task = self.manager.get_task(task_id)
            assert task is not None, f"Task {task_id} not found"
            assert task["status"] == "completed", f"Expected completed, got {task['status']}: {task.get('error_message', '')}"
            assert task["progress"] == 1.0
            assert "hello" in (task["result_summary"] or "")
        finally:
            await self.manager.stop()

    @pytest.mark.asyncio
    async def test_submit_and_fail(self):
        """提交任务并验证失败处理"""
        await self.manager.start()
        try:
            task_id = await self.manager.submit(
                TaskType("yuque_pull"),
                params={"url": "test"},
            )
            await asyncio.sleep(0.2)

            task = self.manager.get_task(task_id)
            assert task["status"] == "failed"
            assert "test error" in task["error_message"]
        finally:
            await self.manager.stop()

    @pytest.mark.asyncio
    async def test_unregistered_handler(self):
        """未注册的处理器应报错"""
        with pytest.raises(ValueError):
            await self.manager.submit(TaskType("minutes"))

    def test_get_nonexistent_task(self):
        """查询不存在的任务返回 None"""
        assert self.manager.get_task("nonexistent") is None

    def test_list_tasks_empty(self):
        """空列表"""
        tasks = self.manager.list_tasks()
        assert isinstance(tasks, list)

    @pytest.mark.asyncio
    async def test_concurrent_tasks(self):
        """并发任务处理"""
        await self.manager.start()
        try:
            ids = []
            for i in range(3):
                tid = await self.manager.submit(TaskType("asr"), params={"msg": f"task-{i}"})
                ids.append(tid)

            for i in range(10):
                await asyncio.sleep(0.1)
                all_done = True
                for tid in ids:
                    t = self.manager.get_task(tid)
                    if t["status"] not in ("completed", "failed"):
                        all_done = False
                        break
                if all_done:
                    break

            for tid in ids:
                task = self.manager.get_task(tid)
                assert task["status"] == "completed", f"Task {tid}: {task['status']} - {task.get('error_message', '')}"
        finally:
            await self.manager.stop()