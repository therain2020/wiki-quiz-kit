# wiki-quiz-kit

[中文](README.zh-CN.md)

Treats your notes like a software project: raw source files, compiler passes, build outputs, CI checks, and automated testing. Based on Karpathy's LLM Wiki pattern. Three Claude Code slash commands drive everything. `/ingest` pulls knowledge in, `/review` quizzes you on it, `/lint` audits the wiki for semantic issues.

## What it does

**`/ingest`** takes a URL (video or article), extracts the content, and runs a two-step chain-of-thought pipeline: first the LLM analyzes entities, concepts, arguments, and connections to existing wiki pages, then it generates structured notes from that analysis. 9 LLM prompt templates handle different source types. One confirmation point, everything else automatic. For videos, it prefers transcripts (YouTube auto-captions) over descriptions. After each run, it appends to `wiki/log.md` and regenerates `wiki/overview.md`.

**`/review`** picks questions from your question bank, reads `wiki/purpose.md` for priority context, renders an HTML quiz, and tracks your answers. After you finish, it copies the session results to your clipboard. Paste them into Claude, and your per-question stats (attempts, correct, wrong) get updated. Next time you ask for a quiz, it weighs new questions, weak topics, and past mistakes differently. Session results are logged to `wiki/log.md`.

**`/lint`** does what `health-check.ps1` cannot: LLM-powered semantic audit. It reads purpose.md, samples wiki pages, and checks for contradictions, stale claims, missing concepts, orphan clusters, and duplicate content. Results are written to `wiki/lint-{date}.md` and logged.

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
raw/ (source)  ──→  prompts/ (9 compiler passes, two-step CoT)  ──→  wiki/ (output)
                              ↑
                         Claude Code

questions/  ──→  .claude/skills/review/  ──→  output/ (quiz HTML)
    ↑                                              │
    │                                        session JSON
    │                                              │
    └───  state/  ←────  sessions/  ←─────────────┘
         (per-question stats)   (answer WAL)

wiki/log.md        ←── /ingest, /review, /lint append
wiki/purpose.md    ──→ read by all LLM operations
wiki/overview.md   ←── regenerated after each /ingest
```

Knowledge moves in one direction through the pipeline: URL → raw → wiki → permanent notes → questions → quiz. The quiz results loop back through sessions into state, which feeds into the next quiz selection. Every wiki page records contributing sources in `sources: []`.

## Two-layer quality assurance

**Tier 1 -- deterministic.** `health-check.ps1` runs 8 checks against your vault, all pure rules, zero LLM cost:

1. Broken wiki-links
2. Orphan notes (permanent notes with no incoming links, older than 24h)
3. Empty files (frontmatter only, no body)
4. Frontmatter consistency (required fields per note type)
5. Symmetric links (A links to B but B does not link back, `-Strict` only)
6. Question bank integrity (format validation, per-topic counts, source link checks, INDEX consistency)
7. State integrity (session vs state drift detection, cross-link validation)
8. Log integrity (format validation, chronological order)

**Tier 2 -- LLM-driven.** `/lint` reads `wiki/purpose.md`, samples pages across topics, and checks for contradictions, stale claims, missing concepts, orphan clusters, and duplicates. On-demand, token cost applies.

All scripts support `-Json` output with a documented JSON Schema, so agents and MCP servers can consume results directly.

## How it maps to software engineering

| Software | Knowledge |
|----------|-----------|
| `src/` | `raw/` -- unprocessed capture |
| `build/` | `wiki/` -- structured output |
| compiler | LLM + `prompts/` templates |
| IDE | Obsidian |
| CI/lint | `health-check.ps1` (Tier 1) + `/lint` (Tier 2) |
| incremental build | `compile.ps1` -- change detection + quiz dependency scan |

## Data directories

| Directory | Purpose | Git |
|-----------|---------|-----|
| `raw/` | Source materials, never deleted | tracked |
| `wiki/` | Structured notes + `log.md`, `purpose.md`, `overview.md` | tracked |
| `questions/` | Quiz questions with frontmatter | tracked |
| `state/` | Per-question attempt stats (derived from sessions) | ignored |
| `sessions/` | Raw quiz answer logs, append-only WAL | ignored |
| `temp/` | Intermediate outputs, analysis drafts | ignored |
| `output/` | Generated quiz HTML | ignored |
| `prompts/` | 9 LLM compiler prompt templates | tracked |
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
sources: [fde-kpi-is-contract-growth-not-cost-reduction]
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

Open the folder in Obsidian as a Vault. Drop thoughts into `raw/inbox/`, use `/ingest <URL>` to pull in articles and videos, use `/review` to quiz yourself, use `/lint` for a semantic audit.

## Scripts and commands

```powershell
# Health checks (8 deterministic checks, no LLM)
.\scripts\health-check.ps1 -Verbose
.\scripts\health-check.ps1 -Strict
.\scripts\health-check.ps1 -Json

# Compile (incremental + quiz dependency detection)
.\scripts\compile.ps1
.\scripts\compile.ps1 -Full
.\scripts\compile.ps1 -WhatIf

# Eval gates
.\scripts\eval.ps1 -Verbose        # deterministic: frontmatter, body, links, state-update
.\scripts\eval-llm.ps1 -Verbose    # LLM-driven: question generation structure compliance

# Claude Code slash commands
/ingest <URL>      # one-click knowledge ingestion (two-step CoT)
/review             # smart quiz with state tracking
/lint               # LLM semantic wiki audit
```

## License

MIT
