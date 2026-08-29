---
name: anyrouter-checkin
description: >
  管理 AnyRouter 自动签到服务（GitHub Actions，仓库 dvxiaofan/anyrouter-check-in）。
  能力：检查各账号 session cookie 还有几天过期、新增/更新多账号配置、把本地 .env
  同步到 GitHub Environment secret、查看线上运行结果、排查签到失败。
  当用户提到"anyrouter"、"签到"、"续期 cookie"、"加个账号"、"签到失败"、
  "额度没涨"、"check-in" 时触发。
  ⚠️ 绝不把 session/password 的值打印到对话或日志里，一律用 scripts/accounts.py。
metadata:
  openclaw:
    emoji: "🎫"
    os: ["darwin"]
    requires:
      bins: ["uv", "gh", "git"]
  clawdbot:
    emoji: "🎫"
    os: ["darwin"]
    requires:
      bins: ["uv", "gh", "git"]
---

# AnyRouter 自动签到运维

管理一个跑在 GitHub Actions 上的 AnyRouter 多账号每日签到服务。

| | |
|---|---|
| 本地仓库 | `/Users/ccfun/Documents/claudecode/anyrouter-check-in` |
| GitHub | `dvxiaofan/anyrouter-check-in`（public，已脱离上游自维护） |
| 运行频率 | 每 6 小时（`cron: 0 */6 * * *`），另可手动触发 |
| 认证方式 | session cookie（**刻意不用**明文密码） |

## ⚠️ 四条硬规则

1. **绝不打印 session / password 的值**到对话、日志或 commit。所有操作走
   `scripts/accounts.py`，它只输出账号数、api_user、认证方式和 cookie 寿命。
2. **绝不让用户把 session 粘进对话**。让他们直接编辑 `.env` 文件，或在 GitHub 网页填。
   已经粘过的，提醒去 anyrouter 重新登录换掉。
3. **绝不在这个仓库开 `DEBUG_MODE`**。它是 public 仓库，debug 会把 full_page 的
   已登录 console 页截图传成任何人可下载的 artifact。调试只在本地跑。
4. **不要同步上游**，也**不要主动升 `cloakbrowser`**（钉死 0.3.31）。理由见仓库 README。

## 配置在哪（最容易搞错的地方）

**两个位置，作用完全不同：**

| 位置 | 谁读它 | 改了会怎样 |
|---|---|---|
| GitHub → Settings → Environments → `production` → secret `ANYROUTER_ACCOUNTS` | **GitHub Actions（真正跑签到的）** | 线上生效 |
| 本地 `.env` 的 `ANYROUTER_ACCOUNTS=` 行 | 只有本地 `uv run checkin.py` | **线上不受影响** |

**只改 `.env` 不会影响线上签到。** 必须再跑 `accounts.py push` 同步过去。

### 账号 JSON 格式

必须是**单行** JSON 数组（python-dotenv 不吃多行）：

```json
[{"name":"号1","cookies":{"session":"xxx"},"api_user":"15394"},{"name":"号2","cookies":{"session":"yyy"},"api_user":"23456"}]
```

- `session`：anyrouter 网站 F12 → Application → Cookies → `session`，约 30 天失效
- `api_user`：F12 → Network → 筛 Fetch/XHR → 请求头 `New-Api-User`，正常 5 位数。
  **cookie 模式下必填**（负数或个位数说明取的时候没登录）
- `name`：**会打进公开的 Actions 日志**，别用邮箱前缀等可识别身份的名字；不填默认 `Account N`

## 常用命令

全部在仓库根目录执行。

```bash
cd /Users/ccfun/Documents/claudecode/anyrouter-check-in

uv run scripts/accounts.py check          # 校验 .env + 列出每个账号 cookie 还剩几天
uv run scripts/accounts.py push           # 把 .env 的配置推到 GitHub secret
uv run scripts/accounts.py remote-status  # 远端 environment/secret/workflow 是否就绪
uv run scripts/accounts.py runs           # 最近几次线上运行结果
```

### 本地实跑签到（验证用）

**必须处理代理**，否则会出现很有迷惑性的假象：

```bash
env -u ALL_PROXY -u all_proxy \
    HTTP_PROXY=http://127.0.0.1:7893 HTTPS_PROXY=http://127.0.0.1:7893 \
    uv run checkin.py
```

原因：境内直连 `anyrouter.top` TLS 握手失败，但 CloakBrowser 支持 ECH 能直连成功
→ 表现为「拿到 3 个 WAF cookie 但后续 httpx 全挂」，看起来像 WAF 问题其实是网络问题。
另外 httpx `trust_env=True` 会捡 `all_proxy` 的 socks5 地址，报缺 `socksio`。

GitHub runner 在境外且无这些环境变量，**线上不受影响，无需任何代理配置**。

