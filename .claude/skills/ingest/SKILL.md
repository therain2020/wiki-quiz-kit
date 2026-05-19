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

Auto-generate review questions from the new content. Save to `questions/<topic-slug>-<n>.md`. Update `questions/INDEX.md`.

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
- `prompts/` — 7 compiler pass templates
- `CLAUDE.md` — project-level Claude Code configuration
