#!/bin/bash
# setup.sh — wiki-quiz-kit Initializer (Mac/Linux)
# Run once after cloning. Creates empty directory structure.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== wiki-quiz-kit Setup ==="
echo "Root: $ROOT"
echo ""

DIRS=(
    "raw/inbox" "raw/fleeting" "raw/articles" "raw/videos"
    "raw/meetings" "raw/highlights"
    "wiki/permanent" "wiki/literature" "wiki/daily" "wiki/moc"
    "questions"
    "evals/cases"
    "output"
    "temp"
    "sessions"
    "state"
)

echo "[1/3] Creating directories..."
for d in "${DIRS[@]}"; do
    mkdir -p "$ROOT/$d"
    touch "$ROOT/$d/.gitkeep"
done
echo "  Done."

echo "[2/3] Creating welcome note..."
WELCOME_DATE=$(date +%Y-%m-%d)
cat > "$ROOT/raw/inbox/welcome.md" << WELCOMEEOF
---
type: fleeting
tags: [welcome]
created: "$WELCOME_DATE"
modified: "$WELCOME_DATE"
---
# Welcome

你的第一条笔记。用 raw/inbox/ 作为捕获入口——想法先落地，分类后置。

## 如何使用这个知识库

- 用 \`/ingest <URL>\` 一键摄入视频或文章，自动生成复习题
- 用 \`/review\` 刷题复习，支持按主题筛选和错题回顾
- 用 \`/lint\` 做 LLM 语义审计，检查矛盾、过时、缺失概念
- 笔记模板在 \`templates/\` 目录
- prompts/ 目录有 9 个 LLM 编译器 prompt，可直接使用或修改

## Next
- [ ] 往 raw/inbox/ 扔你的第一个想法
- [ ] 在 Obsidian 中打开此文件夹作为 Vault
- [ ] 配置 Claude Code

> 确定性 guardrails + 概率性核心 = 可信任的知识系统
WELCOMEEOF
echo "  Done: raw/inbox/welcome.md"

echo "[3/3] Running health check..."
if command -v python3 &> /dev/null; then
    python3 "$ROOT/scripts/health-check.py" --verbose
elif command -v pwsh &> /dev/null; then
    pwsh "$ROOT/scripts/health-check.ps1" -Verbose
else
    echo "  WARNING: Neither python3 nor pwsh found. Skipping health check."
    echo "  Install Python 3 (https://python.org) or PowerShell Core (brew install powershell)."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next: Open this folder in Obsidian as a Vault"
