"""Agnes AI platform.agnes-ai.com 自动注册 + API Key 获取

纯协议流水线 (无浏览器, 无人机验证):
    创建临时邮箱 → 发送验证码 → 邮箱取码 → 注册 (拿 access_token)
    → 创建 API Key → 保存 key + 账号
"""
from __future__ import annotations

import re
import traceback
from typing import Any

from lib.base import BaseRegistrant, RegistrantMeta
from lib.config import get_email_config, get_platform_config
from lib.email_client import create_email, poll_code
from lib.http_client import JsonApiClient
from lib.utils import log, save_account, save_key, set_worker_id

DEFAULT_API_BASE = "https://platform-backend.agnes-ai.com"
WEB_ORIGIN = "https://platform.agnes-ai.com"


def _agnes_code_extractor(raw: str) -> str | None:
    """提取 Agnes 验证码

    邮件正文: "...confirm your email address: 458847"
    先按关键词锁定, 再退化为首个独立 6 位数字; 避免误抓版权年份 (©2026) 等。
    """
    text = re.sub(r"<[^>]+>", " ", raw)
    m = re.search(r"verification code to confirm your email address[:\s]*?(\d{6})", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(?:verification code|验证码)[^\d]{0,20}(\d{6})", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    return m.group(1) if m else None


class AgnesAiRegistrant(BaseRegistrant):
    meta = RegistrantMeta(
        name="agnes-ai",
        description="Agnes AI platform.agnes-ai.com 自动注册获取 API Key (纯协议)",
    )

    def register_one(self, idx: int, password: str) -> str | None:
        set_worker_id(idx)

        email_cfg = get_email_config()
        platform_cfg = get_platform_config("agnes_ai")
        api_base = platform_cfg.get("api_base", DEFAULT_API_BASE)
        key_name = platform_cfg.get("key_name", "default")
        key_profile = platform_cfg.get("key_profile", "default")

        log("=" * 40)
        log("开始注册")
        log("=" * 40)

        try:
            email = create_email(email_cfg)
            client = JsonApiClient(api_base, origin=WEB_ORIGIN)

            # 1. 发送注册验证码 (无需鉴权)
            client.get(
                "/api/verification",
                params={"email": email.address, "purpose": "register"},
            )
            log("验证码已发送")

            # 2. 邮箱取码
            code = poll_code(
                email.jwt,
                email_cfg,
                keyword="agnes",
                extractor=_agnes_code_extractor,
                timeout=120,
            )
            if not code:
                log("未收到验证码", "!")
                return None

            # 3. 注册 (响应直接返回 access_token, 无需再登录)
            data = client.post(
                "/api/user/register",
                json={
                    "email": email.address,
                    "password": password,
                    "password_confirm": password,
                    "code": code,
                },
            )
            token = str((data or {}).get("access_token") or "")
            if not token:
                log("注册响应未含 access_token", "!")
                return None
            client.set_token(token)
            log(f"注册成功: {email.address}")

            # 4. 创建 API Key
            key_data = client.post(
                "/api/token",
                json={"name": key_name, "api_key_profile": key_profile},
            )
            api_key = str((key_data or {}).get("key") or "")
            if not api_key:
                log("创建密钥响应未含 key", "!")
                return None

            # 5. 保存 key + 完整账号
            save_key("agnes_ai", api_key)
            account: dict[str, Any] = {
                "email": email.address,
                "password": password,
                "access_token": token,
                "key": api_key,
            }
            save_account("agnes_ai", account)
            log(f"完成! key={api_key}")
            return api_key

        except Exception as exc:
            log(f"失败: {exc}", "!")
            traceback.print_exc()
            return None
