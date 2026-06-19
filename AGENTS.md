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

## 可复用模块 (lib/)

| 模块 | 功能 |
|------|------|
| `lib.utils` | `log()`, `gen_password()`, `rand_name()`, `save_key()`, `set_worker_id()` |
| `lib.config` | `load_config()`, `get_email_config()`, `get_platform_config()` |
| `lib.email_client` | `create_email()`, `poll_code()`, `TempEmail` |
| `lib.browser` | `browser_session()` 上下文, `dismiss_cookie()` |
| `lib.captcha` | `click_hcaptcha_checkbox()`, `poll_hcaptcha_token()` |

## 代码风格

- 所有函数带类型注释
- Python >= 3.11 语法
- 用 `from __future__ import annotations` 推迟求值
- 中文注释和日志

## 配置约定

- 共享配置放 `[email]` 段
- 平台专属配置放 `[platforms.<目录名>]` 段
- 目录名用下划线 (`nvidia_nim`), CLI 名用连字符 (`nvidia-nim`)