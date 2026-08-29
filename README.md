# anyrouter-check-in（自维护分支）

AnyRouter 每日自动签到，跑在 GitHub Actions 上，每 6 小时一轮。

Fork 自 [millylee/anyrouter-check-in](https://github.com/millylee/anyrouter-check-in)（BSD-2-Clause）。
**本仓库已脱离上游自行维护，不再同步。** 改动详见文末「与上游的差异」。

---

## ⚠️ 三条硬约定

1. **绝不在本仓库开 `DEBUG_MODE`。**
   本仓库是 public。debug 会把 `full_page` 的**已登录 console 页截图**传成 artifact，
   而 public 仓库的 artifact **任何人都能下载**（含邮箱、用户 ID、余额，可能还有 API Key）。
   要调试就在本地跑，截图落 `checkin_screenshots/`，已被 `.gitignore` 覆盖。

2. **必须至少配一个通知渠道。**
   一个都不配时，运行日志会明确列出 `[Bark]: Message push failed! Reason: Bark Key not configured`
   （`utils/notify.py` 里未配置的渠道会 `raise`，不是静默跳过），但**你收不到任何推送**——
   session 失效时得自己想起来去翻 Actions 页才会发现。配一个就能被动收告警。

3. **不主动升 `cloakbrowser`。** 见下方「冻结策略」。

---

## 配置

### GitHub 侧（一次性）

1. Actions 标签页 → 点 "I understand my workflows, go ahead and enable them"
   （fork 的 workflow 默认冻结，**只能网页点，没有 API**）

2. Settings → Environments → New environment，命名 **`production`**（名字写死在 workflow 里）

3. 该环境下 → Deployment branches → **Selected branches → 只填 `main`**
   这样其它分支读不到 secret。此规则在 public 仓库免费可用，private 仓库需要 Pro。

4. 添加 Environment secrets：

   | Secret | 必填 | 内容 |
   |---|---|---|
   | `ANYROUTER_ACCOUNTS` | ✅ | 见下 |
   | 任一通知渠道 | ✅ | 如 `BARK_KEY` / `TELEGRAM_BOT_TOKEN`+`TELEGRAM_CHAT_ID` / `FEISHU_WEBHOOK` |

   `ANYROUTER_ACCOUNTS`（**单行** JSON 数组）：

   ```json
   [{"cookies":{"session":"你的session值"},"api_user":"你的api_user"}]
   ```

   - `session`：登录 https://anyrouter.top/ 后 F12 → Application → Cookies → `session`，约 1 个月失效

     ![取 session](./assets/request-session.png)

   - `api_user`：F12 → Network → 筛 Fetch/XHR → 找请求头 `New-Api-User`，正常是 5 位数
     （若是负数或个位数说明当时未登录）。**cookie 模式下此字段必填**

     ![取 api_user](./assets/request-api-user.png)

### 取值方式说明

本仓库刻意**不用** `email` + `password` 方式。密码一旦泄漏等于账号完全失守；
session cookie 泄漏则只暴露一个约 1 个月有效期的会话，拿不到密码、改不了账号。
代价是每月要手动轮换一次。

---

## 本地调试

```bash
uv sync --dev
uv run python -m cloakbrowser install     # 运行时下载浏览器二进制

cat > .env <<'EOF'
ANYROUTER_ACCOUNTS=[{"cookies":{"session":"..."},"api_user":"..."}]
DEBUG_MODE=true
EOF

uv run checkin.py
uv run pytest tests/
```

### ⚠️ 国内本地跑必须处理代理（2026-08-29 实测）

从境内直连 `anyrouter.top` **TLS 握手会失败**（curl exit 35）。但 CloakBrowser 能直连成功
（Chromium 支持 ECH，可绕开基于 SNI 的阻断），所以表现是「拿到了 WAF cookie，
但后续 httpx 请求全挂」，很有迷惑性。

同时 httpx 默认 `trust_env=True` 会捡走 `all_proxy`。如果你的 shell profile 里
`all_proxy=socks5://...`，会报 `Using SOCKS proxy, but the 'socksio' package is not installed`。

正确跑法——清掉 socks、保留 HTTP 代理：

```bash
env -u ALL_PROXY -u all_proxy \
    HTTP_PROXY=http://127.0.0.1:7893 HTTPS_PROXY=http://127.0.0.1:7893 \
    uv run checkin.py
```

GitHub runner 在境外且不带这些环境变量，**不受此影响**，无需任何代理配置。

本地开 `DEBUG_MODE=true` 是安全的——截图只落在本机且已 gitignore。

跑通的日志特征：

```
[AUTH] Account 1: Using auth method -> session cookies
[INFO] Account 1: Got 3 WAF cookies          # anyrouter 需 acw_tc / cdn_sec_tc / acw_sc__v2
Current balance: $X, Used: $Y
[SUCCESS] Account 1: Check-in successful!    # 或 Already checked in today
```

---

## 月度维护

| 周期 | 事项 |
|---|---|
| 每月 | 轮换 `session` cookie（约 1 个月失效；上游 issue #6 记录了会提前失效，表现为 401） |
| 每季度 | 瞄一眼 Actions 是否还在跑；`cloakbrowser` **只在 WAF 开始失败时才动** |
| 约 2 个月 | 确认 workflow 没被自动禁用（keepalive 应该已经挡住了，但值得抽查） |

### 故障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| HTTP 401 | session 过期 | 重新取 cookie，更新 secret |
| `Missing WAF cookies` | WAF 策略变了 / cloakbrowser 指纹过时 | 考虑升 `cloakbrowser`，须本地实测 |
| `Error 1040 (08004)` | 官方数据库连接数打满 | 等，上游 issue #7 |
| 定时任务不跑了 | 60 天无活动被自动禁用 | 见下方「冻结策略」 |

---

## 冻结策略

本仓库**刻意不同步上游**。相关事实：

- 上游 main 最后提交 **2026-06-23**，此后仅在非 main 分支有推送
- `cloakbrowser` 钉死在 **0.3.31（2026-05-26）**，PyPI 当前已到 0.5.9，中间隔 31 个版本
- `pyproject.toml` 用 `==` 而非 `>=` 写明这个意图；`uv.lock` 与之一致，CI 走 `uv sync --frozen`

`cloakbrowser` 是反 bot 检测的军备竞赛型依赖，**冻结意味着 WAF 升级时它会先失效**。
处理原则：**出现失败再升，且必须先本地实测**，不要为了"保持最新"主动跳版本——
跨 31 个版本 API 大概率不兼容。

### 60 天自动禁用

GitHub 官方规则：

> In a public repository, scheduled workflows are automatically disabled
> when no repository activity has occurred in 60 days.

冻结不提交必然踩到。`checkin.yml` 里的 `keepalive` job 会在每次**定时**运行时
调 `PUT /actions/workflows/checkin.yml/enable` 抢先把自己重新启用。

选这个做法而非"推空 commit"，是因为它不污染提交历史、不需要 `contents:write`、
也不引入第三方 action（社区最流行的那个 keepalive action 仓库已被 GitHub 以 ToS 封禁）。

该机制依赖的 60 天判定语义 GitHub 未公开文档化，所以**头两个月请抽查一次**
Actions 页面确认 workflow 仍是启用状态。

---

## 与上游的差异

| 改动 | 原因 |
|---|---|
| `permissions: contents: read` | 上游未声明。最小权限，且不受仓库默认值变动影响 |
| 4 个 `actions/*` 全部 SHA pin | 上游用可移动的 tag（`astral-sh/setup-uv` 上游本就是 SHA） |
| 删除「配置代理 / 停止代理」两步 | 只签 anyrouter，其 `use_proxy=false`；顺带去掉运行时下载 mihomo 二进制的供应链面 |
| debug artifact 保留期 14 → 1 天 | public 仓库下 artifact 公开可下载 |
| 新增 `keepalive` job | 防 60 天自动禁用 |
| 删除 `.github/workflows/pr-check.yml` | 自用仓库不会收 PR；它引用 `CODECOV_TOKEN` 并用 `github-script` 写 PR 评论 |
| `cloakbrowser` `>=0.3.0` → `==0.3.31` | 写明冻结意图 |
| README 重写 | 去掉上游的注册推广链接，改成自维护运维文档 |

保留但当前走不到的：`xvfb` + 字体安装 + `CHECKIN_HEADLESS`。
cookie 模式下 `checkin.py` 取 WAF cookie 时硬编码 `headless=True`，这些用不上，
保留是为了 cookie 失效时能临时切回 email/password 登录应急。
