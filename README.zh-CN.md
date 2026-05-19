# wiki-quiz-kit

[English](README.md)

把你的笔记当成软件项目来管理：原始源文件、编译器通道、构建产物、CI 检查、自动化测试。基于 Karpathy 的 LLM Wiki 方法论。三个 Claude Code 斜杠命令驱动一切。`/ingest` 把知识拉进来，`/review` 考你记住了多少，`/lint` 做语义审计。

## 能做什么

**`/ingest`** 接收一个 URL（视频或文章），提取内容，走两步思维链管道：LLM 先分析实体、概念、论证以及与现有 wiki 的连接点，再基于分析结果生成结构化笔记。9 个 LLM prompt 模板处理不同源类型。全程只有一个确认点，其余自动完成。处理视频时优先用转录文稿（YouTube 自动字幕）。每次运行后追加 `wiki/log.md`，重新生成 `wiki/overview.md`。

**`/review`** 从题库选题，先读 `wiki/purpose.md` 了解优先级，渲染 HTML 测验页面，记录答案。做完后自动把答题结果复制到剪贴板，粘贴给 Claude 就行，它会更新每道题的状态（做过几次、对了几次、错了几次）。下次出题时，新题、薄弱点和错题的权重都不一样。答题结果记入 `wiki/log.md`。

**`/lint`** 做 `health-check.ps1` 做不到的事：LLM 驱动的语义审计。读 purpose.md，采样 wiki 页面，检查矛盾、过时声明、缺失概念、孤立群组和重复内容。结果写入 `wiki/lint-{date}.md` 并记入日志。

五种选题模式：

| 模式 | 规则 |
|------|------|
| 默认 | 40% 新题，30% 薄弱，30% 随机 |
| 新题 | 只选没做过的 |
| 错题 | 只选上次答错的 |
| 巩固 | 做过但正确率不到 80% |
| 随机 | 完全随机 |

## 架构

```
raw/ (源文件)  ──→  prompts/ (9 个编译器通道，两步 CoT)  ──→  wiki/ (构建产物)
                              ↑
                         Claude Code

questions/  ──→  .claude/skills/review/  ──→  output/ (测验 HTML)
    ↑                                              │
    │                                        session JSON
    │                                              │
    └───  state/  ←────  sessions/  ←─────────────┘
         (每题状态)         (答题记录 WAL)

wiki/log.md        ←── /ingest, /review, /lint 追加
wiki/purpose.md    ──→ 所有 LLM 操作读取
wiki/overview.md   ←── 每次 /ingest 后重新生成
```

知识单向流经管道：URL → raw → wiki → permanent notes → questions → quiz。测验结果经 sessions 回流到 state，影响下一次选题。每篇 wiki 页面用 `sources: []` 记录所有贡献源。

## 双层质量保障

**第一层——确定性检查。** `health-check.ps1` 对知识库跑 8 项检查，纯规则，不调 LLM，零 token 消耗：

1. 断链检测
2. 孤立笔记（无入链且超过 24 小时的 permanent note）
3. 空文件（只有 frontmatter，无正文）
4. frontmatter 一致性（每种笔记类型的必填字段）
5. 对称链接（A 链 B 但 B 不链 A，仅 `-Strict` 模式）
6. 题库完整性（格式校验、单主题题数、源链接、INDEX 一致性）
7. 状态完整性（sessions 与 state 漂移检测、跨链校验）
8. 日志完整性（格式校验、时间顺序）

**第二层——LLM 驱动。** `/lint` 读 `wiki/purpose.md`，跨主题采样页面，检查矛盾、过时声明、缺失概念、孤立群组和重复内容。按需触发，消耗 token。

所有脚本支持 `-Json` 输出，有完整的 JSON Schema 文档，Agent 和 MCP server 可以直接消费。

## 软件工程映射

| 软件 | 知识 |
|------|------|
| `src/` | `raw/` -- 未加工捕获 |
| `build/` | `wiki/` -- 结构化输出 |
| 编译器 | LLM + `prompts/` 模板 |
| IDE | Obsidian |
| CI/lint | `health-check.ps1` (Tier 1) + `/lint` (Tier 2) |
| 增量编译 | `compile.ps1` -- 变更检测 + quiz 依赖扫描 |

## 数据目录

| 目录 | 用途 | Git |
|------|------|-----|
| `raw/` | 源材料，永不删除 | tracked |
| `wiki/` | 结构化笔记 + `log.md`, `purpose.md`, `overview.md` | tracked |
| `questions/` | 测验题目（含 frontmatter） | tracked |
| `state/` | 每题答题状态（从 sessions 派生） | ignored |
| `sessions/` | 原始答题记录，只追加不删除 | ignored |
| `temp/` | 中间产物、分析草稿 | ignored |
| `output/` | 生成的测验 HTML | ignored |
| `prompts/` | 9 个 LLM 编译器 prompt 模板 | tracked |
| `templates/` | 7 种 Obsidian 笔记模板 | tracked |
| `scripts/` | PowerShell 工具脚本 | tracked |
| `evals/` | Golden 测试用例 | tracked |

## 题目格式

每道题是一个 `.md` 文件，带 YAML frontmatter：

```yaml
type: question
id: fde-kpi-is-contract-growth-1
topic: FDE
difficulty: medium
sources: [fde-kpi-is-contract-growth-not-cost-reduction]
deprecated: false
created: "2026-05-19"
```

正文使用固定格式，`/review` 和 `health-check.ps1` 都能解析：

```markdown
# FDE 战略的核心 KPI 是什么？

A. 降低定制成本
B. 保持合同规模增长
C. 提高用户活跃度
D. 降低边际成本

**答案:** B

**解析:** FDE 战略与 SaaS PMF 的度量逻辑相反，FDE 阶段的核心度量是合同规模增长而非成本降低。
```

题目状态（attempts, correct, wrong）存放在 `state/{id}.json`，不在题目文件里。题目的源笔记更新后，旧题标记 `deprecated: true`，系统生成新题，旧题的答题记录全部保留。

## 快速开始

```powershell
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
.\setup.ps1
```

用 Obsidian 打开文件夹作为 Vault。往 `raw/inbox/` 扔想法，用 `/ingest <URL>` 摄入文章和视频，用 `/review` 刷题复习，用 `/lint` 做语义审计。

## 脚本和命令

```powershell
# 健康检查（8 项确定性检查，不调 LLM）
.\scripts\health-check.ps1 -Verbose
.\scripts\health-check.ps1 -Strict
.\scripts\health-check.ps1 -Json

# 编译（增量 + quiz 依赖检测）
.\scripts\compile.ps1
.\scripts\compile.ps1 -Full
.\scripts\compile.ps1 -WhatIf

# Eval 门禁
.\scripts\eval.ps1 -Verbose        # 确定性：frontmatter, body, links, state-update
.\scripts\eval-llm.ps1 -Verbose    # LLM 驱动：出题结构合规性

# Claude Code 斜杠命令
/ingest <URL>      # 一键知识摄入（两步 CoT）
/review             # 智能测验 + 状态追踪
/lint               # LLM 语义 wiki 审计
```

## License

MIT
