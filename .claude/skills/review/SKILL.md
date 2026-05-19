---
name: review
description: 知识复习测验 — 从知识库题库中选题，生成交互式 HTML 测验页面。支持随机出题、指定主题出题、错题复习。Use when user says "复习", "出题", "测验", "quiz", "test me", "考考我", "random quiz", "复习 FDE", "考一下 transformer", or any request to review/test knowledge.
---

# /review — Knowledge Review Quiz

## Purpose

Read questions from the project's `questions/` directory, select and shuffle, render an interactive HTML quiz. Zero network dependency — everything runs locally.

## Trigger

- "复习"、"出题"、"测验"、"quiz"、"test me"、"考考我"
- "随机出题"、"random quiz"、"来几道题"
- "复习 FDE"、"考一下 transformer"、"出几道 LLM 的题"
- "错题复习"、"只做错题"、"review mistakes"

## Execution

### Step 0: Ensure question bank exists

Check `questions/` directory exists and contains at least 5 `.md` question files.
If not, prompt user to run `/ingest` to generate questions first.

### Step 1: Parse parameters

Extract from user input:
- **Topic filter**: FDE / LLM / Agent / RAG / Ontology / LangChain / ETL / Adoption. No filter = all topics
- **Question count**: Default 10
- **Mode**: Random / wrong-answer-review (reads wrong answer IDs from localStorage)
- **Difficulty**: Default mixed, supports easy/medium/hard/mixed

### Step 2: Read question bank

```bash
Get-ChildItem "questions/*.md" -Exclude "INDEX.md"
```

Read each question file, parse the `topic` field from frontmatter.

### Step 3: Filter and select

1. Filter by topic if specified
2. For wrong-answer mode, keep only questions whose IDs are in the wrong-answer list
3. Randomly select N questions (if fewer available, use all and inform user)
4. Shuffle option order (A/B/C/D labels stay, content is randomized)

### Step 4: Render HTML

Read `quiz-template.html` from this skill directory, replace placeholders:

| Placeholder | Replacement |
|-------------|-------------|
| `{{QUIZ_TITLE}}` | Quiz title (e.g. "FDE 知识复习 · 10 题") |
| `{{QUIZ_SLUG}}` | Unique slug for localStorage key |
| `{{TOTAL}}` | Total question count |
| `{{QUESTIONS_JSON}}` | JSON array of all questions (question, options, answer, explanation, source, topic) |
| `{{TOPICS}}` | Topic filter tag HTML |

QUESTIONS_JSON format:
```json
[
  {
    "id": "fde-kpi-1",
    "topic": "FDE",
    "question": "FDE 战略的核心 KPI 是什么？",
    "options": ["降低定制成本", "保持合同规模增长", "提高用户活跃度", "降低边际成本"],
    "answer": 1,
    "explanation": "Bob McGrew 明确指出：FDE 战略与 SaaS PMF 的度量逻辑相反...",
    "source": "fde-kpi-is-contract-growth-not-cost-reduction"
  }
]
```

### Step 5: Save and present

Save to `output/quiz-[topic]-[date].html`. Open in browser.

## Design Spec

Uses paper-ink design tokens (same `:root` variables as plan-writer):

| Token | Value | Usage |
|-------|-------|-------|
| `--correct` | `#5C8D4A` | Correct answer |
| `--incorrect` | `#D4726A` | Wrong answer flash |
| `--correct-bg` | `rgba(92,141,74,0.06)` | Correct card background |

Interaction rules:
- Click option → immediate verdict, cannot change
- Correct: option turns green + explanation slides down (warm orange left border)
- Wrong: option briefly flashes red → correct option highlighted green + explanation slides out
- Progress dots clickable to jump to any question
- Finish panel: accuracy + per-topic breakdown + [New Set] [Review Wrong]
- Wrong answer IDs persisted to localStorage, survives sessions

## Reference

- `quiz-template.html` — Quiz HTML template (paper-ink design), in this skill directory
