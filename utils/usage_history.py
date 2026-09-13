"""跨运行的消耗记录：每次签到后把各账号的 (时间, 余额, 累计消耗) 追加到 JSON，
下次运行据此算「距上次消耗」和「近 24h 消耗」。文件由 GitHub Actions cache 跨 run 保存。

消耗一律用 used_quota（累计消耗，只增不减）的差值，不用余额差——余额会被签到奖励抬高。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

HISTORY_FILE = Path(os.getenv('USAGE_HISTORY_FILE', 'usage_history.json'))
KEEP_DAYS = 7
DAY_WINDOW = (timedelta(hours=20), timedelta(hours=30))  # 「近 24h」基线允许的实际跨度


def _parse(ts: str) -> datetime:
	return datetime.fromisoformat(ts)


def load_history(path: Path = HISTORY_FILE) -> dict:
	"""{api_user: [{"t": iso, "quota": float, "used": float}, ...]}，按时间升序。损坏则当空。"""
	try:
		data = json.loads(path.read_text(encoding='utf-8'))
		return data if isinstance(data, dict) else {}
	except (OSError, ValueError):
		return {}


def save_history(history: dict, path: Path = HISTORY_FILE) -> None:
	tmp = path.with_suffix('.tmp')
	tmp.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding='utf-8')
	tmp.replace(path)


def _fmt_hours(delta: timedelta) -> str:
	h = delta.total_seconds() / 3600
	return f'{h:.0f}h' if h >= 10 else f'{h:.1f}h'


def compute_usage(records: list[dict], now: datetime, used_now: float) -> dict:
	"""返回 {"since_last": (amount, span_str) | None, "day": (amount, span_str) | None}。
	records 是该账号历史（不含本次）。没有基线就给 None，不硬算。"""
	out = {'since_last': None, 'day': None}
	if not records:
		return out
	last = records[-1]
	out['since_last'] = (round(used_now - float(last['used']), 2), _fmt_hours(now - _parse(last['t'])))

	target = now - timedelta(hours=24)
	candidates = [r for r in records if DAY_WINDOW[0] <= now - _parse(r['t']) <= DAY_WINDOW[1]]
	if candidates:
		base = min(candidates, key=lambda r: abs(_parse(r['t']) - target))
		out['day'] = (round(used_now - float(base['used']), 2), _fmt_hours(now - _parse(base['t'])))
	return out


def record_and_compute(history: dict, key: str, now: datetime, quota: float, used: float) -> dict:
	"""先用旧记录算差值，再把本次追加进去并裁剪到 KEEP_DAYS。"""
	records = history.get(key, [])
	result = compute_usage(records, now, used)
	records.append({'t': now.isoformat(timespec='seconds'), 'quota': quota, 'used': used})
	cutoff = now - timedelta(days=KEEP_DAYS)
	history[key] = [r for r in records if _parse(r['t']) >= cutoff]
	return result


def format_usage_lines(usage: dict | None) -> list[str]:
	"""通知里的两行。无基线显示 —。"""
	if not usage:
		return ['  距上次消耗: —', '  近24h消耗: —']

	def one(label: str, item):
		if item is None:
			return f'  {label}: —'
		amount, span = item
		return f'  {label}: ${amount:.2f}（{span}）'

	return [one('距上次消耗', usage['since_last']), one('近24h消耗', usage['day'])]


def now_local() -> datetime:
	"""带时区的当前时间，跨 runner 时区也能算对间隔。"""
	return datetime.now().astimezone()
