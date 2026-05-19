---
name: ingest
description: One-command knowledge ingestion pipeline. URL → multi-source extraction + transcript → raw/ → wiki/ → permanent → MOC → health check. Only 1 confirmation point. Use when the user shares a video/article link, says "ingest", "摄入", "一键处理", or "compile this".
---

# /ingest — 7-Stage Knowledge Ingestion Pipeline

## Purpose

Turn any URL (video, article) into structured, linked, health-checked knowledge with one command and one confirmation point. This is the primary agent orchestration demonstration in knowledge-base.

## Pipeline

```
URL → [1] Multi-Source Extract → [2] Confirm → [3] Save raw/
    → [4a] Analyze (CoT step 1) → [4b] Compile wiki/ (CoT step 2)
    → [5] Deepen permanent → [5.5] Generate questions → [6] Update MOC
    → [7] Log + Overview + Health check
```

Only stage [2] requires human confirmation. Everything else is automated.

## Stage Details

### Stage 1: Multi-Source Extraction

For videos:
1. Extract original page content (web fetch)
2. Search for mirrors on transcript-capable platforms (YouTube, B站)
3. If companion articles exist, extract as `raw/articles/<slug>.md`
4. **Transcript priority**: prefer full transcript over video description

For articles:
1. Extract full text from URL
2. If paywalled, fall back to accessible summary

### Stage 2: Confirmation

Present extracted content summary. User confirms: proceed / skip / retry.

### Stage 3: Save raw/

Save to appropriate directory:
- Videos: `raw/videos/<slug>.md` with full metadata (platform, author, URLs, transcript)
- Articles: `raw/articles/<slug>.md` with source attribution

Raw files are **never deleted** — they are the audit trail (sandbox isolation).

### Stage 4: Compile wiki/ (Two-Step Chain-of-Thought)

Before starting, read `wiki/purpose.md` for directional context.

**4a. Analysis (Step 1):**

Read the source file + `wiki/purpose.md` + `wiki/overview.md` → apply `prompts/ingest-analysis.md` → write structured analysis to `temp/analysis-{slug}.json`.

The analysis identifies entities, concepts, arguments, connections to existing wiki pages, contradictions, and structural recommendations. It does NOT write any wiki files.

**4b. Generation (Step 2):**

Read the source file + `temp/analysis-{slug}.json` + `wiki/purpose.md` → apply the appropriate compilation prompt from the table below → generate output with proper frontmatter and wikilinks. Use the analysis to produce more precise connections, better-targeted permanent notes, and well-calibrated questions.

| Source Type | Prompt | Output |
|------------|--------|--------|
| `raw/videos/*.md` | `prompts/video-to-literature.md` | `wiki/literature/<slug>.md` |
| `raw/articles/*.md` | `prompts/article-to-literature.md` | `wiki/literature/<slug>.md` |
| `raw/fleeting/*.md` | `prompts/fleeting-to-permanent.md` | `wiki/permanent/<slug>.md` |
| `raw/highlights/*.md` | `prompts/highlight-to-permanent.md` | `wiki/permanent/<slug>.md` |
| `raw/meetings/*.md` | `prompts/meeting-to-notes.md` | polished meeting notes |
| `raw/inbox/*.md` | `prompts/inbox-triage.md` | Classify first, then compile |

### Stage 5: Deepen to Permanent

For each key concept identified in the literature note, generate an atomic permanent note in `wiki/permanent/`. One idea per note. Wikilinks to existing notes.

### Stage 5.5: Generate Questions

Uses `prompts/generate-questions.md` (8th compiler pass). Structured pipeline:

1. **Generate draft** — LLM reads new wiki notes + applies `prompts/generate-questions.md`, outputs JSON to `temp/draft-{slug}.json`
2. **Validate** — check each question in the draft:
   - `id`, `topic`, `difficulty`, `source`, `question`, `explanation` are non-empty
   - `options` has at least 2 items
   - `answer` is a valid index into `options`
3. **On validation failure** — rename draft to `temp/draft-{slug}_REJECTED.json`, report which questions failed and why
4. **On validation pass** — for each question, write `questions/{question.id}.md`:
   ```markdown
   ---
   type: question
   id: {id}
   topic: {topic}
   difficulty: {difficulty}
   sources: [{source}]
   created: "YYYY-MM-DD"
   ---
   # {question}
   A. {options[0]}
   B. {options[1]}
   C. {options[2]}
   D. {options[3]}
   **答案:** {A|B|C|D}
   **解析:** {explanation}
   ```
5. **Update INDEX.md** — add each new question to the appropriate topic section in `questions/INDEX.md`
6. **Update bank.json** — read `questions/bank.json` (init `[]` if missing), append new question objects, write back atomically. `/review` reads this single file instead of parsing individual `.md` files.
7. **Keep draft** — `temp/draft-{slug}.json` stays for traceability, user deletes when ready

### Stage 6: Update MOC

Add new notes to relevant Maps of Content. Add to the relevant MOC in `wiki/moc/` or create a new MOC if needed.

### Stage 7: Finalize

1. **Log:** Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD HH:MM] ingest | {title}
   ```
2. **Overview:** Regenerate `wiki/overview.md` — read all wiki stats (note counts, topic coverage) and update the summary. Include recent activity from the last 5 log entries. Identify knowledge gaps (frequently-linked concepts lacking pages, topics with quiz accuracy below 40%).
3. **Health check:** Run `python3 scripts/health-check.py --verbose`. Report: broken links, orphans, empty files, frontmatter errors. Fix any issues.

## Design Principles

1. **Two-step CoT**: analyze first (entities, concepts, connections, contradictions), then generate. Better precision at the cost of one extra LLM call.
2. **Deterministic guardrails + probabilistic core**: health-check is the hard constraint. LLM generates content within those constraints.
3. **Sandbox isolation**: raw/ is never deleted. Wiki/ is the processed output.
4. **Transcript priority**: prefer verbatim transcripts over summarized descriptions.
5. **Multi-source traceability**: every wiki page records all contributing source slugs in `sources: []`.
6. **One idea per note**: atomic permanent notes. Structure emerges from links, not folders.

## Related

- `scripts/compile.py` — deterministic change detection + file-to-prompt mapping
- `scripts/health-check.py` — CI for knowledge integrity
- `prompts/` — 9 compiler pass templates (including ingest-analysis)
- `CLAUDE.md` — project-level Claude Code configuration
