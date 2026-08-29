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
| `Missing WAF cookies` | 过不了 WAF（IP 信誉或 cloakbrowser 指纹过时） | 先本地跑对比；本地成功=远端 IP 问题；都失败=考虑升 cloakbrowser（须本地实测） |
| `Error 1040 (08004)` | anyrouter 官方数据库连接数打满 | 等下一轮，不用管 |
| `Using SOCKS proxy... socksio` | 本地 `all_proxy` 是 socks5 | 见上方本地实跑命令 |
| `SSLV3_ALERT_HANDSHAKE_FAILURE` | 本地直连被阻断 | 挂 HTTP 代理 |
| `Message push failed! Reason: X not configured` | 该通知渠道没配 | 正常现象；至少配一个渠道即可 |
| 「今日已签到，无变化」 | 24h 内已签过 | 正常，anyrouter 是滚动 24h 不是零点重置 |

## 通知渠道

`utils/notify.py` 支持 9 种：Bark / Telegram / 飞书 / 钉钉 / 企微 / PushPlus /
Server酱 / Gotify / SMTP 邮件。未配置的会 `raise` 并在日志明确写
`Message push failed! Reason: X not configured`（**不是**静默跳过）。

**至少配一个**——否则 cookie 失效时收不到推送，只能自己想起来去翻 Actions 页。
在 GitHub Environment `production` 里加对应 secret 即可，脚本会自动跳过没配的。

## 架构要点（排查时有用）

- 两段式：CloakBrowser 拿阿里云 WAF cookie（`acw_tc`/`cdn_sec_tc`/`acw_sc__v2`）
  → 交给 `httpx`（HTTP/2）打 `/api/user/sign_in`
- `anyrouter.top` 前面是 Cloudflare（`104.17.x.x`），后面是阿里云 WAF（`server: ESA`，
  返回混淆 JS 挑战）。**裸 HTTP 请求拿不到 API，必须走浏览器**
- 余额 SHA256 hash 存 Actions cache 去重：只有余额变化或失败才推通知
- `permissions: contents: read`；`keepalive` job 单独 `actions: write`
- 所有 `actions/*` 已 SHA pin
