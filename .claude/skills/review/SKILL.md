---
name: review
description: 知识复习测验 — 从知识库题库中选题，生成交互式 HTML 测验页面。支持智能选题（新题/薄弱/错题/巩固/随机）、session 记录、状态回流。Use when user says "复习", "出题", "测验", "quiz", "test me", "考考我", "random quiz", "复习 FDE", "考一下 transformer", or any request to review/test knowledge.
---

# /review — Knowledge Review Quiz

## Purpose

Read questions from `questions/`, select based on state from `state/`, render interactive HTML quiz with session recording. After quiz, session JSON flows back through `sessions/` → `state/` update.

## Trigger

- "复习"、"出题"、"测验"、"quiz"、"test me"、"考考我"
- "随机出题"、"random quiz"、"来几道题"
- "复习 FDE"、"考一下 transformer"、"出几道 LLM 的题"
- "错题复习"、"只做错题"、"review mistakes"
- "巩固 FDE"、"新题"
- "记录结果"、"更新状态" (post-quiz state回流)

## Execution

### Step 0: Ensure question bank exists

Check `questions/INDEX.md` exists and contains at least one topic with ≥1 question. If not, prompt user to run `/ingest` to generate questions first.

### Step 1: Parse parameters

Extract from user input:
- **Topic filter**: FDE / LLM / Agent / etc. No filter = all topics
- **Question count**: Default 10
- **Mode**: 
  - `default` — 新题40% + 薄弱30% + 随机30%
  - `new` — 只选 attempts=0 的题
  - `wrong` — 只选 last_result="wrong" 的题
  - `consolidate` — 只选 correct/attempts < 0.8 且 attempts ≥ 1 的题
  - `random` — 纯随机（和旧行为一致）
- **Difficulty**: Default mixed, supports easy/medium/hard/mixed

### Step 2: Load question index and states

Read `wiki/purpose.md` for review priority context (which topics matter most).
Read `questions/INDEX.md` to enumerate available topics and question IDs.

Read all `state/*.json` files to build in-memory state map:
```json
{
  "fde-kpi-1": {"attempts": 3, "correct": 1, "wrong": 2, "last_result": "wrong", "last_attempt": "2026-05-19"}
}
```

Questions without a state file are treated as new (attempts=0, correct=0, wrong=0, last_result="", last_attempt="").

### Step 3: Filter and select

1. Filter by topic if specified (from INDEX.md)
2. Apply mode rules to score/rank questions:
   - `new`: keep only attempts=0
   - `wrong`: keep only last_result="wrong"
   - `consolidate`: keep only 0 < correct/attempts < 0.8
   - `default`: 40% new + 30% weakest (lowest correct/attempts) + 30% random from remaining
3. If a mode yields fewer questions than requested, fill with random to hit count (or use all available)
4. Shuffle option order (A/B/C/D labels stay, content is randomized)

### Step 4: Render HTML

Read `quiz-template.html` from this skill directory, replace placeholders:

| Placeholder | Replacement |
|-------------|-------------|
| `{{QUIZ_TITLE}}` | Quiz title (e.g. "FDE 知识复习 · 10 题") |
| `{{QUIZ_SLUG}}` | Unique slug for localStorage key (progress recovery) |
| `{{SESSION_ID}}` | `{date}-{time}` e.g. `2026-05-19-153000` |
| `{{SESSION_DATE}}` | ISO timestamp |
| `{{MODE}}` | Selection mode string (for session metadata) |
| `{{TOTAL}}` | Total question count |
| `{{QUESTIONS_JSON}}` | JSON array of all questions |
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

When the user clicks "查看结果", the session JSON is automatically copied to clipboard. The user simply pastes (Ctrl+V) into Claude, which recognizes the session JSON and triggers state回流.

### Step 6: State回流 (triggered by user after quiz)

When user says "记录结果" / "更新状态" and provides the session file or clipboard content:

1. Read session JSON from `sessions/{session_id}.json` (or parse clipboard content and save to sessions/)
2. For each answer in the session:
   - Read current `state/{id}.json` (or init defaults if missing)
   - Update: `attempts += 1`, `correct += 1` (if result="correct"), `wrong += 1` (if result="wrong")
   - Set `last_result`, `last_attempt`
3. Write all state files concurrently (one per question)
4. Verify: re-read all written state files, confirm counts match expected
5. Report: "Updated N question states. X correct, Y wrong this session. Overall accuracy: Z%."
6. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD HH:MM] review | {topic} · {total} questions | {score}/{total}
   ```
7. Update `wiki/overview.md` mastery data for affected topics.

If any state file write fails, report which ones and suggest re-running.

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
- Finish panel: accuracy + per-topic breakdown + [New Set] [Download Session] [Copy to Clipboard]
- Session JSON contains all answers for state回流

## Reference

- `quiz-template.html` — Quiz HTML template (paper-ink design), in this skill directory
- `questions/INDEX.md` — Static question index (topic enumeration)
- `state/*.json` — Per-question attempt state
- `sessions/*.json` — Raw answer WAL
- `prompts/generate-questions.md` — Question generation prompt (/ingest Stage 5.5)
