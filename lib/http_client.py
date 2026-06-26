"""协议路径通用 HTTP 客户端

为"纯协议"平台 (直接调后端 JSON API, 不走浏览器) 提供可复用基建:
    - curl_cffi Session 浏览器指纹模拟, 自动持久化 Cloudflare __cf_bm cookie
    - 统一注入公共请求头 (origin/referer/x-user-language)
    - 统一解包 {"code","message","data"} 响应信封, 非成功码抛错
    - Bearer Token 鉴权注入
"""
from __future__ import annotations

import time
from typing import Any

from curl_cffi import requests as cffi_requests

from .utils import log

DEFAULT_IMPERSONATE = "chrome131"


class ApiError(RuntimeError):
    """后端返回非成功响应 (HTTP 非 2xx 或信封 code != 期望值)"""

    def __init__(self, message: str, *, status: int = 0, code: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class JsonApiClient:
    """基于 curl_cffi 的 JSON API 客户端

    Usage:
        client = JsonApiClient(
            "https://api.example.com",
            origin="https://app.example.com",
        )
        data = client.get("/api/foo", params={"x": 1})   # 返回 data 字段
        client.set_token(data["access_token"])
        client.post("/api/bar", json={"k": "v"})
    """

    def __init__(
        self,
        base_url: str,
        *,
        origin: str = "",
        referer: str = "",
        language: str = "zh-CN",
        impersonate: str = DEFAULT_IMPERSONATE,
        timeout: int = 20,
        success_code: int = 200,
        max_retries: int = 3,
        retry_backoff: float = 5.0,
        max_retry_wait: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.success_code = success_code
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        # 单次重试最长等待 (秒): 服务端 Retry-After 过长时封顶, 避免死等
        self.max_retry_wait = max_retry_wait
        self._token: str = ""

        headers: dict[str, str] = {"content-type": "application/json"}
        if origin:
            headers["origin"] = origin
        if referer:
            headers["referer"] = referer
        elif origin:
            headers["referer"] = origin.rstrip("/") + "/"
        if language:
            headers["x-user-language"] = language

        self.session = cffi_requests.Session(impersonate=impersonate, headers=headers)

    def set_token(self, token: str) -> None:
        """设置后续请求的 Bearer Token"""
        self._token = token

    def _auth_headers(self) -> dict[str, str]:
        # 未登录时部分接口要求显式传 Bearer null (对齐前端行为)
        return {"authorization": f"Bearer {self._token}" if self._token else "Bearer null"}

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, json=json)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        for attempt in range(self.max_retries + 1):
            resp = self.session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
            # 限流: 退避后重试 (优先遵循 Retry-After, 否则指数退避; 统一封顶避免死等)
            if resp.status_code == 429 and attempt < self.max_retries:
                wait = min(
                    self._retry_after(resp) or self.retry_backoff * (2**attempt),
                    self.max_retry_wait,
                )
                log(f"{path} 被限流 (429), {wait:.0f}s 后重试 ({attempt + 1}/{self.max_retries})", "!")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                raise ApiError(
                    f"{method} {path} HTTP {resp.status_code}: {resp.text[:200]}",
                    status=resp.status_code,
                )
            try:
                payload = resp.json()
            except Exception as exc:
                raise ApiError(f"{method} {path} 响应非 JSON: {resp.text[:200]}") from exc

            code = payload.get("code")
            if code != self.success_code:
                raise ApiError(
                    f"{method} {path} 业务失败 code={code}: {payload.get('message', '')}",
                    status=resp.status_code,
                    code=code,
                )
            return payload.get("data")

        raise ApiError(f"{method} {path} 限流重试耗尽", status=429)

    @staticmethod
    def _retry_after(resp: Any) -> float:
        """解析 Retry-After 响应头 (秒), 无则返回 0"""
        raw = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
        try:
            return float(raw) if raw else 0.0
        except (TypeError, ValueError):
            return 0.0
