# setup.ps1 — wiki-quiz-kit Initializer
# Run once after cloning. Creates empty directory structure.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSCommandPath

Write-Host "=== wiki-quiz-kit Setup ===" -ForegroundColor Cyan
Write-Host "Root: $root"
Write-Host ""

$dirs = @(
    "raw/inbox", "raw/fleeting", "raw/articles", "raw/videos",
    "raw/meetings", "raw/highlights",
    "wiki/permanent", "wiki/literature", "wiki/daily", "wiki/moc",
    "questions",
    "evals/cases",
    "output",
    "temp",
    "sessions",
    "state"
)

Write-Host "[1/3] Creating directories..." -ForegroundColor Cyan
foreach ($d in $dirs) {
    $path = Join-Path $root $d
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    $gitkeep = Join-Path $path ".gitkeep"
    if (-not (Test-Path $gitkeep)) {
        "" | Set-Content $gitkeep -Encoding UTF8
    }
}
Write-Host "  Done."

Write-Host "[2/3] Creating welcome note..." -ForegroundColor Cyan
$welcome = @"
---
type: fleeting
tags: [welcome]
created: "$(Get-Date -Format 'yyyy-MM-dd')"
modified: "$(Get-Date -Format 'yyyy-MM-dd')"
---
# Welcome

你的第一条笔记。用 raw/inbox/ 作为捕获入口——想法先落地，分类后置。

## 如何使用这个知识库

- 运行 `.\scripts\health-check.ps1 -Verbose` 检查完整性
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
"@
$welcomePath = Join-Path $root "raw/inbox/welcome.md"
$welcome | Set-Content $welcomePath -Encoding UTF8
Write-Host "  Done: raw/inbox/welcome.md"

Write-Host "[3/3] Running health check..." -ForegroundColor Cyan
$hc = Join-Path $root "scripts/health-check.ps1"
if (Test-Path $hc) {
    & $hc -Verbose
} else {
    Write-Host "  health-check.ps1 not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Open this folder in Obsidian as a Vault"
