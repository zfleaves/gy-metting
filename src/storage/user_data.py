"""
用户数据管理（自学习）

- 文字更正记录：用户纠正的错词 → 正确词，下次转写自动应用
- 废话标记记录：用户标记的废话模式，下次自动折叠
"""

import json
import os
from pathlib import Path
from typing import Dict, List

from src.config import get_config

config = get_config()


def _data_dir() -> Path:
    d = config.resolve_path(config.DATA_DIR) / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(filename: str, default=None) -> dict:
    path = _data_dir() / filename
    if not path.exists():
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default if default is not None else {}


def _save_json(filename: str, data: dict) -> None:
    path = _data_dir() / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 文字更正
# ============================================================

def get_corrections() -> Dict[str, str]:
    """获取用户文字更正映射 {错词: 正确词}"""
    return _load_json("corrections.json", {})


def add_correction(wrong: str, correct: str) -> Dict[str, str]:
    """添加一条文字更正"""
    corrections = get_corrections()
    corrections[wrong] = correct
    _save_json("corrections.json", corrections)
    return corrections


def remove_correction(wrong: str) -> Dict[str, str]:
    """删除一条文字更正"""
    corrections = get_corrections()
    corrections.pop(wrong, None)
    _save_json("corrections.json", corrections)
    return corrections


# ============================================================
# 废话标记
# ============================================================

def get_fluff_patterns() -> List[str]:
    """获取用户标记的废话模式列表"""
    return _load_json("fluff.json", {"patterns": []}).get("patterns", [])


def add_fluff_pattern(text: str) -> List[str]:
    """添加一条废话模式（去重）"""
    patterns = get_fluff_patterns()
    text = text.strip()
    if text and text not in patterns:
        patterns.append(text)
        _save_json("fluff.json", {"patterns": patterns})
    return patterns


def remove_fluff_pattern(text: str) -> List[str]:
    """删除一条废话模式"""
    patterns = get_fluff_patterns()
    if text in patterns:
        patterns.remove(text)
        _save_json("fluff.json", {"patterns": patterns})
    return patterns