"""验证码处理"""
from __future__ import annotations

import time

from playwright.sync_api import Page

from .utils import log


def click_hcaptcha_checkbox(page: Page, timeout: int = 10) -> bool:
    """点击 hCaptcha 的 checkbox, 触发验证弹窗"""
    for attempt in range(3):
        try:
            iframe = page.frame_locator(
                'iframe[title="Widget containing checkbox for hCaptcha security challenge"]'
            )
            iframe.locator("#checkbox").click(timeout=timeout * 1000)
            log("hCaptcha checkbox 已点击 ✓")
            return True
        except Exception:
            time.sleep(1)
    log("hCaptcha checkbox 点击失败", "!")
    return False


def poll_hcaptcha_token(page: Page, timeout: int = 180) -> str:
    """轮询等待 hCaptcha 完成, 返回 token (空字符串表示超时)"""
    log("等待 hCaptcha 完成 (请在浏览器中手动解算)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            token: str = page.evaluate("() => window.hcaptcha?.getResponse?.() || ''")
            if token:
                log(f"检测到 hCaptcha 已完成! ({token[:30]}...)")
                return token
        except Exception:
            pass
        time.sleep(1)
    log("hCaptcha 等待超时", "!")
    return ""