#!/usr/bin/env python3
"""wiki-quiz-kit initializer — creates directories, welcome note, health check."""

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DIRS = [
    "raw/inbox", "raw/fleeting", "raw/articles", "raw/videos",
    "raw/meetings", "raw/highlights",
    "wiki/permanent", "wiki/literature", "wiki/daily", "wiki/moc",
    "questions", "evals/cases",
    "output", "temp", "sessions", "state",
]

print("=== wiki-quiz-kit Setup ===")
print(f"Root: {ROOT}")
print()

print("[1/3] Creating directories...")
for d in DIRS:
    (ROOT / d).mkdir(parents=True, exist_ok=True)
    (ROOT / d / ".gitkeep").touch()
print("  Done.")
print()

print("[2/3] Creating welcome note...")
today = date.today().isoformat()
welcome = ROOT / "raw" / "inbox" / "welcome.md"
welcome.write_text(f"""---
type: fleeting
tags: [welcome]
created: "{today}"
modified: "{today}"
---
# Welcome

你的第一条笔记。用 raw/inbox/ 作为捕获入口——想法先落地，分类后置。

## 如何使用这个知识库

- 用 `/ingest <URL>` 一键摄入视频或文章，自动生成复习题
- 用 `/review` 刷题复习，支持按主题筛选和错题回顾
- 用 `/lint` 做 LLM 语义审计，检查矛盾、过时、缺失概念
- 笔记模板在 `templates/` 目录
- prompts/ 目录有 9 个 LLM 编译器 prompt，可直接使用或修改

## Next
- [ ] 往 raw/inbox/ 扔你的第一个想法
- [ ] 在 Obsidian 中打开此文件夹作为 Vault
- [ ] 配置 Claude Code

> 确定性 guardrails + 概率性核心 = 可信任的知识系统
""", encoding="utf-8")
print("  Done: raw/inbox/welcome.md")
print()

print("[3/3] Running health check...")
result = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "health-check.py"), "--verbose"]
)
print()
print("=== Setup Complete ===")
print()
print("Next: Open this folder in Obsidian as a Vault")
