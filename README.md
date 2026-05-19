# wiki-quiz-kit

Treats your notes like a software project: raw source files, compiler passes, build outputs, CI checks, and automated testing. Two Claude Code slash commands drive everything. `/ingest` pulls knowledge in, `/review` quizzes you on it.

## What it does

**`/ingest`** takes a URL (video or article), extracts the content, and runs it through 8 LLM prompt templates to produce structured notes. One confirmation point, everything else automatic. For videos, it prefers transcripts (YouTube auto-captions) over descriptions. More detail, closer to the source.

**`/review`** picks questions from your question bank, renders an HTML quiz, and tracks your answers. After you finish, it copies the session results to your clipboard. Paste them into Claude, and your per-question stats (attempts, correct, wrong) get updated. Next time you ask for a quiz, it weighs new questions, weak topics, and past mistakes differently.

The quiz has five selection modes:

| Mode | What it picks |
|------|---------------|
| default | 40% new, 30% weak, 30% random |
| new | questions you have never seen |
| wrong | questions you got wrong last time |
| consolidate | attempted but accuracy below 80% |
| random | anything |

## Architecture

```
raw/ (source files)  ──→  prompts/ (8 compiler passes)  ──→  wiki/ (build output)
                               ↑
                          Claude Code

questions/  ──→  .claude/skills/review/  ──→  output/ (quiz HTML)
    ↑                                              │
    │                                        session JSON
    │                                              │
    └───  state/  ←────  sessions/  ←─────────────┘
         (per-question stats)   (answer WAL)
```

Knowledge moves in one direction through the pipeline: URL → raw → wiki → permanent notes → questions → quiz. The quiz results loop back through sessions into state, which feeds into the next quiz selection.

## How it maps to software engineering

| Software | Knowledge |
|----------|-----------|
| `src/` | `raw/` -- unprocessed capture |
| `build/` | `wiki/` -- structured output |
| compiler | LLM + `prompts/` templates |
| IDE | Obsidian |
| CI/lint | `health-check.ps1` -- 7 deterministic checks |
| incremental build | `compile.ps1` -- change detection |

## Health checks (all deterministic, no LLM)

`health-check.ps1` runs 7 checks against your vault:

1. Broken wiki-links
2. Orphan notes (permanent notes with no incoming links, older than 24h)
3. Empty files (frontmatter only, no body)
4. Frontmatter consistency (required fields per note type)
5. Symmetric links (A links to B but B does not link back, `-Strict` only)
6. Question bank integrity (format validation, per-topic counts, source links, INDEX consistency)
7. State integrity (session vs state drift detection, cross-link validation)

All scripts support `-Json` output with a documented JSON Schema, so agents and MCP servers can consume results directly.

## Data directories

| Directory | Purpose | Git |
|-----------|---------|-----|
| `raw/` | Source materials, never deleted | tracked |
| `wiki/` | Structured notes (permanent, literature, daily, MOC) | tracked |
| `questions/` | Quiz questions with frontmatter | tracked |
| `state/` | Per-question attempt stats (derived from sessions) | ignored |
| `sessions/` | Raw quiz answer logs, append-only WAL | ignored |
| `temp/` | Intermediate outputs, question drafts | ignored |
| `output/` | Generated quiz HTML | ignored |
| `prompts/` | 8 LLM compiler prompt templates | tracked |
| `templates/` | 7 Obsidian note templates | tracked |
| `scripts/` | PowerShell tooling | tracked |
| `evals/` | Golden test cases | tracked |

## Question format

Each question is a `.md` file with YAML frontmatter:

```yaml
type: question
id: fde-kpi-is-contract-growth-1
topic: FDE
difficulty: medium
source: fde-kpi-is-contract-growth-not-cost-reduction
deprecated: false
created: "2026-05-19"
```

The body uses a fixed format that `/review` and `health-check.ps1` both parse:

```markdown
# What is the core KPI of the FDE strategy?

A. Lower customization costs
B. Contract revenue growth
C. Increase user activity
D. Reduce marginal costs

**答案:** B

**解析:** FDE measures success by contract revenue growth, not cost reduction.
```

Question state (attempts, correct, wrong) lives in `state/{id}.json`, not in the question file. When a question's source note changes, the old question gets `deprecated: true` and a new one is generated. The old stats stay.

## Quick start

```powershell
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
.\setup.ps1
```

Open the folder in Obsidian as a Vault. Drop thoughts into `raw/inbox/`, use `/ingest <URL>` to pull in articles and videos, use `/review` to quiz yourself.

## Scripts

```powershell
.\scripts\health-check.ps1            # 7 checks, no LLM
.\scripts\health-check.ps1 -Strict    # with symmetric link check
.\scripts\health-check.ps1 -Verbose   # per-issue details
.\scripts\health-check.ps1 -Json      # machine-readable output

.\scripts\compile.ps1                 # incremental scan
.\scripts\compile.ps1 -Full           # treat all files as changed
.\scripts\compile.ps1 -WhatIf         # dry run
.\scripts\compile.ps1 -Interactive    # step through each file

.\scripts\eval.ps1 -Verbose           # deterministic eval gate
.\scripts\eval-llm.ps1 -Verbose       # LLM-driven question generation eval
```

## License

MIT
