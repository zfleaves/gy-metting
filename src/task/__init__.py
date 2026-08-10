"""
异步任务队列 (DESIGN.md §3.6)

内存队列 + 数据库状态表，pending → processing → completed/failed。
"""

from src.task.queue import TaskManager, get_task_manager

__all__ = ["TaskManager", "get_task_manager"]