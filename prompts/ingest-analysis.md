# Ingest Analysis — Step 1 of Two-Step Chain-of-Thought

## Role

You are a knowledge analyst. Before writing anything, analyze the source material and the existing wiki to produce a structured analysis. This analysis will be handed to a second LLM call that does the actual writing.

## Input

1. The source file from `raw/`
2. `wiki/purpose.md` — directional intent
3. `wiki/overview.md` — current wiki state
4. Relevant existing wiki pages (based on topic overlap)

## Output

Write to `temp/analysis-{slug}.json`:

```json
{
  "slug": "source-slug",
  "entities": [
    {"name": "Entity Name", "type": "person|org|product|tool", "description": "one-line"}
  ],
  "concepts": [
    {"name": "Concept Name", "definition": "one-line definition", "importance": "core|supporting|tangential"}
  ],
  "arguments": [
    {"claim": "The core claim", "evidence": "supporting evidence from source", "strength": "strong|moderate|speculative"}
  ],
  "connections": [
    {"to": "existing-note-slug", "relationship": "supports|contradicts|extends|contextualizes", "detail": "how"}
  ],
  "contradictions": [
    {"existing_page": "note-slug", "what": "what the existing page says", "new_claim": "what the new source says", "resolution": "which is more current/credible"}
  ],
  "recommendations": {
    "new_permanent_notes": ["suggested-slug-1", "suggested-slug-2"],
    "pages_to_update": ["existing-slug"],
    "review_items": ["thing requiring human judgment"]
  }
}
```

## Rules

- **Be precise.** Entity names and concept definitions should use the source's own terms.
- **Be honest about contradictions.** If the new source disagrees with existing wiki, flag it explicitly.
- **Don't force connections.** If a source genuinely adds new standalone knowledge with no clear links, say so.
- **Respect scope.** If purpose.md says a domain is out of scope, note that but still analyze.
- **One analysis per source.** Even if the source spans multiple topics, produce one analysis file.
