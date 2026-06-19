"""Cloudflare Temp Email 临时邮箱客户端"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from curl_cffi import requests as cffi_requests

from .utils import log, rand_name


@dataclass
class TempEmail:
    address: str
    jwt: str
    address_id: int


def create_email(config: dict[str, Any]) -> TempEmail:
    """创建临时邮箱地址

    Args:
        config: 邮箱配置, 需包含 base_url, admin_auth, custom_auth, domain
    """
    base_url = config.get("base_url", "")
    admin_auth = config.get("admin_auth", "")
    custom_auth = config.get("custom_auth", "")
    domain = config.get("domain", "")

    headers = {
        "Content-Type": "application/json",
        "x-admin-auth": admin_auth,
        "x-custom-auth": custom_auth,
    }

    for attempt in range(5):
        name = rand_name("nv")
        try:
            resp = cffi_requests.post(
                f"{base_url}/admin/new_address",
                json={"name": name, "enablePrefix": False, "domain": domain},
                headers=headers,
                timeout=15,
                impersonate="chrome136",
            )
            if resp.status_code == 200:
                r = resp.json()
                e = TempEmail(
                    address=str(r.get("address") or "").strip(),
                    jwt=str(r.get("jwt") or "").strip(),
                    address_id=int(r.get("address_id") or 0),
                )
                if e.address and e.jwt:
                    log(f"邮箱: {e.address}")
                    return e
                raise RuntimeError(f"不完整: {r}")
            if resp.status_code == 400 and "already exists" in resp.text.lower():
                time.sleep(1)
                continue
            if resp.status_code == 429:
                time.sleep(10)
                continue
            raise RuntimeError(f"{resp.status_code} {resp.text[:200]}")
        except RuntimeError:
            raise
        except Exception as exc:
            if attempt >= 4:
                raise RuntimeError(f"创建邮箱失败: {exc}") from exc
            time.sleep(2)
    raise RuntimeError("创建邮箱失败")


def _default_code_extractor(raw: str) -> str | None:
    m = re.search(r"\b(\d{4,6})\b", raw)
    return m.group(1) if m else None


def poll_code(
    jwt: str,
    config: dict[str, Any],
    *,
    keyword: str = "",
    extractor: Callable[[str], str | None] | None = None,
    timeout: int = 120,
) -> str:
    """轮询邮箱获取验证码

    Args:
        jwt: 邮箱的 JWT token
        config: 邮箱配置
        keyword: 邮件过滤关键词 (不区分大小写)
        extractor: 自定义验证码提取函数 (raw_html -> code | None)
        timeout: 超时秒数
    """
    if extractor is None:
        extractor = _default_code_extractor

    base_url = config.get("base_url", "")
    custom_auth = config.get("custom_auth", "")

    log("等待验证码...")
    deadline = time.time() + timeout
    seen: set[str] = set()
    hdrs = {
        "Accept": "application/json",
        "Authorization": f"Bearer {jwt}",
        "x-custom-auth": custom_auth,
    }

    while time.time() < deadline:
        try:
            resp = cffi_requests.get(
                f"{base_url}/api/mails?limit=10&offset=0",
                headers=hdrs,
                timeout=15,
                impersonate="chrome136",
            )
            if resp.status_code != 200:
                time.sleep(0.5)
                continue

            data = resp.json()
            results = data.get("results") if isinstance(data, dict) else data
            if not isinstance(results, list):
                time.sleep(0.5)
                continue

            for mail in results:
                mid = str(mail.get("id", ""))
                if not mid or mid in seen:
                    continue
                seen.add(mid)

                dr = cffi_requests.get(
                    f"{base_url}/api/mail/{mid}",
                    headers=hdrs,
                    timeout=15,
                    impersonate="chrome136",
                )
                if dr.status_code != 200:
                    continue

                raw = str(dr.json().get("raw", ""))
                if keyword and keyword.lower() not in raw.lower():
                    continue

                clean = re.sub(r'=\r?\n', "", raw)
                code = extractor(clean)
                if code:
                    log(f"验证码: {code}")
                    return code
        except Exception:
            pass
        time.sleep(0.5)

    return ""