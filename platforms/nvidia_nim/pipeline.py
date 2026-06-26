"""NVIDIA build.nvidia.com 自动注册 + API Key 获取

流水线:
    创建邮箱 → 打开浏览器 → 填邮箱 → 填密码 → hCaptcha → 提交注册
    → 邮箱验证码 → 条款 → Cloud Account → Generate Key → 保存
"""
from __future__ import annotations

import re
import threading
import time
import traceback

from lib.base import BaseRegistrant, RegistrantMeta
from lib.browser import browser_session, dismiss_cookie
from lib.captcha import click_hcaptcha_checkbox, poll_hcaptcha_token
from lib.config import get_email_config, get_platform_config
from lib.email_client import TempEmail, create_email, poll_code
from lib.utils import log, rand_name, save_key, set_worker_id

DEFAULT_BUILD_URL = "https://build.nvidia.com"


def _nvidia_code_extractor(raw: str) -> str | None:
    """NVIDIA 邮件验证码提取: font-weight: bold; font-size: 1.5em; > 123-456 <"""
    m = re.search(
        r'font-weight:\s*bold.*?font-size:\s*1\.5em.*?>\s*(\d{3})\s*[-–]\s*(\d{3})\s*<',
        raw,
        re.I,
    )
    if m:
        return m.group(1) + m.group(2)
    return None


class NvidiaNimRegistrant(BaseRegistrant):
    meta = RegistrantMeta(
        name="nvidia-nim",
        description="NVIDIA build.nvidia.com 自动注册获取 API Key",
    )

    def register_one(self, idx: int, password: str) -> str | None:
        set_worker_id(idx)

        email_cfg = get_email_config()
        platform_cfg = get_platform_config(self.meta.name)
        build_url = platform_cfg.get("build_url", DEFAULT_BUILD_URL)

        log("=" * 40)
        log("开始注册")
        log("=" * 40)

        email_result: list[TempEmail] = []
        email_err: list[Exception] = []

        def _do_create() -> None:
            try:
                email_result.append(create_email(email_cfg))
            except Exception as e:
                email_err.append(e)

        email_thread = threading.Thread(target=_do_create, daemon=True)
        email_thread.start()

        try:
            with browser_session() as page:
                _preload_page(page, build_url)
                email_thread.join()

                if email_err:
                    raise email_err[0]
                email_obj = email_result[0]

                jwt_key = _fill_email(page, email_obj.address)
                log(f"JWT: {jwt_key[:40]}...")

                for _ in range(20):
                    time.sleep(0.2)
                    has_two = page.locator('input[type="password"]').count() >= 2
                    is_create = "create-account" in page.url
                    if has_two or is_create:
                        break

                is_new = "create-account" in page.url
                has_two = page.locator('input[type="password"]').count() >= 2
                if not is_new and not has_two:
                    log("已是登录页 (邮箱可能被注册过), 重试")
                    return None

                _fill_password(page, password)

                click_hcaptcha_checkbox(page)
                token = poll_hcaptcha_token(page)
                if not token:
                    return None

                page.wait_for_selector(
                    'button:has-text("Create Account"):not([disabled])', timeout=10000
                )
                page.click('button:has-text("Create Account")')
                log("Create Account ✓")

                if not _handle_verification(page, email_obj.jwt, email_cfg):
                    return None

                _click_submit(page)
                _handle_cloud_account(page)

                api_key = _generate_key(page)
                if api_key:
                    save_key("nvidia_nim", api_key)
                    log(f"完成! {email_obj.address}")
                return api_key

        except Exception as exc:
            log(f"失败: {exc}", "!")
            traceback.print_exc()
            return None


