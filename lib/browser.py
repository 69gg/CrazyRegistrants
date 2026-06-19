"""Playwright 浏览器封装"""
from __future__ import annotations

from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright

from .utils import log

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)

CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--start-maximized"]


@contextmanager
def browser_session(ua: str = DEFAULT_UA, headless: bool = False):
    """浏览器会话上下文管理器

    Usage:
        with browser_session() as page:
            page.goto("https://example.com")
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=CHROMIUM_ARGS)
        ctx = browser.new_context(no_viewport=True, user_agent=ua, locale="en-US")
        page = ctx.new_page()
        try:
            yield page
        finally:
            ctx.close()
            browser.close()


def dismiss_cookie(page: Page, timeout: int = 5000) -> None:
    """尝试关闭 Cookie 同意弹窗"""
    try:
        page.click(
            'button:has-text("Agree"), button:has-text("同意"), '
            'button:has-text("Accept")',
            timeout=timeout,
        )
        log("Cookie 弹窗已关闭")
    except Exception:
        pass