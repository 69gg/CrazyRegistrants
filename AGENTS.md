# 开发规范

## 添加新平台

1. 在 `platforms/` 下创建目录, 如 `platforms/new_platform/`
2. 创建 `__init__.py`, 导出 `REGISTRANT` 实例:

```python
# platforms/new_platform/__init__.py
from .pipeline import NewPlatformRegistrant

REGISTRANT = NewPlatformRegistrant()
```

3. 创建 `pipeline.py`, 继承 `lib.base.BaseRegistrant`:

```python
from lib.base import BaseRegistrant, RegistrantMeta

class NewPlatformRegistrant(BaseRegistrant):
    meta = RegistrantMeta(
        name="new-platform",        # CLI 子命令名 (仅小写+连字符)
        description="平台说明",
    )

    def register_one(self, idx: int, password: str) -> str | None:
        # 单次注册流水线
        # 返回 key 或 None (None 会触发重试)
        ...
```

4. 创建 `README.md` 说明平台用法
5. 在 `config.toml.example` 添加 `[platforms.new_platform]` 配置段
6. CLI 会自动发现, 无需手动注册

## BaseRegistrant 接口

```python
class BaseRegistrant(ABC):
    meta: RegistrantMeta

    def add_args(self, parser): ...    # 覆盖以添加平台专属 CLI 参数
    def run(self, args): ...           # 已实现: 多进程调度 + 重试
    def register_one(self, idx, password) -> str | None: ...  # 必须实现
```

- `register_one()` 返回 `str` 表示成功, `None` 表示失败 (外层自动重试)
- `register_one()` 会运行在多进程中 (仅 `-w > 1` 时), 避免全局状态
- 密码由 `run()` 自动生成传入, 无需自己生成

## CLI 通用参数 (基类已实现)

- `-n/--count`: 注册数量。`N > 0` 注册满 N 个成功账号即停; **`N = 0` 无限注册** (惰性下发任务, 直到 `Ctrl-C` 优雅停止并汇总)
- `-w/--workers`: 并行进程数。无限模式下不受 count 限制

## 两种实现路径

| 路径 | 适用 | 基建 | 示例 |
|------|------|------|------|
| **纯协议** | 后端有可直接调用的 JSON API, 无人机验证 | `lib.http_client.JsonApiClient` + `lib.email_client` | `agnes_ai` |
| **浏览器** | 需走前端 / 有 hCaptcha / Turnstile | `lib.browser` + `lib.captcha` / `lib.turnstile` | `nvidia_nim` |

优先走协议路径 (快、稳、无需图形界面)。先用抓包确认接口与人机验证情况, 再决定路径。

### 纯协议路径速查

```python
from lib.http_client import JsonApiClient

client = JsonApiClient(api_base, origin="https://app.example.com")
data = client.get("/api/verification", params={...})   # 自动解包 data 字段
client.set_token(data["access_token"])                 # 注入 Bearer
client.post("/api/token", json={...})                  # 非 200 码自动抛 ApiError
```

- `JsonApiClient` 基于 curl_cffi 模拟浏览器指纹 (默认 `chrome131`), 自动持久化 Cloudflare `__cf_bm` cookie
- 自定义验证码提取器配合 `poll_code(extractor=...)` 使用 (注意排除版权年份等干扰数字)

## 可复用模块 (lib/)

| 模块 | 功能 |
|------|------|
| `lib.utils` | `log()`, `gen_password()`, `rand_name()`, `save_key()`, `save_account()`, `set_worker_id()` |
| `lib.config` | `load_config()`, `get_email_config()`, `get_turnstile_config()`, `get_platform_config()` |
| `lib.email_client` | `create_email()`, `poll_code()`, `TempEmail` |
| `lib.http_client` | `JsonApiClient` (协议路径 JSON API 客户端), `ApiError` |
| `lib.browser` | `browser_session()` 上下文, `dismiss_cookie()` |
| `lib.captcha` | `click_hcaptcha_checkbox()`, `poll_hcaptcha_token()` |
| `lib.turnstile` | `solve_turnstile()`, `inject_turnstile_widget()`, `click_turnstile_checkbox()`, `poll_turnstile_token()` |

## 代码风格

- 所有函数带类型注释
- Python >= 3.11 语法
- 用 `from __future__ import annotations` 推迟求值
- 中文注释和日志

## 配置约定

- 邮箱共享配置放 `[email]` 段
- Turnstile 共享配置放 `[turnstile]` 段，使用内置 Playwright 求解，不依赖外部脚本
- 平台专属配置放 `[platforms.<目录名>]` 段
- 目录名用下划线 (`nvidia_nim`), CLI 名用连字符 (`nvidia-nim`)

## 附录

- 请及时维护该AGENTS.md文件
