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
- 有图形界面的环境（Playwright 需要看浏览器窗口手动解 hCaptcha）

## 支持的平台

| 平台 | 命令 | 说明 |
|------|------|------|
| [NVIDIA NIM](./platforms/nvidia_nim/README.md) | `nvidia-nim` | build.nvidia.com API Key 注册 |

## 目录结构

```
CrazyRegistrants/
├── main.py                 # CLI 入口
├── config.toml.example     # 配置模板
├── lib/                    # 可复用模块
│   ├── base.py             # 注册机基类
│   ├── config.py           # 配置加载
│   ├── email_client.py     # 临时邮箱
│   ├── browser.py          # Playwright 封装
│   ├── captcha.py          # 验证码处理
│   └── utils.py            # 工具函数
├── platforms/              # 各平台注册机
│   └── nvidia_nim/         # ← 平台目录, 内有 pipeline.py + README.md
└── data/keys/              # 输出: API Key (gitignored)
```

## 如何添加新平台及开发规范

参见 [AGENTS.md](./AGENTS.md)。
