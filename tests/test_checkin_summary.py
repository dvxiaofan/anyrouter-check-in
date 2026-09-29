"""通知汇总里的合计行：[BALANCE] 账号总余额 / [USAGE] 累计总消耗。"""

from checkin import format_totals_lines


def test_no_balance_data_gives_no_lines():
	assert format_totals_lines({'quota': 0.0, 'used': 0.0, 'n': 0}, 4) == []


def test_totals_lines_include_amounts_and_account_count():
	lines = format_totals_lines({'quota': 12771.16, 'used': 12299.84, 'n': 4}, 4)
	assert lines == [
		'[BALANCE] 账号总余额: $12771.16（4/4 账号）',
		'[USAGE] 累计总消耗: $12299.84（4/4 账号）',
	]


def test_partial_data_reports_partial_account_count():
	lines = format_totals_lines({'quota': 4580.39, 'used': 3069.61, 'n': 1}, 4)
	assert lines == [
		'[BALANCE] 账号总余额: $4580.39（1/4 账号）',
		'[USAGE] 累计总消耗: $3069.61（1/4 账号）',
	]
