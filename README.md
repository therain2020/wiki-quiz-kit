# wiki-quiz-kit

[中文](README.zh-CN.md)

A personal knowledge system that treats your notes like code. You capture raw material, an LLM compiles it into structured wiki pages and quiz questions, and scripts keep everything consistent. You browse and edit in Obsidian. You drive it through Claude Code slash commands.

## What you need

This is a project template for an LLM-powered knowledge workflow, not a standalone app. To use it:

- **An AI coding agent.** Claude Code, Codex CLI, or anything that reads files, runs LLM prompts from templates, and writes output files. The slash commands (`/ingest`, `/review`, `/lint`) are Claude Code skills shipped in this repo.
- **An LLM API key.** Any provider works: DeepSeek, Claude API, OpenAI. The prompt templates are model-agnostic. Set your key the way your agent expects.
- **Obsidian.** Open this folder as an Obsidian Vault. That is your IDE for browsing, editing, and linking notes. The frontmatter schemas and wikilinks are Obsidian-native.
- **Python 3.11+.** All tooling runs on Python 3. macOS has it, Windows needs `winget install python3`.
- **yt-dlp and PyYAML.** `pip install yt-dlp pyyaml` covers both. `setup.py` checks for yt-dlp.

## Quick start

```bash
git clone https://github.com/therain2020/wiki-quiz-kit.git my-kb
cd my-kb
bash setup.sh
```

`setup.sh` finds Python (tries `python3` first, falls back to `python`), hands off to `setup.py` which creates the directory tree, writes a welcome note, and runs a health check.

Open the folder in Obsidian as a Vault. In Claude Code, run:

```
/ingest https://youtu.be/vz3Z2XETpGM
```

It pulls the YouTube transcript, cleans the VTT noise, runs a two-step chain-of-thought analysis, generates structured notes, and writes quiz questions. One confirmation. When it finishes, try `/review` to quiz yourself.

## Slash commands

**`/ingest <url>`** takes a URL — video or article — and runs a two-step CoT pipeline. Step one: the LLM analyzes entities, concepts, arguments, and connections to existing notes. Step two: it generates a literature note, atomic permanent notes (one idea each), quiz questions (validated by `validate-draft.py` before writing), and an updated topic MOC. YouTube videos get auto-captions pulled via yt-dlp, cleaned of VTT noise, then fed to the LLM. Appends to `wiki/log.md`, regenerates `wiki/overview.md`.

**`/review`** runs `python3 scripts/quiz-gen.py`. All the LLM does is translate your words into CLI args — "复习 ontology 错题" becomes `python3 scripts/quiz-gen.py --tags ontology --mode wrong`. The script reads `questions/bank.json`, picks questions from your history in `state/*.json`, and opens an interactive HTML quiz in your browser. Five modes:

| Mode | What it picks |
|------|---------------|
| random | anything |
| new | questions you have never seen |
| wrong | questions you got wrong last time |
| consolidate | attempted but accuracy below 80% |
| (default) | random, same as `--mode random` |

The HTML embeds every question matching your tag filter. Click "再来一组" and it re-rolls from that set in the browser — no LLM call, no page reload. After answering, session JSON auto-downloads. Run `python3 scripts/watch-sessions.py` in the background and your per-question stats update automatically.

**`/lint`** runs a semantic audit across your wiki. It reads `wiki/purpose.md`, samples pages by topic, and checks for contradictions, stale claims, missing concepts, orphan clusters, and duplicates. Writes a report to `wiki/lint-{date}.md`. Token cost applies — run it when you want a second pair of eyes on your notes.

## Architecture

```
raw/ (source)  -->  prompts/ (9 compiler passes, two-step CoT)  -->  wiki/ (output)
                              |
                    Your AI agent (Claude Code)

questions/bank.json  -->  scripts/quiz-gen.py  -->  output/ (quiz HTML)
      |                                                    |
      |                                              session JSON
      |                                                    |
      +--  state/*.json  <--  scripts/watch-sessions.py  <+
           (per-question stats)

wiki/log.md        <-- /ingest, /review, /lint append
wiki/purpose.md    --> read by all LLM operations
wiki/overview.md   <-- regenerated after each /ingest
```

URL -> raw -> wiki -> permanent notes -> questions -> quiz. Quiz results flow back through sessions into state, feeding the next round of question selection. The quiz generation and state update steps cost zero LLM tokens — they only read and write local data.

## Quality assurance

**Tier 1 — deterministic.** `health-check.py` runs 8 checks, no LLM calls:

1. Broken wiki-links
2. Orphan notes (no incoming links, older than 24h)
3. Empty files
4. Frontmatter consistency (required fields per note type)
5. Symmetric links (`--strict` only)
6. Question bank integrity (format, INDEX consistency, bank.json sync)
7. State integrity (session vs state drift)
8. Log integrity (format, chronological order)

`validate-draft.py` provides a structural gate for question generation. It checks field completeness, option count, answer validity, ID uniqueness, source note existence, and JSON syntax. On failure, it renames the draft to `_REJECTED.json` and reports every error. On pass with `--write`, it writes `.md` files, updates `INDEX.md`, and merges into `bank.json` — all in one command.

**Tier 2 — LLM-driven.** `/lint` checks for contradictions, stale claims, missing concepts, orphan clusters, and duplicates. Token cost applies.

## Scripts

```bash
# Health check
python3 scripts/health-check.py --verbose
python3 scripts/health-check.py --strict
python3 scripts/health-check.py --json

# Quiz generation (zero LLM cost)
python3 scripts/quiz-gen.py                        # all topics, 10 questions
python3 scripts/quiz-gen.py --tags llm --count 5
python3 scripts/quiz-gen.py --mode wrong
python3 scripts/quiz-gen.py --mode new
python3 scripts/quiz-gen.py --mode consolidate     # accuracy < 80%

# Question draft validation + file writing
python3 scripts/validate-draft.py temp/draft-{slug}.json
python3 scripts/validate-draft.py temp/draft-{slug}.json --write

# State management (zero LLM cost)
python3 scripts/update-state.py sessions/session.json
python3 scripts/watch-sessions.py                  # background auto-update

# Compile — change detection + quiz dependency scan
python3 scripts/compile.py
python3 scripts/compile.py --full
python3 scripts/compile.py --what-if

# Eval
python3 scripts/eval.py --verbose
python3 scripts/eval-llm.py --verbose

# Ingest pipeline utilities
python3 scripts/clean.py --mode vtt --input file.vtt --output clean.txt
python3 scripts/clean.py --mode web --input page.md
python3 scripts/youtube-transcript.py <url> -o transcript.txt
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
| `scripts/` | Python tooling (cross-platform) | tracked |
| `.claude/skills/` | Claude Code slash command definitions | tracked |

Knowledge and quiz data are gitignored by default. To sync across devices, unignore `raw/`, `wiki/`, and `questions/` in `.gitignore`. Use a private repo if you push to GitHub.

## License

MIT
