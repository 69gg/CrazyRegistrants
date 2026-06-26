from __future__ import annotations

from unittest import TestCase

from lib.base import BaseRegistrant, RegistrantMeta


class _FakeRegistrant(BaseRegistrant):
    """成功 success_before 次后, 下一次 register_one 抛 KeyboardInterrupt"""

    meta = RegistrantMeta(name="fake", description="test")

    def __init__(self, success_before: int) -> None:
        self.success_before = success_before
        self.calls = 0

    def register_one(self, idx: int, password: str) -> str | None:
        if self.calls >= self.success_before:
            raise KeyboardInterrupt
        self.calls += 1
        return f"key-{self.calls}"


class _AllFailThenInterrupt(BaseRegistrant):
    """全部失败 (返回 None), 第 fail_limit 次失败后中断"""

    meta = RegistrantMeta(name="fail", description="test")

    def __init__(self, fail_limit: int) -> None:
        self.fail_limit = fail_limit
        self.calls = 0

    def register_one(self, idx: int, password: str) -> str | None:
        self.calls += 1
        if self.calls >= self.fail_limit:
            raise KeyboardInterrupt
        return None


class SerialCountTest(TestCase):
    def test_interrupt_returns_accumulated_success(self) -> None:
        # 无限模式下成功 3 个后中断, 应返回 3 而非 0
        reg = _FakeRegistrant(success_before=3)
        result = reg._run_serial(count=0, infinite=True)
        self.assertEqual(result, 3)

    def test_interrupt_with_zero_success(self) -> None:
        # 一上来就中断, 返回 0
        reg = _FakeRegistrant(success_before=0)
        self.assertEqual(reg._run_serial(count=0, infinite=True), 0)

    def test_finite_count_completes_without_interrupt(self) -> None:
        # 有限模式正常跑满, 不触发中断
        reg = _FakeRegistrant(success_before=100)
        self.assertEqual(reg._run_serial(count=5, infinite=False), 5)

    def test_failures_do_not_count_but_retry(self) -> None:
        # 失败不计数, 中断时成功数为 0 (验证重试循环里中断也能正确返回)
        reg = _AllFailThenInterrupt(fail_limit=4)
        self.assertEqual(reg._run_serial(count=0, infinite=True), 0)
        self.assertEqual(reg.calls, 4)
