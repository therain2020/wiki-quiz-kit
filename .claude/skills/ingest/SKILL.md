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
    → [4] Compile wiki/ → [5] Deepen permanent
    → [5.5] Generate questions → [6] Update MOC → [7] Health check
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

### Stage 4: Compile wiki/

Map source → prompt → output:

| Source Type | Prompt | Output |
|------------|--------|--------|
| `raw/videos/*.md` | `prompts/video-to-literature.md` | `wiki/literature/<slug>.md` |
| `raw/articles/*.md` | `prompts/article-to-literature.md` | `wiki/literature/<slug>.md` |
| `raw/fleeting/*.md` | `prompts/fleeting-to-permanent.md` | `wiki/permanent/<slug>.md` |
| `raw/highlights/*.md` | `prompts/highlight-to-permanent.md` | `wiki/permanent/<slug>.md` |
| `raw/meetings/*.md` | `prompts/meeting-to-notes.md` | polished meeting notes |
| `raw/inbox/*.md` | `prompts/inbox-triage.md` | Classify first, then compile |

Read the source file → read the prompt template → generate output with proper frontmatter and wikilinks.

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
   source: {source}
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
6. **Keep draft** — `temp/draft-{slug}.json` stays for traceability, user deletes when ready

### Stage 6: Update MOC

Add new notes to relevant Maps of Content. Add to the relevant MOC in `wiki/moc/` or create a new MOC if needed.

### Stage 7: Health Check

Run `scripts/health-check.ps1 -Verbose`. Report: broken links, orphans, empty files, frontmatter errors. Fix any issues.

## Design Principles

1. **Deterministic guardrails + probabilistic core**: health-check is the hard constraint. LLM generates content within those constraints.
2. **Sandbox isolation**: raw/ is never deleted. Wiki/ is the processed output. Same pattern as sandbox branching for AI agents.
3. **Transcript priority**: prefer verbatim transcripts over summarized descriptions. Primary source > secondary source.
4. **API first, scrape fallback**: prefer structured data APIs (YouTube transcripts via tavily) over raw page scraping.
5. **One idea per note**: atomic permanent notes. Structure emerges from links, not folders.

## Related

- `scripts/compile.ps1` — deterministic change detection + file-to-prompt mapping
- `scripts/health-check.ps1` — CI for knowledge integrity
- `prompts/` — 8 compiler pass templates
- `CLAUDE.md` — project-level Claude Code configuration
