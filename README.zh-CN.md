# wiki-quiz-kit

[English](README.md)

把笔记当成代码管——你捕获原始材料，LLM 把它们编译成结构化 wiki 页面和测验题，健康检查脚本保证一切不乱。你用 Obsidian 浏览和编辑，用 Claude Code 的斜杠命令驱动整个流程。

## 你需要什么

这不是一个独立应用，也不是 pip install 就能用的库。它是一个**项目模板**，给 LLM 驱动的知识工作流用的。你需要：

- **一个 AI coding agent。** Claude Code、Codex CLI，任何能读文件、按模板调 LLM、写输出文件的 agent 都行。项目里的三个斜杠命令（`/ingest`、`/review`、`/lint`）就是 Claude Code 的 skill，代码在 `.claude/skills/` 里。
- **一个 LLM API key。** 随便哪个 provider——DeepSeek、Claude API、OpenAI 都行。prompt 模板跟模型无关。按你 agent 要求的方式配好 key 就行。
- **Obsidian。** 把项目文件夹当成 Obsidian Vault 打开。它是你浏览、编辑、链接笔记的 IDE。frontmatter schema 和 wikilink 都是 Obsidian 原生支持的。
- **Python 3。** 所有工具脚本都是 Python 3 写的。macOS 自带，Windows 上 `winget install python3` 一行搞定。

## 快速开始

```bash
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
bash setup.sh
```

`setup.sh` 检查 Python 是否就绪，然后交给 `setup.py`——创建目录结构、写欢迎笔记、跑一次健康检查。

用 Obsidian 打开文件夹作为 Vault。在 Claude Code（或者你的 agent）里跑：

```
/ingest https://youtu.be/vz3Z2XETpGM
```

这会把一个 YouTube 视频拉进来，提取字幕，跑两步思维链分析，生成结构化笔记和测验题。全程只确认一次，其他自动完成。跑完之后用 `/review` 刷题，检验刚学的东西。

## 三个斜杠命令

**`/ingest <url>`** —— 喂一个 URL（视频或文章），提取内容，走两步 CoT 管道。LLM 先分析实体、概念、论证、跟已有笔记的关联，再生成：一篇文献笔记、若干原子化永久笔记（一个想法一篇）、测验题、更新主题 MOC。处理视频时优先用字幕而非简介。追加 `wiki/log.md`，重新生成 `wiki/overview.md`。

**`/review`** —— 读 `questions/bank.json`（一个文件，速度快），根据你的答题历史选题，渲染交互式 HTML 测验。五种模式：

| 模式 | 规则 |
|------|------|
| 默认 | 40% 新题，30% 薄弱，30% 随机 |
| 新题 | 只选没做过的 |
| 错题 | 只选上次答错的 |
| 巩固 | 做过但正确率不到 80% |
| 随机 | 随便选 |

做完后答题结果自动复制到剪贴板。贴给 Claude，每道题的状态就更新了。下次出题时，新题、薄弱点、错题的权重都不一样。

**`/lint`** —— LLM 驱动的语义审计。读 `wiki/purpose.md`，跨主题采样笔记，检查矛盾、过时说法、缺失概念、孤立群组和重复内容。结果写入 `wiki/lint-{date}.md`。这是确定性检查做不到的事。

## 架构

```
raw/ (源文件)  ──→  prompts/ (9 个编译器通道，两步 CoT)  ──→  wiki/ (构建产物)
                              ↑
                     你的 AI agent (Claude Code)

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

知识单向流动：URL → raw → wiki → permanent notes → questions → quiz。测验结果经 sessions 回流到 state，影响下一次选题。

## 质量保障

**第一层——确定性检查。** `health-check.py` 跑 8 项，不调 LLM，零 token 消耗：

1. 断链检测
2. 孤立笔记（无入链且超 24 小时）
3. 空文件
4. frontmatter 一致性（每种笔记类型的必填字段）
5. 对称链接（`--strict` 模式）
6. 题库完整性（格式、INDEX 一致性、bank.json 同步）
7. 状态完整性（sessions 与 state 漂移检测）
8. 日志完整性（格式、时间顺序）

**第二层——LLM 驱动。** `/lint` 检查矛盾、过时说法、缺失概念、孤立群组和重复内容。消耗 token，想深查的时候跑。

## 脚本

```bash
# 健康检查
python3 scripts/health-check.py --verbose
python3 scripts/health-check.py --strict
python3 scripts/health-check.py --json

# 编译——增量变更检测 + quiz 依赖扫描
python3 scripts/compile.py
python3 scripts/compile.py --full
python3 scripts/compile.py --what-if

# Eval
python3 scripts/eval.py --verbose
python3 scripts/eval-llm.py --verbose
```

## 目录结构

| 目录 | 用途 | Git |
|------|------|-----|
| `raw/` | 源材料 | ignored |
| `wiki/` | 结构化笔记、log、purpose、overview | ignored |
| `questions/` | 题库（`bank.json` + `.md` 文件） | ignored |
| `state/` | 每题答题状态（从 sessions 派生） | ignored |
| `sessions/` | 答题记录，只追加 | ignored |
| `temp/` | 中间产物 | ignored |
| `output/` | 生成的测验 HTML | ignored |
| `prompts/` | 9 个 LLM prompt 模板 | tracked |
| `scripts/` | Python 工具脚本（跨平台） | tracked |
| `.claude/skills/` | Claude Code 斜杠命令定义 | tracked |

知识和题库默认 gitignore。想跨设备同步的话，在 `.gitignore` 里取消 `raw/`、`wiki/`、`questions/` 的忽略——但记得用**私人仓库**。

## License

MIT
