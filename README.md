# wiki-quiz-kit

[中文](README.zh-CN.md)

A personal knowledge system that treats your notes like code. You capture raw material, an LLM compiles it into structured wiki pages and quiz questions, and a health-check script keeps everything consistent. You browse and edit in Obsidian. You drive the whole thing through Claude Code slash commands.

It needs three things to work: an AI agent that can read files and run prompts (Claude Code, Codex CLI, or similar), an LLM API key, and Obsidian.

## What you need

This is not a standalone app or a library you install with pip. It is a **project template** for an LLM-powered knowledge workflow. To use it:

- **An AI coding agent.** Claude Code, Codex CLI, or anything that reads files, runs LLM prompts from templates, and writes output files. The three slash commands (`/ingest`, `/review`, `/lint`) are Claude Code skills that ship in this repo.
- **An LLM API key.** Any provider works — DeepSeek, Claude API, OpenAI, etc. The prompt templates are model-agnostic. Set your key the way your agent expects (Claude Code uses `ANTHROPIC_API_KEY` or your configured provider).
- **Obsidian.** Open this folder as an Obsidian Vault. That is your IDE for browsing, editing, and linking notes. The frontmatter schemas and wikilinks are Obsidian-native. Any Markdown editor works, but Obsidian's linking and graph view are the point.
- **Python 3 (Mac/Linux) or PowerShell (Windows).** The health check ships in two versions. Mac and Linux use `health-check.py` (Python 3, pre-installed on macOS). Windows uses `health-check.ps1` (PowerShell, built in).

## Quick start

**Windows:**
```powershell
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
.\setup.ps1
```

**Mac / Linux:**
```bash
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
bash setup.sh
```

The setup script creates the directory structure, drops a welcome note in `raw/inbox/`, and runs a health check.

Open the folder in Obsidian as a Vault. In Claude Code (or your agent), run:

```
/ingest https://youtu.be/vz3Z2XETpGM
```

This pulls in a YouTube video, extracts the transcript, runs a two-step chain-of-thought analysis, generates structured notes, and writes quiz questions. One confirmation, everything else automatic. When it finishes, try `/review` to quiz yourself on what you just learned.

## What the slash commands do

**`/ingest <url>`** — takes a URL (video, article), extracts content, and runs a two-step CoT pipeline. First the LLM analyzes entities, concepts, arguments, and connections to existing notes. Then it generates: a literature note, atomic permanent notes (one idea each), quiz questions, and an updated topic MOC. For videos, it prioritizes transcripts over descriptions. Appends to `wiki/log.md`, regenerates `wiki/overview.md`.

**`/review`** — reads `questions/bank.json` (one file, fast), picks questions based on your history, and renders an interactive HTML quiz. Five selection modes:

| Mode | What it picks |
|------|---------------|
| default | 40% new, 30% weak, 30% random |
| new | questions you have never seen |
| wrong | questions you got wrong last time |
| consolidate | attempted but accuracy below 80% |
| random | anything |

After the quiz, results copy to your clipboard. Paste them back to Claude, and your per-question stats update. The next quiz weights new questions, weak topics, and past mistakes differently.

**`/lint`** — LLM-driven semantic audit. Reads `wiki/purpose.md`, samples pages across topics, checks for contradictions, stale claims, missing concepts, orphan clusters, and duplicate content. Writes findings to `wiki/lint-{date}.md`. This does what deterministic health checks cannot.

## Architecture

```
raw/ (source)  ──→  prompts/ (9 compiler passes, two-step CoT)  ──→  wiki/ (output)
                              ↑
                    Your AI agent (Claude Code)

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

Knowledge flows one way: URL → raw → wiki → permanent notes → questions → quiz. Quiz results loop back through sessions into state, which feeds the next quiz selection.

## Quality assurance

**Tier 1 — deterministic.** `health-check.ps1` (Windows) or `health-check.py` (Mac/Linux) runs 8 checks, no LLM calls:

1. Broken wiki-links
2. Orphan notes (no incoming links, older than 24h)
3. Empty files
4. Frontmatter consistency (required fields per note type)
5. Symmetric links (`-Strict` only)
6. Question bank integrity (format, INDEX consistency, bank.json sync)
7. State integrity (session vs state drift)
8. Log integrity (format, chronological order)

**Tier 2 — LLM-driven.** `/lint` checks for contradictions, stale claims, missing concepts, orphan clusters, and duplicates. Token cost applies, run it when you want a deeper look.

## Scripts

**Health check (cross-platform):**

```bash
# Mac / Linux
python3 scripts/health-check.py --verbose
python3 scripts/health-check.py --strict
python3 scripts/health-check.py --json
```

```powershell
# Windows
.\scripts\health-check.ps1 -Verbose
.\scripts\health-check.ps1 -Strict
.\scripts\health-check.ps1 -Json
```

**Compile and eval (Windows, or install PowerShell Core on Mac):**

```powershell
# Incremental compilation + quiz dependency detection
.\scripts\compile.ps1
.\scripts\compile.ps1 -Full
.\scripts\compile.ps1 -WhatIf

# Eval
.\scripts\eval.ps1 -Verbose
.\scripts\eval-llm.ps1 -Verbose
```

## Directory map

| Directory | Purpose | Git |
|-----------|---------|-----|
| `raw/` | Source materials | ignored |
| `wiki/` | Structured notes, log, purpose, overview | ignored |
| `questions/` | Quiz bank (`bank.json` + `.md` files) | ignored |
| `state/` | Per-question stats (derived from sessions) | ignored |
| `sessions/` | Quiz answer log, append-only | ignored |
| `temp/` | Intermediate outputs | ignored |
| `output/` | Generated quiz HTML | ignored |
| `prompts/` | 9 LLM prompt templates | tracked |
| `scripts/` | PowerShell + Python tooling (cross-platform) | tracked |
| `.claude/skills/` | Claude Code slash command definitions | tracked |

Knowledge and quiz data are gitignored by default. If you want to sync across devices, unignore `raw/`, `wiki/`, and `questions/` in `.gitignore` — but use a private repo.

## License

MIT
