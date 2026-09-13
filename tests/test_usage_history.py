from datetime import datetime, timedelta, timezone

from utils.usage_history import compute_usage, format_usage_lines, load_history, record_and_compute, save_history

TZ = timezone(timedelta(hours=8))
T0 = datetime(2026, 9, 13, 9, 0, tzinfo=TZ)


def rec(hours_ago, used, quota=100.0):
	return {'t': (T0 - timedelta(hours=hours_ago)).isoformat(timespec='seconds'), 'quota': quota, 'used': used}


def test_no_history_gives_none():
	assert compute_usage([], T0, 50.0) == {'since_last': None, 'day': None}
	assert format_usage_lines(None) == ['  距上次消耗: —', '  近24h消耗: —']


def test_since_last_and_nearest_24h():
	records = [rec(28, 10.0), rec(24.5, 12.0), rec(20, 15.0), rec(4, 18.0)]
	u = compute_usage(records, T0, 20.0)
	assert u['since_last'] == (2.0, '4.0h')
	assert u['day'] == (8.0, '24h')  # 取最接近 24h 的那条（24.5h 那条），≥10h 显示整数小时
	lines = format_usage_lines(u)
	assert lines[0] == '  距上次消耗: $2.00（4.0h）' and lines[1] == '  近24h消耗: $8.00（24h）'


def test_day_baseline_missing_when_gap_too_large():
	u = compute_usage([rec(40, 1.0), rec(4, 5.0)], T0, 6.0)
	assert u['since_last'] == (1.0, '4.0h') and u['day'] is None


def test_record_trims_and_roundtrips(tmp_path):
	h = {'15394': [rec(24 * 8, 1.0), rec(4, 5.0)]}
	u = record_and_compute(h, '15394', T0, 99.0, 7.0)
	assert u['since_last'] == (2.0, '4.0h')
	assert len(h['15394']) == 2 and h['15394'][-1]['used'] == 7.0  # 8 天前的被裁掉，本次已追加
	p = tmp_path / 'u.json'
	save_history(h, p)
	assert load_history(p) == h
	assert load_history(tmp_path / 'missing.json') == {}
	(tmp_path / 'bad.json').write_text('{oops', encoding='utf-8')
	assert load_history(tmp_path / 'bad.json') == {}
