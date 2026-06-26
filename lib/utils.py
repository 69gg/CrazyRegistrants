"""通用工具函数"""
from __future__ import annotations

import contextvars
import fcntl
import json
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Any

_worker_id: contextvars.ContextVar[int] = contextvars.ContextVar("worker_id", default=0)


def set_worker_id(wid: int) -> None:
    _worker_id.set(wid)


def log(msg: str, level: str = "*") -> None:
    wid = f"[W{_worker_id.get()}] " if _worker_id.get() else ""
    print(f"[{datetime.now():%H:%M:%S}] [{level}] {wid}{msg}", flush=True)


def gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    chars = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*"),
    ]
    chars += [random.choice(alphabet) for _ in range(length - 4)]
    random.shuffle(chars)
    return "".join(chars)


def rand_name(prefix: str = "nv", n: int = 6) -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


# 各平台产物统一输出到 output/<platform>/ 下
OUTPUT_ROOT = Path("output")


def _append_locked(platform: str, filename: str, line: str) -> None:
    """跨进程/线程安全地向 output/<platform>/<filename> 追加一行 (flock 互斥)"""
    output_dir = OUTPUT_ROOT / platform
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_file = output_dir / ".lock"
    target = output_dir / filename
    with open(lock_file, "a") as lf:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            with open(target, "a") as f:
                f.write(f"{line}\n")
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def save_key(platform: str, key: str) -> None:
    """线程安全的 key 保存到 output/<platform>/keys.txt (一行一个 key)"""
    _append_locked(platform, "keys.txt", key)


def save_account(platform: str, account: dict[str, Any]) -> None:
    """线程安全的完整账号保存到 output/<platform>/accounts.jsonl (一行一个账号)

    account 通常含 email/password/access_token/key 等字段, 便于二次登录复用。
    """
    record = {"created_at": f"{datetime.now():%Y-%m-%dT%H:%M:%S}", **account}
    _append_locked(platform, "accounts.jsonl", json.dumps(record, ensure_ascii=False))