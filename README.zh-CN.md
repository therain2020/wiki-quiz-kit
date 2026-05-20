# wiki-quiz-kit

[English](README.md)

把笔记当成代码管。你捕获原材料，LLM 编译成结构化 wiki 和测验题，脚本保证不乱。在 Obsidian 里浏览编辑，用 Claude Code 斜杠命令驱动全部流程。

## 你需要什么

这是一个项目模板，给 LLM 驱动的知识工作流用的，不是独立应用。你需要：

- **一个 AI coding agent。** Claude Code、Codex CLI——能读文件、按模板调 LLM、写输出文件就行。三个斜杠命令（`/ingest`、`/review`、`/lint`）是 Claude Code skill，代码在 `.claude/skills/`。
- **一个 LLM API key。** 随便哪个 provider：DeepSeek、Claude API、OpenAI 都行。prompt 模板跟模型无关。按你 agent 要求的方式配好 key。
- **Obsidian。** 把项目文件夹当成 Obsidian Vault 打开，用来浏览、编辑、链接笔记。frontmatter schema 和 wikilink 都是 Obsidian 原生支持的。
- **Python 3.11+。** 所有工具脚本都是 Python 3 写的。macOS 自带，Windows 上 `winget install python3`。
- **yt-dlp 和 PyYAML。** `pip install yt-dlp pyyaml`，两个都装上。`setup.py` 会检查 yt-dlp。

## 快速开始

```bash
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
bash setup.sh
```

`setup.sh` 找到 Python（先试 `python3`，不行就用 `python`），交给 `setup.py`：建目录、写欢迎笔记、跑健康检查。

用 Obsidian 把文件夹作为 Vault 打开。在 Claude Code 里跑：

```
/ingest https://youtu.be/vz3Z2XETpGM
```

它会拉 YouTube 字幕，清洗 VTT 噪声，跑两步思维链分析，生成结构化笔记和测验题。全程一次确认。跑完用 `/review` 检验。

## 斜杠命令

**`/ingest <url>`** 喂一个 URL——视频或文章都行——走两步 CoT 管道。第一步：LLM 分析实体、概念、论证、跟已有笔记的关联。第二步：生成一篇文献笔记、若干原子化永久笔记（一个想法一篇）、测验题（写入前经 `validate-draft.py` 校验）、更新主题 MOC。YouTube 视频会通过 yt-dlp 拉字幕，清洗 VTT 噪音后再喂给 LLM。追加 `wiki/log.md`，重新生成 `wiki/overview.md`。

**`/review`** 背后跑的是 `python3 scripts/quiz-gen.py`。LLM 只做一件事：把你说的"复习 ontology 错题"翻译成 `python3 scripts/quiz-gen.py --tags ontology --mode wrong`。脚本读 `questions/bank.json`，根据 `state/*.json` 里的历史选题，打开交互式 HTML 测验。五种模式：

| 模式 | 规则 |
|------|------|
| random | 随便抽 |
| new | 只选没做过的 |
| wrong | 只选上次答错的 |
| consolidate | 正确率不到 80% |
| （默认） | 随机，等同 `--mode random` |

HTML 里嵌的是匹配你标签筛选的全部题目。点"再来一组"浏览器端重新抽——不调 LLM，不刷新页面。做完后 session JSON 自动下载。后台跑 `python3 scripts/watch-sessions.py`，答题状态自动回流，同样零 LLM 成本。

**`/lint`** 对整个 wiki 做语义审计。读 `wiki/purpose.md`，按主题采样笔记，检查矛盾、过时说法、缺失概念、孤立群组和重复内容。报告写入 `wiki/lint-{date}.md`。消耗 token，想深查的时候跑。

## 架构

```
raw/ (源文件)  -->  prompts/ (9 个编译器通道，两步 CoT)  -->  wiki/ (构建产物)
                              |
                     你的 AI agent (Claude Code)

questions/bank.json  -->  scripts/quiz-gen.py  -->  output/ (测验 HTML)
      |                                                    |
      |                                              session JSON
      |                                                    |
      +--  state/*.json  <--  scripts/watch-sessions.py  <+
           (每题状态)

wiki/log.md        <-- /ingest、/review、/lint 追加
wiki/purpose.md    --> 所有 LLM 操作读取
wiki/overview.md   <-- 每次 /ingest 后重新生成
```

URL -> raw -> wiki -> permanent notes -> questions -> quiz。测验结果经 sessions 回流到 state，影响下一次选题。出题和状态更新零 LLM token 消耗——只读写本地数据。

## 质量保障

**第一层——确定性检查。** `health-check.py` 跑 8 项，不调 LLM：

1. 断链检测
2. 孤立笔记（无入链且超 24 小时）
3. 空文件
4. frontmatter 一致性（每种笔记类型的必填字段）
5. 对称链接（`--strict` 模式）
6. 题库完整性（格式、INDEX 一致性、bank.json 同步）
7. 状态完整性（sessions 与 state 漂移检测）
8. 日志完整性（格式、时间顺序）

`validate-draft.py` 在出题管道里充当结构性门禁。它检查字段完备、选项数量、答案有效性、ID 唯一性、源笔记存在性和 JSON 语法。未通过时把 draft 重命名为 `_REJECTED.json` 并报告每条错误。通过时加 `--write`，一次性写完 `.md` 文件、更新 `INDEX.md`、合并到 `bank.json`。

**第二层——LLM 驱动。** `/lint` 检查矛盾、过时说法、缺失概念、孤立群组和重复内容。消耗 token。

## 脚本

```bash
# 健康检查
python3 scripts/health-check.py --verbose
python3 scripts/health-check.py --strict
python3 scripts/health-check.py --json

# 出题（零 LLM 成本）
python3 scripts/quiz-gen.py                        # 全部主题，10 题
python3 scripts/quiz-gen.py --tags llm --count 5
python3 scripts/quiz-gen.py --mode wrong
python3 scripts/quiz-gen.py --mode new
python3 scripts/quiz-gen.py --mode consolidate     # 正确率 < 80%

# 题目 draft 校验 + 写文件
python3 scripts/validate-draft.py temp/draft-{slug}.json
python3 scripts/validate-draft.py temp/draft-{slug}.json --write

# 状态管理（零 LLM 成本）
python3 scripts/update-state.py sessions/session.json
python3 scripts/watch-sessions.py                  # 后台自动更新

# 编译——变更检测 + quiz 依赖扫描
python3 scripts/compile.py
python3 scripts/compile.py --full
python3 scripts/compile.py --what-if

# Eval
python3 scripts/eval.py --verbose
python3 scripts/eval-llm.py --verbose

# Ingest 管道工具
python3 scripts/clean.py --mode vtt --input file.vtt --output clean.txt
python3 scripts/clean.py --mode web --input page.md
python3 scripts/youtube-transcript.py <url> -o transcript.txt
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

知识和题库默认 gitignore。想跨设备同步，在 `.gitignore` 里取消 `raw/`、`wiki/`、`questions/` 的忽略。推 GitHub 用私人仓库。

## License

MIT
