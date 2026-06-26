from __future__ import annotations

from typing import Any
from unittest import TestCase, mock

from lib.http_client import ApiError, JsonApiClient
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

    def request(self, *args: Any, **kwargs: Any) -> _FakeResp:
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

    def test_retry_exhausted_raises(self) -> None:
        client = JsonApiClient("https://api.example.com", max_retries=2, retry_backoff=0.01)
        client.session = _FakeSession([_FakeResp(429, {"code": 429})])  # type: ignore[assignment]
        with mock.patch("lib.http_client.time.sleep"):
            with self.assertRaises(ApiError) as ctx:
                client.get("/api/foo")
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(client.session.calls, 3)  # type: ignore[attr-defined]  # 1 + 2 retries
