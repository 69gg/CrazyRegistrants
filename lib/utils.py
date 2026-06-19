"""通用工具函数"""
from __future__ import annotations

import contextvars
import fcntl
import random
import string
from datetime import datetime
from pathlib import Path

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


def save_key(output_dir: Path, platform: str, key: str) -> None:
    """线程安全的 key 保存"""
    lock_file = output_dir / ".lock"
    key_file = output_dir / f"{platform}.txt"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "a") as lf:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            with open(key_file, "a") as f:
                f.write(f"{key}\n")
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)