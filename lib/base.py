"""注册机基类"""
from __future__ import annotations

import argparse
import itertools
import multiprocessing as mp
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

from .utils import gen_password, log, set_worker_id


@dataclass
class RegistrantMeta:
    name: str
    description: str = ""


class BaseRegistrant(ABC):
    meta: RegistrantMeta

    def add_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-n",
            "--count",
            type=int,
            default=1,
            help="注册数量 (0 表示无限注册, 直到 Ctrl-C)",
        )
        parser.add_argument("-w", "--workers", type=int, default=1, help="并行进程数")

    def run(self, args: argparse.Namespace) -> None:
        count: int = args.count
        infinite = count <= 0
        # 无限模式下 workers 不受 count 限制
        workers = args.workers if infinite else min(args.workers, max(count, 1))

        target = "无限" if infinite else str(count)
        log(f"目标 {target} 个账号, {workers} 进程并行")

        if workers <= 1:
            success = self._run_serial(count, infinite)
        else:
            success = self._run_parallel(count, infinite, workers)

        log("=" * 50)
        log(f"完成: {success}" + ("" if infinite else f"/{count}"))
        log("=" * 50)

    def _run_serial(self, count: int, infinite: bool) -> int:
        """单进程: 依次注册, 每个失败自动重试直到成功

        中断 (Ctrl-C) 时返回已成功数, 不让 KeyboardInterrupt 冒泡丢失计数。
        """
        success = 0
        idx = 0
        try:
            while infinite or idx < count:
                set_worker_id(idx)
                while True:
                    r = self.register_one(idx, password=gen_password())
                    if r:
                        success += 1
                        break
                    log(f"重试 #{idx + 1}...")
                idx += 1
        except KeyboardInterrupt:
            log("收到中断信号, 停止注册", "!")
        return success

    def _run_parallel(self, count: int, infinite: bool, workers: int) -> int:
        """多进程: 惰性下发任务, 支持无限模式

        中断 (Ctrl-C) 时终止进程池并返回已成功数。
        """
        success = 0
        with mp.Pool(workers) as pool:
            try:
                for r in pool.imap_unordered(self._mp_worker, self._task_stream(count, infinite)):
                    if r:
                        success += 1
            except KeyboardInterrupt:
                log("收到中断信号, 停止注册", "!")
                pool.terminate()
                pool.join()
        return success

    @staticmethod
    def _task_stream(count: int, infinite: bool) -> Iterator[tuple[int, str]]:
        """惰性任务生成器: (idx, password), 无限模式下不预生成列表"""
        counter = itertools.count() if infinite else range(count)
        for idx in counter:
            yield idx, gen_password()

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
