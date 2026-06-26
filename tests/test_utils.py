from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from lib import utils


class SaveOutputLayoutTest(TestCase):
    """验证产物写入 output/<platform>/ 布局"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        patcher = mock.patch.object(utils, "OUTPUT_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_save_key_writes_platform_keys_file(self) -> None:
        utils.save_key("agnes_ai", "sk-aaa")
        utils.save_key("agnes_ai", "sk-bbb")

        key_file = self.root / "agnes_ai" / "keys.txt"
        self.assertTrue(key_file.exists())
        self.assertEqual(key_file.read_text().splitlines(), ["sk-aaa", "sk-bbb"])

    def test_save_account_writes_jsonl_with_created_at(self) -> None:
        utils.save_account("agnes_ai", {"email": "a@b.com", "key": "sk-x"})

        acc_file = self.root / "agnes_ai" / "accounts.jsonl"
        self.assertTrue(acc_file.exists())
        lines = acc_file.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["email"], "a@b.com")
        self.assertEqual(record["key"], "sk-x")
        self.assertIn("created_at", record)

    def test_platforms_are_isolated_in_subdirs(self) -> None:
        utils.save_key("agnes_ai", "sk-agnes")
        utils.save_key("nvidia_nim", "nvapi-xxx")

        self.assertEqual((self.root / "agnes_ai" / "keys.txt").read_text().strip(), "sk-agnes")
        self.assertEqual((self.root / "nvidia_nim" / "keys.txt").read_text().strip(), "nvapi-xxx")

    def test_directory_created_on_demand(self) -> None:
        # 平台目录不预先存在, 应自动创建
        self.assertFalse((self.root / "agnes_ai").exists())
        utils.save_key("agnes_ai", "sk-aaa")
        self.assertTrue((self.root / "agnes_ai").is_dir())
