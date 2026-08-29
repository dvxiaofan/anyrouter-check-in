#!/usr/bin/env bash
# 把 skills/anyrouter-checkin 安装到本机各 AI agent 的 skills 目录。
# 跟随现有惯例：实体副本，不用软链（三家现有 skill 都是副本）。
# 重复执行 = 覆盖更新。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/anyrouter-checkin"
[ -d "$SRC" ] || { echo "❌ 找不到 $SRC"; exit 1; }

TARGETS=(
	"$HOME/.claude/skills"    # Claude Code
	"$HOME/.openclaw/skills"  # openclaw（小虾米）
	"$HOME/.hermes/skills"    # Hermes（晓伊）
)

for base in "${TARGETS[@]}"; do
	agent="$(basename "$(dirname "$base")")"
	if [ ! -d "$base" ]; then
		echo "  ⏭️  $agent: $base 不存在，跳过"
		continue
	fi
	dst="$base/anyrouter-checkin"
	mkdir -p "$dst"
	cp -f "$SRC/SKILL.md" "$dst/SKILL.md"
	echo "  ✅ $agent → $dst"
done

echo
echo "已安装。openclaw / Hermes 可能需要重启或重载 skill 索引才能看到。"