def _preload_page(page, build_url: str) -> None:
    page.goto(
        f"{build_url}/explore/discover",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_load_state("networkidle")
    dismiss_cookie(page)
    page.click('button:has-text("Get API Key")')
    page.wait_for_selector(
        'input[type="email"], input[placeholder*="email"]', timeout=10000
    )
    log("页面就绪, 等待邮箱...")


def _fill_email(page, email: str) -> str:
    page.locator('input[type="email"], input[placeholder*="email"]').first.fill(email)
    page.click('button:has-text("Next")')
    page.wait_for_url("**/login.nvgs.nvidia.com/**", timeout=15000)
    for _ in range(15):
        time.sleep(0.2)
        if "create-account" in page.url:
            break
    log(f"页面: {page.url[:100]}...")
    m = re.search(r'[?&]key=([^&]+)', page.url)
    if not m:
        raise RuntimeError(f"未找到 JWT: {page.url[:200]}")
    return m.group(1)


def _fill_password(page, password: str) -> None:
    page.wait_for_selector('input[type="password"]', timeout=15000)
    pwds = page.locator('input[type="password"]')
    pwds.first.fill(password)
    if pwds.count() >= 2:
        pwds.nth(1).fill(password)
    log("密码已填入 ✓")


def _on_verify_page(page) -> bool:
    try:
        return "Verify your email" in page.content() or "verify" in page.url.lower()
    except Exception:
        return False


def _handle_verification(page, jwt: str, email_cfg: dict) -> bool:
    log("等待验证页面...")
    for i in range(120):
        try:
            if "Verify your email" in page.content():
                log(f"已进入验证页 ({i * 0.5:.0f}s)")
                break
        except Exception:
            pass
        time.sleep(0.5)

    for retry in range(3):
        log(f"验证码尝试 {retry + 1}/3")
        code = poll_code(
            jwt,
            email_cfg,
            keyword="nvidia",
            extractor=_nvidia_code_extractor,
            timeout=120,
        )
        if not code:
            log(f"未收到码 ({retry + 1}/3)")
            continue
        if _try_fill_code(page, code):
            log("验证码 ✓")
            return True
        try:
            page.click('text=Request a new one')
            time.sleep(1)
        except Exception:
            pass
    log("验证码重试耗尽", "!")
    return False


def _try_fill_code(page, code: str) -> bool:
    if not _on_verify_page(page):
        log("页面已离开验证页 (自动验证)")
        return True

    for attempt in range(5):
        log(f"填入验证码 (attempt {attempt + 1})")
        if not _on_verify_page(page):
            log("已离开验证页")
            return True

        spinners = page.locator('[role="spinbutton"]')
        if spinners.count() >= 6:
            for i in range(6):
                spinners.nth(i).fill(code[i])
        else:
            inputs = page.locator(
                'input:not([type="checkbox"]):not([type="submit"])'
                ':not([type="hidden"]):not([readonly])'
            )
            try:
                for i in range(min(6, inputs.count())):
                    inputs.nth(i).fill(code[i])
            except Exception:
                try:
                    page.keyboard.type(code)
                except Exception:
                    pass

        try:
            page.wait_for_selector(
                'button:has-text("Continue"):not([disabled])', timeout=3000
            )
            page.click('button:has-text("Continue")')
            for _ in range(10):
                time.sleep(0.5)
                if not _on_verify_page(page):
                    log("验证码已提交 ✓ (页面已跳转)")
                    return True
            try:
                if "Invalid" in page.content():
                    log("验证码无效!")
                    return False
            except Exception:
                pass
            log("验证码已提交 ✓")
            return True
        except Exception:
            time.sleep(0.5)

        if not _on_verify_page(page):
            return True

    return False


def _click_submit(page) -> None:
    log("等待条款页面...")
    for _ in range(120):
        try:
            btn = page.locator(
                'button:has-text("Submit"), button:has-text("提交"), '
                'input[type="submit"]'
            ).first
            if btn.is_visible() and btn.is_enabled():
                btn.click()
                log("条款已同意 ✓")
                return
        except Exception:
            pass
        time.sleep(0.5)


def _handle_cloud_account(page) -> None:
    log("等待 Cloud Account...")
    for _ in range(120):
        try:
            c = page.content()
        except Exception:
            c = ""

        if "Cloud Account" not in c and "cloud accounts" not in c.lower():
            try:
                if page.locator('button:has-text("Generate Key")').first.is_visible():
                    log("跳过 Cloud Account")
                    break
            except Exception:
                pass
        else:
            org = rand_name("NvOrg", 3)
            try:
                page.locator("input").first.fill(org)
            except Exception:
                try:
                    page.keyboard.type(org)
                except Exception:
                    pass
            for _ in range(20):
                try:
                    btn = page.locator(
                        'button:has-text("Create"):not([disabled])'
                    ).first
                    if btn.is_visible():
                        btn.click()
                        log(f"'{org}' ✓")
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            break
        time.sleep(0.5)


def _generate_key(page) -> str | None:
    log("等待 Generate Key...")
    for _ in range(240):
        try:
            btn = page.locator('button:has-text("Generate Key")').first
            if btn.is_visible():
                btn.click()
                log("已点击 Generate Key")
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        log("未找到 Generate Key", "!")
        return None

    for _ in range(60):
        try:
            inp = page.locator('input[value*="nvapi-"]').first
            if inp.is_visible():
                api_key = inp.input_value()
                log(f"Key: {api_key}")
                return api_key
        except Exception:
            pass
        time.sleep(0.5)

    log("未提取到 Key", "!")
    return None