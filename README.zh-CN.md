# wiki-quiz-kit

[English](README.md)

把你的笔记当成软件项目来管理：原始源文件、编译器通道、构建产物、CI 检查、自动化测试。两个 Claude Code 斜杠命令驱动一切。`/ingest` 把知识拉进来，`/review` 考你记住了多少。

## 能做什么

**`/ingest`** 接收一个 URL（视频或文章），提取内容，通过 8 个 LLM prompt 模板生成结构化笔记。全程只有一个确认点，其余自动完成。处理视频时优先用转录文稿（YouTube 自动字幕），而不是视频描述。信息更完整，更接近一手来源。

**`/review`** 从题库选题，渲染 HTML 测验页面，记录你的答案。做完后自动把答题结果复制到剪贴板，粘贴给 Claude 就行，它会更新每道题的状态（做过几次、对了几次、错了几次）。下次出题时，新题、薄弱点和错题的权重都不一样。

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
raw/ (源文件)  ──→  prompts/ (8 个编译器通道)  ──→  wiki/ (构建产物)
                               ↑
                          Claude Code

questions/  ──→  .claude/skills/review/  ──→  output/ (测验 HTML)
    ↑                                              │
    │                                        session JSON
    │                                              │
    └───  state/  ←────  sessions/  ←─────────────┘
         (每题状态)         (答题记录 WAL)
```

知识单向流经管道：URL → raw → wiki → permanent notes → questions → quiz。测验结果经 sessions 回流到 state，影响下一次选题。

## 软件工程映射

| 软件 | 知识 |
|------|------|
| `src/` | `raw/` -- 未加工捕获 |
| `build/` | `wiki/` -- 结构化输出 |
| 编译器 | LLM + `prompts/` 模板 |
| IDE | Obsidian |
| CI/lint | `health-check.ps1` -- 7 项确定性检查 |
| 增量编译 | `compile.ps1` -- 变更检测 |

## 健康检查（纯规则，不调 LLM）

`health-check.ps1` 对知识库跑 7 项检查：

1. 断链检测
2. 孤立笔记（无入链且超过 24 小时的 permanent note）
3. 空文件（只有 frontmatter，无正文）
4. frontmatter 一致性（每种笔记类型的必填字段）
5. 对称链接（A 链 B 但 B 不链 A，仅 `-Strict` 模式）
6. 题库完整性（格式校验、单主题题数、源链接、INDEX 一致性）
7. 状态完整性（sessions 与 state 漂移检测、跨链校验）

所有脚本支持 `-Json` 输出，有完整的 JSON Schema 文档，Agent 和 MCP server 可以直接消费。

## 数据目录

| 目录 | 用途 | Git |
|------|------|-----|
| `raw/` | 源材料，永不删除 | tracked |
| `wiki/` | 结构化笔记（permanent, literature, daily, MOC） | tracked |
| `questions/` | 测验题目（含 frontmatter） | tracked |
| `state/` | 每题答题状态（从 sessions 派生） | ignored |
| `sessions/` | 原始答题记录，只追加不删除 | ignored |
| `temp/` | 中间产物、出题草稿 | ignored |
| `output/` | 生成的测验 HTML | ignored |
| `prompts/` | 8 个 LLM 编译器 prompt 模板 | tracked |
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
source: fde-kpi-is-contract-growth-not-cost-reduction
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

用 Obsidian 打开文件夹作为 Vault。往 `raw/inbox/` 扔想法，用 `/ingest <URL>` 摄入文章和视频，用 `/review` 刷题复习。

## 脚本

```powershell
.\scripts\health-check.ps1            # 7 项检查，不调 LLM
.\scripts\health-check.ps1 -Strict    # 含对称链接检查
.\scripts\health-check.ps1 -Verbose   # 逐条显示
.\scripts\health-check.ps1 -Json      # 机器可读输出

.\scripts\compile.ps1                 # 增量扫描
.\scripts\compile.ps1 -Full           # 全量
.\scripts\compile.ps1 -WhatIf         # 干跑
.\scripts\compile.ps1 -Interactive    # 逐个确认

.\scripts\eval.ps1 -Verbose           # 确定性 eval 门禁
.\scripts\eval-llm.ps1 -Verbose       # LLM 驱动出题 eval
```

## License

MIT
