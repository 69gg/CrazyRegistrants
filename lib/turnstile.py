"""Cloudflare Turnstile 求解封装"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from random import choice
from shutil import which
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright
from playwright.sync_api import Route

try:
    from patchright.sync_api import Playwright as PatchrightPlaywright
    from patchright.sync_api import sync_playwright as patchright_sync_playwright
except Exception:  # pragma: no cover - 可选依赖
    PatchrightPlaywright = Any  # type: ignore[misc, assignment]
    patchright_sync_playwright = None

from .browser import CHROMIUM_ARGS
from .utils import log


@dataclass
class TurnstileConfig:
    """Turnstile 内置 Playwright 求解配置。"""

    browser_type: str = "patchright"
    browser_name: str = ""
    browser_version: str = ""
    headless: bool = False
    timeout: int = 120
    proxy_url: str = ""
    executable_path: str = ""
    use_random_config: bool = True
    debug: bool = False


def load_turnstile_config(config: dict[str, Any] | None = None) -> TurnstileConfig:
    """从配置字典构造 Turnstile 配置。"""
    config = config or {}
    return TurnstileConfig(
        browser_type=str(config.get("browser_type") or "patchright").strip() or "patchright",
        browser_name=str(config.get("browser_name") or "").strip(),
        browser_version=str(config.get("browser_version") or "").strip(),
        headless=bool(config.get("headless") or False),
        timeout=int(config.get("timeout") or 120),
        proxy_url=str(config.get("proxy_url") or "").strip(),
        executable_path=str(config.get("executable_path") or "").strip(),
        use_random_config=bool(config.get("use_random_config", True)),
        debug=bool(config.get("debug") or False),
    )


@dataclass
class BrowserFingerprint:
    browser_name: str
    browser_version: str
    user_agent: str
    sec_ch_ua: str


def get_browser_fingerprint(config: TurnstileConfig) -> BrowserFingerprint:
    """生成与 grok2api solver 对齐的 Chrome 指纹。"""
    if config.browser_name and config.browser_version:
        name = config.browser_name
        version = config.browser_version
    elif config.use_random_config:
        name = "chrome"
        version = choice(["120.0.0.0", "121.0.0.0", "122.0.0.0", "124.0.0.0"])
    else:
        name = "chrome"
        version = "124.0.0.0"
    major = version.split(".")[0]
    user_agent = (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{version} Safari/537.36"
    )
    sec_ch_ua = f'"Not(A:Brand";v="99", "Google Chrome";v="{major}", "Chromium";v="{major}"'
    return BrowserFingerprint(
        browser_name=name,
        browser_version=version,
        user_agent=user_agent,
        sec_ch_ua=sec_ch_ua,
    )


def resolve_chromium_executable(configured_path: str = "") -> str:
    """解析可用的系统 Chromium/Chrome 路径。"""
    if configured_path:
        return configured_path
    candidates = [
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ]
    for name in candidates:
        path = which(name)
        if path:
            return path
    fixed_paths = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in fixed_paths:
        if Path(path).exists():
            return path
    return ""


def launch_browser(playwright: Playwright | PatchrightPlaywright, config: TurnstileConfig) -> Browser:
    """启动浏览器，优先复用系统 Chrome。"""
    launcher_name = "chromium" if config.browser_type == "patchright" else config.browser_type
    browser_launcher = getattr(playwright, launcher_name, playwright.chromium)
    launch_kwargs: dict[str, Any] = {
        "headless": config.headless,
        "args": [
            *CHROMIUM_ARGS,
            "--window-position=0,0",
            "--force-device-scale-factor=1",
        ],
    }
    if config.browser_type == "chromium":
        executable_path = resolve_chromium_executable(config.executable_path)
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
            if config.debug:
                log(f"使用系统浏览器: {executable_path}")
    return browser_launcher.launch(**launch_kwargs)


def sync_browser_runtime(config: TurnstileConfig):
    """返回可用的同步浏览器运行时。"""
    if config.browser_type == "patchright":
        if patchright_sync_playwright is None:
            log("patchright 不可用，回退 playwright", "!")
            return sync_playwright()
        return patchright_sync_playwright()
    return sync_playwright()


def add_stealth_scripts(page: Page) -> None:
    """注入 grok2api solver 同款基础反自动化脚本。"""
    page.add_init_script(
        """
        (() => {
          const originalAttachShadow = Element.prototype.attachShadow;
          Element.prototype.attachShadow = function(init) {
            const shadow = originalAttachShadow.call(this, init);
            if (init.mode === 'closed') {
              window.__lastClosedShadowRoot = shadow;
            }
            return shadow;
          };

          Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
          });

          window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
          };
        })();
        """
    )


def route_turnstile_resources(route: Route) -> None:
    """拦截非必要资源，保持 Turnstile 加载路径与 grok2api solver 一致。"""
    request = route.request
    url = request.url
    allowed_types = {"document", "script", "xhr", "fetch"}
    allowed_domains = [
        "challenges.cloudflare.com",
        "static.cloudflareinsights.com",
        "cloudflare.com",
        "zenmux.ai",
    ]
    if request.resource_type in allowed_types or any(domain in url for domain in allowed_domains):
        route.continue_()
    else:
        route.abort()


def _set_token_input(page: Page, token: str) -> None:
    page.evaluate(
        """
        (token) => {
          let tokenInput = document.querySelector('input[name="cf-turnstile-response"]');
          if (!tokenInput) {
            tokenInput = document.createElement('input');
            tokenInput.type = 'hidden';
            tokenInput.name = 'cf-turnstile-response';
            document.body.appendChild(tokenInput);
          }
          tokenInput.value = token;
        }
        """,
        token,
    )


def inject_turnstile_widget(
    page: Page,
    *,
    sitekey: str,
    action: str = "",
    cdata: str = "",
) -> None:
    """在当前页面注入 Turnstile widget。"""
    page.evaluate(
        """
        ({ sitekey, action, cdata }) => {
          document.querySelectorAll('[data-crazy-turnstile="1"]').forEach((el) => el.remove());

          const captchaDiv = document.createElement('div');
          captchaDiv.className = 'cf-turnstile';
          captchaDiv.setAttribute('data-crazy-turnstile', '1');
          captchaDiv.setAttribute('data-sitekey', sitekey);
          captchaDiv.style.position = 'fixed';
          captchaDiv.style.top = '20px';
          captchaDiv.style.left = '20px';
          captchaDiv.style.zIndex = '9999';
          captchaDiv.style.backgroundColor = 'white';
          captchaDiv.style.padding = '15px';
          captchaDiv.style.border = '2px solid #0f79af';
          captchaDiv.style.borderRadius = '8px';
          document.body.appendChild(captchaDiv);

          window.__turnstileToken = '';
          window.__turnstileError = '';
          window.__turnstileRenderResult = '';
        }
        """,
        {"sitekey": sitekey, "action": action, "cdata": cdata},
    )
    ensure_turnstile_api(page)
    page.evaluate(
        """
        ({ sitekey, action, cdata }) => {
          const captchaDiv = document.querySelector('[data-crazy-turnstile="1"]');
          if (!captchaDiv) {
            window.__turnstileError = 'Turnstile 容器不存在';
            return;
          }
          if (!window.turnstile?.render) {
            window.__turnstileError = 'Turnstile API 未加载';
            return;
          }
          const options = {
            sitekey,
            callback: (token) => {
              window.__turnstileToken = token;
              let tokenInput = document.querySelector('input[name="cf-turnstile-response"]');
              if (!tokenInput) {
                tokenInput = document.createElement('input');
                tokenInput.type = 'hidden';
                tokenInput.name = 'cf-turnstile-response';
                document.body.appendChild(tokenInput);
              }
              tokenInput.value = token;
            },
            'error-callback': (error) => {
              window.__turnstileError = String(error || 'Turnstile 验证失败');
            },
          };
          if (action) {
            options.action = action;
          }
          if (cdata) {
            options.cdata = cdata;
          }
          try {
            window.__turnstileWidgetId = window.turnstile.render(captchaDiv, options);
            window.__turnstileRenderResult = String(window.__turnstileWidgetId || 'rendered-empty-id');
          } catch (error) {
            window.__turnstileError = String(error || 'Turnstile render 失败');
            window.__turnstileRenderResult = 'render-error';
          }
        }
        """,
        {"sitekey": sitekey, "action": action, "cdata": cdata},
    )


def ensure_turnstile_api(page: Page) -> None:
    """确保 Turnstile API 可用。"""
    try:
        page.wait_for_function("() => !!window.turnstile?.render", timeout=5_000)
        return
    except Exception:
        pass

    page.evaluate(
        """
        () => {
          window.__turnstileError = '';
          document.querySelectorAll('script[data-crazy-turnstile-api="1"]').forEach((el) => el.remove());
        }
        """
    )
    page.add_script_tag(
        url="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
        type="text/javascript",
    )
    try:
        page.wait_for_function("() => !!window.turnstile?.render", timeout=15_000)
    except Exception:
        page.evaluate("() => { window.__turnstileError = 'Turnstile API 未加载'; }")


def click_turnstile_checkbox(page: Page, *, debug: bool = False) -> bool:
    """尝试点击 Turnstile checkbox。"""
    if debug:
        log_turnstile_state(page)
    iframe_selectors = [
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="challenge-platform"]',
        'iframe[src*="turnstile"]',
        'iframe[title*="widget"]',
        'iframe[title*="Cloudflare"]',
    ]
    checkbox_selectors = [
        'input[type="checkbox"]',
        '.cb-lb input[type="checkbox"]',
        'label input[type="checkbox"]',
        '[role="checkbox"]',
    ]

    for iframe_selector in iframe_selectors:
        try:
            iframe = page.locator(iframe_selector).first
            if iframe.count() <= 0:
                continue

            frame = iframe.element_handle().content_frame()
            if frame is not None:
                for checkbox_selector in checkbox_selectors:
                    try:
                        frame.locator(checkbox_selector).first.click(timeout=2_000)
                        if debug:
                            log(f"已点击 Turnstile checkbox: {checkbox_selector}")
                        return True
                    except Exception:
                        continue

            box = iframe.bounding_box()
            if box:
                _click_box_points(
                    page,
                    box,
                    points=[
                        (0.12, 0.50),
                        (0.10, 0.58),
                        (38.0, 50.0),
                    ],
                    debug=debug,
                    label="Turnstile iframe",
                )
                if debug:
                    log("已点击 Turnstile iframe 坐标")
                return True
            iframe.click(timeout=1_000)
            if debug:
                log("已点击 Turnstile iframe")
            return True
        except Exception:
            continue

    for selector in [".cf-turnstile", "[data-sitekey]"]:
        try:
            locator = page.locator(selector).first
            if locator.count() <= 0:
                continue
            box = locator.bounding_box()
            if box:
                _click_box_points(
                    page,
                    box,
                    points=[
                        (38.0, 50.0),
                        (0.12, 0.50),
                        (0.10, 0.58),
                        (0.15, 0.50),
                    ],
                    debug=debug,
                    label=selector,
                )
            else:
                locator.click(timeout=1_000)
            if debug:
                log(f"已点击 Turnstile 容器: {selector}")
            return True
        except Exception:
            continue
    return False


def log_turnstile_state(page: Page) -> None:
    """输出 Turnstile 页面结构，辅助定位点击失败。"""
    try:
        state = page.evaluate(
            """
            () => ({
              href: location.href,
              iframes: Array.from(document.querySelectorAll('iframe')).map((el) => ({
                title: el.getAttribute('title') || '',
                src: el.src || '',
                rect: (() => {
                  const r = el.getBoundingClientRect();
                  return { x: r.x, y: r.y, width: r.width, height: r.height };
                })(),
              })),
              widgets: Array.from(document.querySelectorAll('.cf-turnstile, [data-sitekey]')).map((el) => ({
                tag: el.tagName,
                className: el.className,
                sitekey: el.getAttribute('data-sitekey') || '',
                html: el.outerHTML.slice(0, 300),
                rect: (() => {
                  const r = el.getBoundingClientRect();
                  return { x: r.x, y: r.y, width: r.width, height: r.height };
                })(),
              })),
              inputs: Array.from(document.querySelectorAll('input[name="cf-turnstile-response"]')).map((el) => ({
                valueLength: el.value.length,
                id: el.id || '',
              })),
              turnstile: {
                type: typeof window.turnstile,
                hasRender: !!window.turnstile?.render,
                tokenLength: String(window.__turnstileToken || '').length,
                error: String(window.__turnstileError || ''),
                renderResult: String(window.__turnstileRenderResult || ''),
                widgetId: String(window.__turnstileWidgetId || ''),
              },
            })
            """
        )
        frame_urls = [frame.url for frame in page.frames if frame != page.main_frame]
        log(f"Turnstile DOM: {state}")
        log(f"Turnstile frames: {frame_urls}")
    except Exception as exc:
        log(f"Turnstile DOM 诊断失败: {exc}", "!")


def _click_box_points(
    page: Page,
    box: dict[str, float],
    *,
    points: list[tuple[float, float]],
    debug: bool = False,
    label: str = "",
) -> None:
    """按绝对偏移或比例点击元素内的多个候选点。"""
    for raw_x, raw_y in points:
        x_offset = raw_x * box["width"] if 0 < raw_x < 1 else raw_x
        y_offset = raw_y * box["height"] if 0 < raw_y < 1 else raw_y
        x = box["x"] + x_offset
        y = box["y"] + y_offset
        if debug:
            log(f"点击 {label} 坐标: x={x:.1f}, y={y:.1f}")
        page.mouse.click(x, y)
        time.sleep(0.2)


def poll_turnstile_token(
    page: Page,
    *,
    timeout: int = 120,
    interval: float = 0.5,
    auto_click: bool = True,
    debug: bool = False,
) -> str:
    """轮询当前页面 Turnstile token。"""
    deadline = time.time() + timeout
    last_error = ""
    next_click_at = 0.0
    while time.time() < deadline:
        token = str(
            page.evaluate(
                """
                () => window.__turnstileToken
                  || document.querySelector('input[name="cf-turnstile-response"]')?.value
                  || ''
                """
            )
            or ""
        )
        if token:
            _set_token_input(page, token)
            log(f"Turnstile token: {token[:30]}...")
            return token
        now = time.time()
        if auto_click and now >= next_click_at:
            click_turnstile_checkbox(page, debug=debug)
            next_click_at = now + 2.0
        last_error = str(page.evaluate("() => window.__turnstileError || ''") or "")
        time.sleep(interval)
    if last_error:
        log(f"Turnstile 等待超时: {last_error}", "!")
    else:
        log("Turnstile 等待超时", "!")
    return ""


def solve_turnstile(
    *,
    page_url: str,
    sitekey: str,
    config: TurnstileConfig | None = None,
    action: str = "",
    cdata: str = "",
    user_agent: str = "",
) -> str:
    """打开页面、注入 Turnstile widget 并返回 token。"""
    cfg = config or TurnstileConfig()
    fingerprint = get_browser_fingerprint(cfg)
    resolved_user_agent = user_agent or fingerprint.user_agent
    proxy = {"server": cfg.proxy_url} if cfg.proxy_url else None
    log(f"打开 Turnstile 页面: {page_url}")
    with sync_browser_runtime(cfg) as p:
        browser = launch_browser(p, cfg)
        ctx = browser.new_context(
            user_agent=resolved_user_agent,
            locale="en-US",
            proxy=proxy,
            extra_http_headers={"sec-ch-ua": fingerprint.sec_ch_ua},
        )
        page = ctx.new_page()
        try:
            add_stealth_scripts(page)
            page.set_viewport_size({"width": 500, "height": 100})
            page.route("**/*", route_turnstile_resources)
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                log(f"Turnstile 页面导航异常，继续尝试: {exc}", "!")
            page.unroute("**/*", route_turnstile_resources)
            inject_turnstile_widget(page, sitekey=sitekey, action=action, cdata=cdata)
            time.sleep(3)
            return poll_turnstile_token(page, timeout=cfg.timeout, debug=cfg.debug)
        finally:
            ctx.close()
            browser.close()
