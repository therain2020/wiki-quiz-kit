---
name: lint
description: LLM-driven semantic wiki audit. Checks contradictions, stale claims, missing concepts, orphan clusters, and duplicates. Use when user says "lint", "语义检查", "audit wiki", or "deep check".
---

# /lint — LLM Semantic Wiki Audit

## Purpose

Complement the deterministic `health-check.ps1` with LLM-powered semantic analysis. Tier 1 (health-check) catches structural problems. Tier 2 (/lint) catches meaning-level problems.

Trigger: "lint", "语义检查", "audit wiki", "deep check", "run lint"

## Execution

### Step 1: Gather context

Read:
- `wiki/purpose.md` — what this wiki is for
- `wiki/overview.md` — current state snapshot
- `wiki/log.md` — recent activity

### Step 2: Sample wiki pages

Read a representative sample:
- 5-10 permanent notes (spread across topics)
- 3-5 literature notes
- 2-3 MOC pages

The LLM decides which pages to read based on overview.md topic distribution and recent log activity.

### Step 3: Semantic checks

For each of the following, find concrete issues with page references:

**Contradictions:**
Two pages make conflicting factual claims. Example: `page-A` says "X was released in 2023" but `page-B` says "X launched in 2024."

**Stale claims:**
A page asserts something that a more recent source corrects or refines. Check `sources[]` dates and cross-reference with newer literature notes.

**Missing concepts:**
A term or concept appears frequently across pages (in wikilinks, in prose) but lacks its own permanent note.

**Orphan clusters:**
A group of pages heavily interlinked with each other, but with no links to the rest of the wiki. These may represent knowledge that should be integrated.

**Duplicates:**
Two pages covering substantially the same idea under different titles. Flag for potential merge.

### Step 4: Generate report

Write `wiki/lint-{date}.md`:

```markdown
---
type: lint
date: "YYYY-MM-DD"
issues_found: N
---
# Lint Report — {date}

## Contradictions
- `page-A` vs `page-B`: ...

## Stale Claims
- ...

## Missing Concepts
- ...

## Orphan Clusters
- ...

## Duplicates
- ...

## Recommendations
_(actionable next steps)_
```

### Step 5: Log and report

Append to `wiki/log.md`:
```
## [YYYY-MM-DD HH:MM] lint | N issues found
```

Present a summary to the user. Ask which issues to fix.

## Design note

This is complementary to `health-check.ps1`, not a replacement. health-check runs on every compile (deterministic, zero token cost). /lint runs on demand (LLM-powered, semantic depth).
