"""注册机基类"""
from __future__ import annotations

import argparse
import multiprocessing as mp
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .utils import gen_password, log, set_worker_id


@dataclass
class RegistrantMeta:
    name: str
    description: str = ""


class BaseRegistrant(ABC):
    meta: RegistrantMeta

    def add_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("-n", "--count", type=int, default=1, help="注册数量")
        parser.add_argument("-w", "--workers", type=int, default=1, help="并行进程数")

    def run(self, args: argparse.Namespace) -> None:
        count = args.count
        workers = min(args.workers, count)
        passwords = [gen_password() for _ in range(count)]

        log(f"{count} 个账号, {workers} 进程并行")

        success = 0
        if workers <= 1:
            for i in range(count):
                while True:
                    set_worker_id(i)
                    r = self.register_one(i, password=passwords[i])
                    if r:
                        success += 1
                        break
                    log(f"重试 #{i + 1}...")
        else:
            with mp.Pool(workers) as pool:
                tasks = [(i, passwords[i]) for i in range(count)]
                results = pool.map(self._mp_worker, tasks)
                success = sum(1 for r in results if r)

        log("=" * 50)
        log(f"完成: {success}/{count}")
        log("=" * 50)

    def _mp_worker(self, args: tuple[int, str]) -> str | None:
        idx, password = args
        while True:
            set_worker_id(idx)
            r = self.register_one(idx, password=password)
            if r:
                return r
            log("重试中...")

    @abstractmethod
    def register_one(self, idx: int, password: str) -> str | None:
        """单次注册, 返回 key 或 None (表示失败, 外层自动重试)"""
        ...