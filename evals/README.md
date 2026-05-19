# Evals — Eval Driven Development for Knowledge Compilation

Define what "correct" compilation looks like by creating labeled eval cases.
Each case pairs a raw source with its expected wiki output.

This follows the EDD methodology used by OpenAI's FDE team for LLM-powered applications.

## Structure

```
evals/
├── README.md
└── cases/
    └── sample/
        ├── source.md    # Raw input
        ├── expected.md  # Expected compilation output
        └── meta.json    # {"expectedType":"permanent","expectFail":false}
```

## Creating Your Own Cases

1. Pick a raw note that you have manually compiled to a wiki note
2. Copy raw → `evals/cases/<case-name>/source.md`
3. Copy verified wiki output → `evals/cases/<case-name>/expected.md`
4. Create `meta.json` with `expectedType` and `expectFail`
5. Run `.\scripts\eval.ps1 -Verbose`

## Checks

| # | Check | Description |
|---|-------|-------------|
| 1 | Frontmatter | Required fields per note type |
| 2 | Body | Non-trivial content beyond frontmatter |
| 3 | Links | All [[wikilinks]] resolve |

## EDD Cycle

```
compile → eval → fail → fix → re-compile → pass
```

eval.ps1 exits non-zero on failure. compile.ps1 -Process mode triggers eval gate.
