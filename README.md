# wiki-quiz-kit

> **Wiki + Quiz：知识库 × 刷题复习，一体化的 AI 原生知识系统**
>
> `/ingest` 一键摄入 → wiki 结构化 → 自动出题 → `/review` 交互刷题
> 确定性 Guardrails · Eval Driven Development · 抽象化管道 · CLI 即 API

---

## 一眼看出我的能力

| 维度 | 能力 | 证据 |
|------|------|------|
| **Wiki** | LLM 作为编译器驱动 | 8 个 prompt 模板构成编译器管道，raw/ → wiki/ 全自动 |
| | Prompt Engineering 作为工程学科 | 每种 raw 类型对应独立 prompt，可单独调试、替换、A/B 测试 |
| | AI Agent 自主执行 | `/ingest` 管道 7 阶段全自动，URL 进去→结构化知识出来，1 个人工确认点 |
| | 确定性 Guardrails | 7 项纯规则检查，不调 LLM。正则+路径解析+字段校验，硬约束在代码里 |
| | Eval Driven Development | Golden cases + eval runner，compile 末尾自动触发 eval gate |
| | 抽象化循环 | raw/ 碎石路 → prompts/ + templates/ 高速公路 |
| **Quiz** | 摄入即出题 | `/ingest` Stage 5.5 自动从新内容生成复习题到 `questions/`，含 prompt 校验 |
| | 交互式测验 | `/review` 选题→渲染 HTML，纸墨质感设计，支持智能选题（新题/错题/薄弱/巩固） |
| | 答题状态追踪 | `sessions/` 记录每次答题 WAL，`state/` 并发更新每题正确率，支持状态回流 |
| | CLI 即 Agent 接口 | 所有脚本 `-Json` 输出，符合 Schema，可直接被 MCP server/Agent 消费 |

## 架构

```
                     Claude Code (编译器驱动)
                           │
raw/ ──→ [prompts/ 8个编译器Pass] ──→ wiki/ ──→ health-check.ps1
  │                                      │            │
  │    questions/ ←── ingest auto-gen ──┘      7项确定性检查
  │         │
  │    .claude/skills/review/
  │         │
  │    output/quiz-*.html ──→ sessions/ ──→ state/
  └────────────────────────────────────────────┘
              (交互刷题 + 状态回流)
```

> `/ingest` 读完文章/视频 → 自动出题。`/review` 随时刷题复习。wiki 和 quiz 是一个闭环。

## 文件清单

```
scripts/
├── health-check.ps1              # CI：7 项确定性检查
├── health-check-schema.json      # MCP-ready JSON Schema
├── compile.ps1                   # 增量编译：hash 变更 + prompt 自动映射
└── eval.ps1                      # Eval runner：compile 末尾自动触发 gate
prompts/                          # 8 个 LLM 编译器 Pass（可替换可A/B）
templates/                        # 抽象产物：7 种笔记模板
evals/cases/sample/               # 示例 Golden Case
.claude/skills/
├── ingest/SKILL.md               # AI Agent：7 阶段全自动知识摄入
└── review/
    ├── SKILL.md                  # 交互式测验生成器
    └── quiz-template.html        # 纸墨质感测验模板
setup.ps1                         # 30 秒初始化
raw/ wiki/ questions/ state/ sessions/ temp/ output/     # 数据目录
```

## 30 秒开始

```powershell
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb; .\setup.ps1              # 一键初始化
```

用 Obsidian 打开文件夹作为 Vault。往 `raw/inbox/` 扔想法，`/ingest <URL>` 摄入文章视频（自动出题），`/review` 刷题复习。

## License

MIT