## 任务手册

### 新增一个账号

1. 让用户在 anyrouter 登录目标账号，F12 取 `session` 和 `New-Api-User`
2. 让用户**自己编辑** `.env`，往 `ANYROUTER_ACCOUNTS` 的数组里加一个对象（保持单行）
3. `uv run scripts/accounts.py check` — 确认 JSON 合法、新账号出现、cookie 寿命正常
4. `uv run scripts/accounts.py push` — 同步到线上
5. 可选：本地实跑一次验证新账号能签到

### 每月轮换 cookie（例行）

1. `uv run scripts/accounts.py check` — 看谁快过期了（剩余 ≤5 天会标 ⚠️）
2. 让用户重新登录对应账号取新 `session`，编辑 `.env` 替换
3. `check` 确认剩余天数变回 ~30 天
4. `push` 同步
5. `runs` 确认下一次运行成功

### 例行体检

```bash
uv run scripts/accounts.py check && uv run scripts/accounts.py remote-status && uv run scripts/accounts.py runs
```

三条都绿就没事。另外**每约 2 个月**确认一次 workflow 仍是 `active`
（public 仓库 60 天无活动会被 GitHub 自动禁用 scheduled workflow；仓库里的
`keepalive` job 会抢先 re-enable，但该规则的判定语义 GitHub 未公开文档化）。

## 故障速查

| 日志现象 | 含义 | 处理 |
|---|---|---|
| `HTTP 401` | session 过期 | 换 cookie，走「每月轮换」流程 |
| **本地** `HTTP 403` + `server: ESA` | **不是真故障**：WAF 把 `acw_sc__v2` 绑定到取它时的客户端 IP。浏览器和 httpx 走了不同出口（Clash 切节点），IP 对不上 | **别据此判断账号有问题**。线上 runner 单一 IP 无代理不会有这问题——直接看线上 `runs` 结果为准 |
| `Missing WAF cookies` | 过不了 WAF（IP 信誉或 cloakbrowser 指纹过时） | 先看线上是否也失败；只有线上也挂才考虑升 cloakbrowser（须实测） |
| `Error 1040 (08004)` | anyrouter 官方数据库连接数打满 | 等下一轮，不用管 |
| `Using SOCKS proxy... socksio` | 本地 `all_proxy` 是 socks5 | 见上方本地实跑命令 |
| `SSLV3_ALERT_HANDSHAKE_FAILURE` | 本地直连被阻断 | 挂 HTTP 代理 |
| 「今日已签到，无变化」 | 24h 内已签过 | 正常，anyrouter 是滚动 24h 不是零点重置 |

> **本地验证的可信度有限**：受代理出口 IP 影响，本地 403/成功都不能直接推断线上。
> 想确认线上状态，用 `accounts.py runs` 看真实运行结果，或
> `gh workflow run checkin.yml --repo dvxiaofan/anyrouter-check-in` 触发一次。

## 通知渠道

`utils/notify.py` 支持 9 种：Bark / Telegram / 飞书 / 钉钉 / 企微 / PushPlus /
Server酱 / Gotify / SMTP 邮件。未配置的会 `raise` 并在日志明确写
`Message push failed! Reason: X not configured`（**不是**静默跳过）。

**当前已配 Telegram**（bot `@cc_any_bot`，secret `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`）。
`checkin.yml` 里只保留了 Telegram 两个 env——未配置的渠道每轮都会打一行
「Message push failed」把真正的失败淹掉，所以不用的渠道不要留在 workflow 里。

要换/加渠道：在 GitHub Environment `production` 加对应 secret，**并且**在
`checkin.yml` 的「执行签到」步骤 env 里补上同名条目，两边都要动。

新配 Telegram 机器人时，`TELEGRAM_CHAT_ID` 只能从「用户已给该 bot 发过消息」
的记录里取：让用户先给 bot 发 `/start`，再
`curl -x http://127.0.0.1:7893 "https://api.telegram.org/bot<TOKEN>/getUpdates"`
从 `result[].message.chat.id` 读。

## 架构要点（排查时有用）

- 两段式：CloakBrowser 拿阿里云 WAF cookie（`acw_tc`/`cdn_sec_tc`/`acw_sc__v2`）
  → 交给 `httpx`（HTTP/2）打 `/api/user/sign_in`
- `anyrouter.top` 前面是 Cloudflare（`104.17.x.x`），后面是阿里云 WAF（`server: ESA`，
  返回混淆 JS 挑战）。**裸 HTTP 请求拿不到 API，必须走浏览器**
- 余额 SHA256 hash 存 Actions cache 去重：只有余额变化或失败才推通知
- `permissions: contents: read`；`keepalive` job 单独 `actions: write`
- 所有 `actions/*` 已 SHA pin
