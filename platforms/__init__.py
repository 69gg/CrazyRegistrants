"""平台注册机自动发现"""
from __future__ import annotations

import importlib
from pathlib import Path

from lib.base import BaseRegistrant


def discover() -> dict[str, BaseRegistrant]:
    """扫描 platforms/ 目录, 自动发现所有注册机"""
    registrants: dict[str, BaseRegistrant] = {}
    base = Path(__file__).parent
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"platforms.{d.name}")
            if hasattr(mod, "REGISTRANT"):
                r = mod.REGISTRANT
                registrants[r.meta.name] = r
        except Exception:
            pass
    return registrants