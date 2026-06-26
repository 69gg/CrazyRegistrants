# CrazyRegistrants - 疯狂注册人

注册机大合集，多平台 API Key / 账号自动注册。

## 快速开始

```bash
# 安装依赖
uv sync
uv run playwright install chromium

# 复制并编辑配置
cp config.toml.example config.toml
# 编辑 config.toml 填入你的邮箱服务信息

# 注册
uv run python main.py nvidia-nim -n 1
```

## 前置条件

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- 自建 [Cloudflare Temp Email](https://github.com/dreamhunter2333/cloudflare_temp_email) 临时邮箱服务
- 协议路径平台（如 agnes-ai）: 纯 HTTP, 无需图形界面、无需解验证码
- 浏览器路径平台（如 nvidia-nim）: 需有图形界面的环境（Playwright 看浏览器窗口手动解 hCaptcha）
- 可选: 内置 Turnstile 求解配置（`[turnstile]`，基于 Playwright）

## 支持的平台

| 平台 | 命令 | 说明 | 路径 |
|------|------|------|------|
| [Agnes AI](./platforms/agnes_ai/README.md) | `agnes-ai` | platform.agnes-ai.com API Key 注册 | 纯协议 |
| [NVIDIA NIM](./platforms/nvidia_nim/README.md) | `nvidia-nim` | build.nvidia.com API Key 注册 | 浏览器 |

## 通用参数

所有平台均支持:

```bash
-n N    # 注册 N 个账号 (N=0 表示无限注册, 直到 Ctrl-C)
-w W    # W 进程并行
```

## 目录结构

```
CrazyRegistrants/
├── main.py                 # CLI 入口
├── config.toml.example     # 配置模板
├── lib/                    # 可复用模块
│   ├── base.py             # 注册机基类 (支持 -n 0 无限模式)
│   ├── config.py           # 配置加载
│   ├── email_client.py     # 临时邮箱
│   ├── http_client.py      # 协议路径 JSON API 客户端 (curl_cffi)
│   ├── browser.py          # Playwright 封装
│   ├── captcha.py          # 验证码处理
│   ├── turnstile.py        # Turnstile solver 封装
│   └── utils.py            # 工具函数
├── platforms/              # 各平台注册机
│   ├── agnes_ai/           # ← 纯协议平台示例
│   └── nvidia_nim/         # ← 浏览器平台示例 (pipeline.py + README.md)
└── output/                 # 输出: output/<平台>/keys.txt + accounts.jsonl (gitignored)
```

## 如何添加新平台及开发规范

参见 [AGENTS.md](./AGENTS.md)。
