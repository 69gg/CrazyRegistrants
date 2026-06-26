# NVIDIA NIM

NVIDIA build.nvidia.com 自动注册获取 API Key。

## 用法

```bash
uv run python main.py nvidia-nim -n 1       # 注册 1 个
uv run python main.py nvidia-nim -n 5 -w 3  # 注册 5 个, 3 进程并行
```

## 配置

在 `config.toml` 中:

```toml
[email]
# 临时邮箱服务 (所有平台共用)
base_url = "https://your-mail.example.com"
custom_auth = "xxx"
admin_auth = "xxx"
domain = "your-domain.com"

[platforms.nvidia_nim]
# 一般不需修改
client_id = "1214762014100529152"
build_url = "https://build.nvidia.com"
```

## 流程

1. 创建临时邮箱
2. 打开浏览器访问 build.nvidia.com → 点击 "Get API Key"
3. 填入邮箱 → 跳转 NVIDIA 注册页
4. 填入密码 → **手动解 hCaptcha** → 点击 Create Account
5. 邮箱接收验证码 → 自动填入
6. 同意条款 → 创建 Cloud Account → Generate Key
7. Key 保存到 `output/nvidia_nim/keys.txt`

> **注意**: hCaptcha 需要手动在浏览器窗口中解算，脚本只负责点击 checkbox 和轮询检测完成状态。