from __future__ import annotations

from typing import Any
from unittest import TestCase, mock

from lib.http_client import (
    ApiError,
    JsonApiClient,
    random_forward_headers,
    random_ip,
    random_user_agent,
)
from platforms.agnes_ai.pipeline import _agnes_code_extractor


class _FakeResp:
    def __init__(self, status: int, payload: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _FakeSession:
    """按预设序列依次返回响应, 记录请求次数"""

    def __init__(self, responses: list[_FakeResp]) -> None:
        self._responses = responses
        self.calls = 0
        self.headers: dict[str, str] = {}
        self.sent_headers: list[dict[str, str]] = []  # 记录每次请求的 headers

    def request(self, *args: Any, **kwargs: Any) -> _FakeResp:
        self.sent_headers.append(dict(kwargs.get("headers") or {}))
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp

# 真实注册邮件正文样本 (HTML 去标签前)
REAL_MAIL_HTML = (
    '<div class="content">Verify your email address</div>'
    '<p>please enter the verification code to confirm your email address:</p>'
    '<div class="verification-code">458847</div>'
    '<p>Agnes Team</p><p>=C2=A9 2025 Agnes AI</p>'
)


class AgnesCodeExtractorTest(TestCase):
    def test_extract_from_real_mail(self) -> None:
        # 必须抓到 458847, 而非版权年份 2025
        self.assertEqual(_agnes_code_extractor(REAL_MAIL_HTML), "458847")

    def test_extract_ignores_leading_year(self) -> None:
        raw = "© 2026 Agnes. verification code to confirm your email address: 123456"
        self.assertEqual(_agnes_code_extractor(raw), "123456")

    def test_extract_by_keyword_fallback(self) -> None:
        raw = "您的验证码 是 654321, 请勿泄露"
        self.assertEqual(_agnes_code_extractor(raw), "654321")

    def test_extract_plain_six_digits(self) -> None:
        self.assertEqual(_agnes_code_extractor("Code 246810 valid 10min"), "246810")

    def test_extract_returns_none_without_code(self) -> None:
        self.assertIsNone(_agnes_code_extractor("no digits here at all"))

    def test_extract_skips_long_digit_runs(self) -> None:
        # 纯 7 位/8 位串不应被当作 6 位验证码误截取
        self.assertIsNone(_agnes_code_extractor("ref 12345678 and 9999999 only"))


class JsonApiClientTest(TestCase):
    def test_default_headers_built(self) -> None:
        client = JsonApiClient("https://api.example.com/", origin="https://app.example.com")
        headers = client.session.headers
        self.assertEqual(headers.get("origin"), "https://app.example.com")
        self.assertEqual(headers.get("referer"), "https://app.example.com/")
        self.assertEqual(headers.get("x-user-language"), "zh-CN")
        self.assertEqual(client.base_url, "https://api.example.com")

    def test_auth_headers_bearer_null_when_no_token(self) -> None:
        client = JsonApiClient("https://api.example.com")
        self.assertEqual(client._auth_headers(), {"authorization": "Bearer null"})

    def test_auth_headers_with_token(self) -> None:
        client = JsonApiClient("https://api.example.com")
        client.set_token("tok123")
        self.assertEqual(client._auth_headers(), {"authorization": "Bearer tok123"})

    def test_api_error_carries_status_and_code(self) -> None:
        err = ApiError("boom", status=500, code=4001)
        self.assertEqual(err.status, 500)
        self.assertEqual(err.code, 4001)

    def test_retry_on_429_then_success(self) -> None:
        client = JsonApiClient("https://api.example.com", retry_backoff=0.01)
        client.session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResp(429, {"code": 429, "message": "rate"}),
                _FakeResp(200, {"code": 200, "message": "ok", "data": {"k": "v"}}),
            ]
        )
        with mock.patch("lib.http_client.time.sleep"):
            data = client.get("/api/foo")
        self.assertEqual(data, {"k": "v"})
        self.assertEqual(client.session.calls, 2)  # type: ignore[attr-defined]

    def test_retry_honors_retry_after_header(self) -> None:
        client = JsonApiClient("https://api.example.com")
        client.session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResp(429, {"code": 429}, headers={"retry-after": "7"}),
                _FakeResp(200, {"code": 200, "data": None}),
            ]
        )
        with mock.patch("lib.http_client.time.sleep") as sleep_mock:
            client.get("/api/foo")
        sleep_mock.assert_called_once_with(7.0)

    def test_retry_after_capped_to_max_wait(self) -> None:
        # 服务端返回超长 Retry-After (如 1800s) 应被封顶到 max_retry_wait, 不死等
        client = JsonApiClient("https://api.example.com", max_retry_wait=30.0)
        client.session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResp(429, {"code": 429}, headers={"retry-after": "1800"}),
                _FakeResp(200, {"code": 200, "data": None}),
            ]
        )
        with mock.patch("lib.http_client.time.sleep") as sleep_mock:
            client.get("/api/foo")
        sleep_mock.assert_called_once_with(30.0)

    def test_retry_exhausted_raises(self) -> None:
        client = JsonApiClient("https://api.example.com", max_retries=2, retry_backoff=0.01)
        client.session = _FakeSession([_FakeResp(429, {"code": 429})])  # type: ignore[assignment]
        with mock.patch("lib.http_client.time.sleep"):
            with self.assertRaises(ApiError) as ctx:
                client.get("/api/foo")
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(client.session.calls, 3)  # type: ignore[attr-defined]  # 1 + 2 retries

    def test_randomized_headers_injected_per_request(self) -> None:
        client = JsonApiClient("https://api.example.com", randomize_headers=True)
        client.session = _FakeSession([_FakeResp(200, {"code": 200, "data": None})])  # type: ignore[assignment]
        client.get("/api/foo")
        sent = client.session.sent_headers[0]  # type: ignore[attr-defined]
        for key in ("user-agent", "x-forwarded-for", "x-real-ip", "x-client-ip"):
            self.assertIn(key, sent)

    def test_randomization_can_be_disabled(self) -> None:
        client = JsonApiClient("https://api.example.com", randomize_headers=False)
        client.session = _FakeSession([_FakeResp(200, {"code": 200, "data": None})])  # type: ignore[assignment]
        client.get("/api/foo")
        sent = client.session.sent_headers[0]  # type: ignore[attr-defined]
        self.assertNotIn("x-forwarded-for", sent)
        self.assertNotIn("user-agent", sent)

    def test_retry_rerandomizes_headers(self) -> None:
        # 重试时应换新的 UA/IP (而非沿用首次)
        client = JsonApiClient("https://api.example.com", retry_backoff=0.01)
        client.session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResp(429, {"code": 429}),
                _FakeResp(200, {"code": 200, "data": None}),
            ]
        )
        with mock.patch("lib.http_client.time.sleep"):
            with mock.patch(
                "lib.http_client.random_forward_headers",
                side_effect=[
                    {"user-agent": "UA1", "x-forwarded-for": "1.1.1.1"},
                    {"user-agent": "UA2", "x-forwarded-for": "2.2.2.2"},
                ],
            ):
                client.get("/api/foo")
        sent = client.session.sent_headers  # type: ignore[attr-defined]
        self.assertEqual(sent[0]["x-forwarded-for"], "1.1.1.1")
        self.assertEqual(sent[1]["x-forwarded-for"], "2.2.2.2")


class RandomHeaderHelpersTest(TestCase):
    def test_random_user_agent_format(self) -> None:
        ua = random_user_agent()
        self.assertTrue(ua.startswith("Mozilla/5.0"))
        self.assertIn("Chrome/", ua)

    def test_random_ip_is_valid_public_ipv4(self) -> None:
        for _ in range(50):
            octets = [int(x) for x in random_ip().split(".")]
            self.assertEqual(len(octets), 4)
            self.assertTrue(all(0 <= o <= 255 for o in octets))
            self.assertNotEqual(octets[0], 127)  # 排除环回
            self.assertNotEqual(octets[0], 0)

    def test_forward_headers_share_one_ip(self) -> None:
        h = random_forward_headers()
        self.assertEqual(h["x-forwarded-for"], h["x-real-ip"])
        self.assertEqual(h["x-forwarded-for"], h["x-client-ip"])

    def test_random_user_agent_varies(self) -> None:
        # 多次生成应出现多个不同值 (概率上几乎必然)
        uas = {random_user_agent() for _ in range(50)}
        self.assertGreater(len(uas), 1)
