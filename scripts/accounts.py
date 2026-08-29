#!/usr/bin/env python3
"""AnyRouter 签到账号配置管理。

绝不打印 session / password 的值——只输出账号数量、api_user、认证方式、
cookie 签发时间与剩余寿命。

用法:
    uv run scripts/accounts.py check          # 校验 .env 并列出各账号 cookie 寿命
    uv run scripts/accounts.py push           # 把 .env 的账号配置推到 GitHub secret
    uv run scripts/accounts.py runs           # 看最近几次线上运行结果
    uv run scripts/accounts.py remote-status  # 看远端配置是否就绪
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess  # nosec B404
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = os.getenv('CHECKIN_REPO', 'dvxiaofan/anyrouter-check-in')
ENVIRONMENT = os.getenv('CHECKIN_ENVIRONMENT', 'production')
SECRET_NAME = 'ANYROUTER_ACCOUNTS'
ENV_FILE = Path(__file__).resolve().parent.parent / '.env'

# anyrouter 的 session 实测约 30 天有效期（上游 issue #6 记录了会提前失效）
ASSUMED_VALID_DAYS = 30
WARN_DAYS = 5

# 访问 github.com 需要代理；socks5 的 all_proxy 会让 httpx/gh 出问题，只留 HTTP 代理
PROXY = os.getenv('CHECKIN_HTTP_PROXY', 'http://127.0.0.1:7893')


def _gh_env() -> dict:
	env = {k: v for k, v in os.environ.items() if k.lower() not in ('all_proxy',)}
	env['HTTPS_PROXY'] = env['HTTP_PROXY'] = PROXY
	return env


def _gh(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
	return subprocess.run(  # nosec B603
		['gh', *args],
		input=stdin,
		capture_output=True,
		text=True,
		env=_gh_env(),
		timeout=60,
	)


def read_accounts_raw() -> str:
	if not ENV_FILE.exists():
		sys.exit(f'❌ 找不到 {ENV_FILE}')
	for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
		if line.startswith(f'{SECRET_NAME}='):
			value = line.split('=', 1)[1].strip()
			if value:
				return value
	sys.exit(f'❌ {ENV_FILE} 里没有 {SECRET_NAME}')


def session_lifetime(session: str) -> tuple[datetime, int] | None:
	"""解析 gorilla/sessions 的签发时间戳，返回 (签发时间, 剩余天数)。

	只解码前 16 个字符即可拿到「时间戳|」前缀——整串解码不可靠：gorilla 用的是
	URL-safe base64，HMAC 段可能含 `-` / `_`，标准 b64decode 会因丢弃这些字符
	导致长度不是 4 的倍数而报错。
	"""
	try:
		head = base64.urlsafe_b64decode(session[:16]).decode('latin1')
	except Exception:
		return None
	m = re.match(r'(\d{9,11})\|', head)
	if not m:
		return None
	try:
		issued = datetime.fromtimestamp(int(m.group(1)))
	except (ValueError, OSError, OverflowError):
		return None
	expires = issued + timedelta(days=ASSUMED_VALID_DAYS)
	return issued, (expires - datetime.now()).days


def validate(raw: str) -> list[dict]:
	try:
		accounts = json.loads(raw)
	except json.JSONDecodeError as e:
		sys.exit(f'❌ JSON 解析失败: {e}\n   常见原因: 末尾多余逗号 / 用了单引号 / 值里有换行')
	if not isinstance(accounts, list) or not accounts:
		sys.exit('❌ 必须是非空的 JSON 数组')

	problems = []
	for i, acc in enumerate(accounts, 1):
		if not isinstance(acc, dict):
			problems.append(f'账号 {i}: 不是对象')
			continue
		has_cookie = bool((acc.get('cookies') or {}).get('session'))
		has_login = bool(acc.get('email') and acc.get('password'))
		if not has_cookie and not has_login:
			problems.append(f'账号 {i}: 既没有 cookies.session 也没有 email+password')
		if has_cookie and not has_login and not acc.get('api_user'):
			problems.append(f'账号 {i}: cookie 模式必须填 api_user')
	if problems:
		sys.exit('❌ 配置有问题:\n   ' + '\n   '.join(problems))
	return accounts


def cmd_check(_args) -> int:
	accounts = validate(read_accounts_raw())
	print(f'✅ JSON 合法，共 {len(accounts)} 个账号\n')
	worst = 999
	for i, acc in enumerate(accounts, 1):
		name = acc.get('name') or f'Account {i}'
		session = (acc.get('cookies') or {}).get('session')
		if session:
			method, extra = 'cookie', ''
			info = session_lifetime(session)
			if info:
				issued, left = info
				worst = min(worst, left)
				flag = '🔴 已过期' if left < 0 else ('⚠️ 即将过期' if left <= WARN_DAYS else '✅')
				extra = f'  签发 {issued:%Y-%m-%d}  预计剩余 {left} 天 {flag}'
			else:
				extra = '  ⚠️ 无法解析签发时间（非 gorilla 格式？）'
		else:
			method, extra = 'email/password', '  ⚠️ 明文密码，建议换 cookie'
		print(f'  [{i}] {name}')
		print(f'      api_user={acc.get("api_user") or "(邮箱登录可省略)"}  认证={method}{extra}')

	print()
	if worst < 0:
		print('🔴 有账号 cookie 已过期，去 anyrouter 重新登录取新 session')
		return 1
	if worst <= WARN_DAYS:
		print(f'⚠️ 最近的一个 {worst} 天后过期，该准备轮换了')
	return 0


def cmd_push(_args) -> int:
	raw = read_accounts_raw()
	accounts = validate(raw)
	print(f'校验通过，准备推送 {len(accounts)} 个账号到 {REPO} / environment={ENVIRONMENT}')
	r = _gh('secret', 'set', SECRET_NAME, '--env', ENVIRONMENT, '--repo', REPO, stdin=raw)
	if r.returncode != 0:
		print(f'❌ 推送失败:\n{r.stderr.strip()}')
		return 1
	print(f'✅ 已更新 secret {SECRET_NAME}（值未在任何日志中出现）')
	return 0


def cmd_remote_status(_args) -> int:
	checks = [
		('environment', ['api', f'repos/{REPO}/environments', '-q', '.environments[].name']),
		('允许的分支', ['api', f'repos/{REPO}/environments/{ENVIRONMENT}/deployment-branch-policies',
		             '-q', '[.branch_policies[].name]|join(",")']),
		('已配 secret', ['api', f'repos/{REPO}/environments/{ENVIRONMENT}/secrets',
		              '-q', '[.secrets[].name]|join(", ")']),
		('workflow 状态', ['api', f'repos/{REPO}/actions/workflows',
		                '-q', '.workflows[]|"\\(.name) = \\(.state)"']),
	]
	ok = True
	for label, args in checks:
		r = _gh(*args)
		out = r.stdout.strip() or '(空)'
		print(f'  {label:14} {out}')
		if r.returncode != 0:
			ok = False

	r = _gh('api', f'repos/{REPO}/environments/{ENVIRONMENT}/secrets', '-q', '[.secrets[].name]')
	try:
		names = json.loads(r.stdout or '[]')
	except json.JSONDecodeError:
		names = []
	notify_keys = {'BARK_KEY', 'TELEGRAM_BOT_TOKEN', 'FEISHU_WEBHOOK', 'DINGDING_WEBHOOK',
	               'WEIXIN_WEBHOOK', 'PUSHPLUS_TOKEN', 'SERVERPUSHKEY', 'GOTIFY_TOKEN', 'EMAIL_USER'}
	print()
	if SECRET_NAME not in names:
		print(f'🔴 缺 {SECRET_NAME}，签到跑不起来'); ok = False
	if not (notify_keys & set(names)):
		print('⚠️ 一个通知渠道都没配：cookie 失效时不会有推送，只能自己翻 Actions 页')
	if ok and SECRET_NAME in names:
		print('✅ 远端配置就绪')
	return 0 if ok else 1


def cmd_runs(args) -> int:
	r = _gh('run', 'list', '--repo', REPO, '--workflow', 'checkin.yml',
	        '--limit', str(args.limit), '--json', 'displayTitle,status,conclusion,createdAt,url')
	if r.returncode != 0:
		print(f'❌ {r.stderr.strip()}')
		return 1
	runs = json.loads(r.stdout or '[]')
	if not runs:
		print('还没有任何运行记录')
		return 0
	for run in runs:
		mark = {'success': '✅', 'failure': '🔴', 'cancelled': '⚪'}.get(run['conclusion'], '⏳')
		print(f"  {mark} {run['createdAt'][:16].replace('T', ' ')}  "
		      f"{run['conclusion'] or run['status']}  {run['url']}")
	return 0


def main() -> int:
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	sub = p.add_subparsers(dest='cmd', required=True)
	sub.add_parser('check', help='校验 .env 并列出各账号 cookie 剩余寿命')
	sub.add_parser('push', help='把 .env 的账号配置推送到 GitHub Environment secret')
	sub.add_parser('remote-status', help='检查远端 environment / secret / workflow 是否就绪')
	pr = sub.add_parser('runs', help='查看最近几次线上运行结果')
	pr.add_argument('--limit', type=int, default=5)
	args = p.parse_args()
	return {
		'check': cmd_check, 'push': cmd_push,
		'remote-status': cmd_remote_status, 'runs': cmd_runs,
	}[args.cmd](args)


if __name__ == '__main__':
	sys.exit(main())
