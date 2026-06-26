# Agnes AI

[platform.agnes-ai.com](https://platform.agnes-ai.com) 自动注册获取 API Key。

**纯协议实现**: 直接调用后端 JSON API, 无需浏览器、无人机验证, 速度快 (单账号约 8 秒)。

## 用法

```bash
uv run python main.py agnes-ai -n 1        # 注册 1 个
uv run python main.py agnes-ai -n 5 -w 3   # 注册 5 个, 3 进程并行
uv run python main.py agnes-ai -n 0 -w 4   # 无限注册 (Ctrl-C 停止), 4 进程并行
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

[platforms.agnes_ai]
# 一般不需修改
api_base = "https://platform-backend.agnes-ai.com"
key_name = "default"
key_profile = "default"   # default=个人免费 / enterprise=企业
```

## 流程

1. 创建临时邮箱
2. `GET /api/verification?email=<邮箱>&purpose=register` 发送验证码
3. 邮箱接收 6 位验证码
4. `POST /api/user/register` 提交注册, 响应直接返回 `access_token`
5. `POST /api/token` 创建 API Key, 响应返回完整 `sk-...` 密钥
6. 保存:
   - `output/agnes_ai/keys.txt` — 一行一个 key
   - `output/agnes_ai/accounts.jsonl` — 完整账号 `{email, password, access_token, key, created_at}`, 可二次登录复用

## 接口速查

| 步骤 | 请求 | 鉴权 | 关键响应字段 |
|------|------|------|-------------|
| 发送验证码 | `GET /api/verification?email=&purpose=register` | 无 | `data.email` |
| 注册 | `POST /api/user/register` `{email,password,password_confirm,code}` | 无 | `data.access_token` |
| 创建密钥 | `POST /api/token` `{name,api_key_profile}` | `Bearer <token>` | `data.key` (`sk-...`) |

- 统一响应信封: `{"code":200,"message":"ok","data":{...}}`
- 鉴权走 `Authorization: Bearer <token>` 头 (非 cookie)；`access_token` 有效期约 28 天
- default 档每账号最多创建 20 个密钥

## 使用生成的 Key

Agnes 提供 OpenAI 兼容网关, Base URL 为 `https://apihub.agnes-ai.com/v1`:

```bash
curl https://apihub.agnes-ai.com/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"Hello!"}]}'
```
