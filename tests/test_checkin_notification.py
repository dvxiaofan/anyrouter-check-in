"""账号块排版：整块信息（名字 + 签到前后 + 消耗 + 结论）夹在两条横线之间。"""

from checkin import RULE_LINE, format_block, format_check_in_notification


def detail(**overrides):
	d = {
		'name': 'ED',
		'before_quota': 4604.24,
		'before_used': 3070.76,
		'after_quota': 4604.24,
		'after_used': 3070.76,
		'check_in_reward': 0.0,
		'usage_increase': 0.0,
		'balance_change': 0.0,
		'success': True,
		'usage': {'since_last': (1.0, '4.0h'), 'day': (1.15, '20h')},
	}
	d.update(overrides)
	return d


def test_block_is_framed_by_two_rules():
	lines = format_check_in_notification(detail()).split('\n')
	assert lines[0] == RULE_LINE
	assert lines[-1] == RULE_LINE
	assert lines.count(RULE_LINE) == 2  # 框内不再有中间横线
	assert lines[1] == '  [CHECK-IN] ED'  # 名字进框
	assert lines[-2] == '  今日已签到，无变化'  # 结论也进框
	assert lines[2:4] == ['  签到前', '     余额: $4604.24  |  累计消耗: $3070.76']


def test_reward_and_usage_lines_stay_inside_frame():
	lines = format_check_in_notification(
		detail(check_in_reward=25.0, usage_increase=3.5, balance_change=25.0, after_quota=4629.24)
	).split('\n')
	assert lines[0] == RULE_LINE and lines[-1] == RULE_LINE and lines.count(RULE_LINE) == 2
	assert '  签到获得: +$25.00' in lines
	assert '  期间消耗: $3.50' in lines
	assert '  余额变化: +$25.00' in lines
	assert '  今日已签到，无变化' not in lines
	assert lines.index('  余额变化: +$25.00') < lines.index(RULE_LINE, 1)  # 结论在框内、底线之上


def test_usage_without_reward_says_already_checked_in():
	lines = format_check_in_notification(detail(usage_increase=1.5)).split('\n')
	assert '  今日已签到（期间有使用）' in lines
	assert '  今日已签到，无变化' not in lines


def test_adjacent_blocks_are_separated_by_two_rules():
	first = format_check_in_notification(detail()).split('\n')
	second = format_check_in_notification(detail(name='CH')).split('\n')
	assert [first[-1], second[0]] == [RULE_LINE, RULE_LINE]


def test_normal_block_is_built_by_format_block():
	lines = format_check_in_notification(detail()).split('\n')
	assert lines[1:-1] == format_block('[CHECK-IN] ED', *lines[2:-1]).split('\n')[1:-1]


def test_format_block_wraps_header_and_details():
	block = format_block('[FAIL] ED', '  Failed to get user info: HTTP 401')
	assert block.split('\n') == [
		RULE_LINE,
		'  [FAIL] ED',
		'  Failed to get user info: HTTP 401',
		RULE_LINE,
	]


def test_format_block_without_details_is_still_framed():
	assert format_block('[FAIL] CH').split('\n') == [RULE_LINE, '  [FAIL] CH', RULE_LINE]
