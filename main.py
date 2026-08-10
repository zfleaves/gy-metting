""""
AI 智能会议纪要轻量化中台 — 入口文件

用法:
    python main.py              # 启动 HTTP API 服务
    python cli.py submit ...    # CLI 模式（待实现）

基于 DESIGN.md V1.1
"""

import sys
from pathlib import Path

# 确保 src 在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    """启动 FastAPI 服务（占位，M1 实现）"""
    print("gy-meeting v0.1.0 — AI 智能会议纪要轻量化中台")
    print("DESIGN.md V1.1 已就绪，项目骨架已搭建。")
    print("下一步：M1 基础能力搭建 → python main.py 启动服务")


if __name__ == "__main__":
    main()