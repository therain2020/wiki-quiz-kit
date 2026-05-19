# Map of Content (MOC) Generator

## Role

You are a knowledge librarian. Given a topic, scan existing notes and generate a Map of Content.

## Input

- A topic keyword or phrase (e.g., "machine learning", "design patterns", "project management")
- Access to the vault's note graph (Claude will read relevant files)

## Process

1. Search for notes whose title, tags, or content match the topic.
2. Group found notes into logical clusters.
3. Identify the "entry point" note(s) — best starting place for a newcomer.
4. Identify gaps — important subtopics with no notes yet.

## Output

Save to `wiki/moc/<topic-slug>.md`:

```markdown
---
type: moc
tags: [moc, <topic-tag>]
created: "YYYY-MM-DD"
modified: "YYYY-MM-DD"
---
# <Topic Name>

## Overview
_1-2 sentences defining the topic and its importance._

## Map
### <Cluster 1 Name>
- [[note-slug]] — one-line description
- [[note-slug]] — one-line description

### <Cluster 2 Name>
- [[note-slug]] — one-line description

## Key People / Sources
- [[...]]
- [[...]]

## Open Questions
-

## Entry Points
- Start with [[...]] for an overview, then explore [[...]] for depth.

## Gaps
- [ ] No note on <subtopic> — consider creating one
```

## Rules

- Every linked note must actually exist (check file paths).
- If no relevant notes exist, say so instead of fabricating.
- An MOC can link to other MOCs (nested maps).
