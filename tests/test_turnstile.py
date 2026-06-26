from __future__ import annotations

from unittest import TestCase

from lib.turnstile import (
    BrowserFingerprint,
    TurnstileConfig,
    click_turnstile_checkbox,
    get_browser_fingerprint,
    load_turnstile_config,
    resolve_chromium_executable,
)


class TurnstileConfigTest(TestCase):
    def test_load_config_parses_values(self) -> None:
        config = load_turnstile_config(
            {
                "browser_type": "chromium",
                "browser_name": "chrome",
                "browser_version": "124.0.0.0",
                "headless": True,
                "timeout": 60,
                "debug": True,
                "proxy_url": "http://127.0.0.1:7890",
                "executable_path": "/usr/bin/google-chrome-stable",
                "use_random_config": False,
            }
        )

        self.assertEqual(config.browser_type, "chromium")
        self.assertEqual(config.browser_name, "chrome")
        self.assertEqual(config.browser_version, "124.0.0.0")
        self.assertTrue(config.headless)
        self.assertEqual(config.timeout, 60)
        self.assertTrue(config.debug)
        self.assertEqual(config.proxy_url, "http://127.0.0.1:7890")
        self.assertEqual(config.executable_path, "/usr/bin/google-chrome-stable")
        self.assertFalse(config.use_random_config)

    def test_load_config_defaults(self) -> None:
        config = load_turnstile_config({})

        self.assertEqual(config, TurnstileConfig())

    def test_resolve_chromium_executable_keeps_configured_path(self) -> None:
        self.assertEqual(resolve_chromium_executable("/tmp/chrome"), "/tmp/chrome")

    def test_get_browser_fingerprint_from_config(self) -> None:
        fingerprint = get_browser_fingerprint(
            TurnstileConfig(
                browser_name="chrome",
                browser_version="124.0.0.0",
                use_random_config=False,
            )
        )

        self.assertEqual(
            fingerprint,
            BrowserFingerprint(
                browser_name="chrome",
                browser_version="124.0.0.0",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                sec_ch_ua='"Not(A:Brand";v="99", "Google Chrome";v="124", "Chromium";v="124"',
            ),
        )

    def test_click_turnstile_checkbox_returns_false_without_widget(self) -> None:
        class DummyLocator:
            def count(self) -> int:
                return 0

        class DummyPage:
            def locator(self, selector: str) -> DummyLocator:
                return DummyLocator()

        self.assertFalse(click_turnstile_checkbox(DummyPage()))  # type: ignore[arg-type]
