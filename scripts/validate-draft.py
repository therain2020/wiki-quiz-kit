#!/usr/bin/env python3
"""Validate question draft JSON before writing. Structural gate for Stage 5.5.

Usage:
  python3 scripts/validate-draft.py temp/draft-quantagent-learning.json
  python3 scripts/validate-draft.py temp/draft-xxx.json --write    # validate + write
  python3 scripts/validate-draft.py temp/draft-xxx.json --json     # JSON report output
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

VAULT_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = VAULT_ROOT / "questions"
BANK_FILE = QUESTIONS_DIR / "bank.json"
INDEX_FILE = QUESTIONS_DIR / "INDEX.md"

REQUIRED_FIELDS = ["id", "topic", "difficulty", "sources", "question", "options", "answer", "explanation"]
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def validate_draft(draft_path):
    """Validate a question draft JSON. Returns (ok, errors, draft)."""
    errors = []
    dp = Path(draft_path)
    if not dp.exists():
        return False, [f"File not found: {draft_path}"], []

    try:
        draft = json.loads(dp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"], []

    if not isinstance(draft, list):
        return False, ["Draft must be a JSON array of question objects"], []

    if len(draft) == 0:
        return False, ["Draft array is empty"], []

    # Load existing IDs from bank.json for collision check
    existing_ids = set()
    if BANK_FILE.exists():
        bank = json.loads(BANK_FILE.read_text(encoding="utf-8"))
        existing_ids = {q["id"] for q in bank}

    seen_ids = set()

    for i, q in enumerate(draft):
        idx = f"[{i}] {q.get('id', 'MISSING-ID')}"

        # 1. All required fields non-empty
        for field in REQUIRED_FIELDS:
            if field not in q:
                errors.append(f"{idx}: missing required field '{field}'")
            elif q[field] is None or (isinstance(q[field], str) and not q[field].strip()):
                errors.append(f"{idx}: field '{field}' is empty")
            elif isinstance(q[field], list) and len(q[field]) == 0:
                errors.append(f"{idx}: field '{field}' is empty list")

        if any(f not in q for f in ["id", "topic", "sources"]):
            continue  # can't validate further without these

        # 2. id format: {topic}-{source}-{n}
        id_parts = q["id"].split("-")
        if len(id_parts) < 3:
            errors.append(f"{idx}: id '{q['id']}' does not match format '{{topic}}-{{source}}-{{n}}'")

        # 3. Duplicate ID within draft
        if q["id"] in seen_ids:
            errors.append(f"{idx}: duplicate id '{q['id']}' within draft")
        seen_ids.add(q["id"])

        # 4. ID collision with existing bank
        if q["id"] in existing_ids:
            errors.append(f"{idx}: id '{q['id']}' already exists in bank.json")

        # 5. Difficulty valid
        if q.get("difficulty", "") not in VALID_DIFFICULTIES:
            errors.append(f"{idx}: difficulty '{q.get('difficulty', '')}' not in {VALID_DIFFICULTIES}")

        # 6. options is list with >= 2 items
        options = q.get("options", [])
        if isinstance(options, list) and len(options) < 2:
            errors.append(f"{idx}: options has {len(options)} items, need at least 2")

        # 7. answer is valid index into options
        answer = q.get("answer")
        if isinstance(answer, int) and isinstance(options, list) and len(options) > 0:
            if answer < 0 or answer >= len(options):
                errors.append(f"{idx}: answer index {answer} out of range for {len(options)} options")
        elif isinstance(answer, int) and isinstance(options, list) and len(options) == 0:
            errors.append(f"{idx}: answer is {answer} but options is empty")

        # 8. sources reference real notes
        if isinstance(q.get("sources"), list):
            for src in q["sources"]:
                found = any(
                    (VAULT_ROOT / d / f"{src}.md").exists()
                    for d in ["wiki/permanent", "wiki/literature"]
                )
                if not found:
                    errors.append(f"{idx}: source '{src}' not found in wiki/permanent or wiki/literature")

    return len(errors) == 0, errors, draft


def write_files(draft_path):
    """Validate draft, then write .md files, update INDEX.md, and merge bank.json."""
    ok, errors, draft = validate_draft(draft_path)
    if not ok:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        # Rename draft to REJECTED
        rejected = Path(draft_path).with_suffix(".json").parent / (
            Path(draft_path).stem + "_REJECTED.json"
        )
        Path(draft_path).rename(rejected)
        print(f"Draft rejected → {rejected}", file=sys.stderr)
        return False

    print(f"Validation passed: {len(draft)} questions valid")

    created = datetime.now().strftime("%Y-%m-%d")
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Write .md files
    for q in draft:
        options_text = "\n".join(f"{chr(65 + i)}. {opt}" for i, opt in enumerate(q["options"]))
        answer_letter = chr(65 + q["answer"])
        sources_yaml = json.dumps(q["sources"])

        md = f"""---
type: question
id: {q["id"]}
topic: {q["topic"]}
difficulty: {q["difficulty"]}
sources: {sources_yaml}
created: "{created}"
---

# {q["question"]}

{options_text}

**答案:** {answer_letter}

**解析:** {q["explanation"]}
"""
        (QUESTIONS_DIR / f"{q['id']}.md").write_text(md, encoding="utf-8")
        print(f"  OK  {q['id']}.md")

    # Update bank.json
    bank = json.loads(BANK_FILE.read_text(encoding="utf-8")) if BANK_FILE.exists() else []
    for q in draft:
        bank.append({
            "id": q["id"],
            "topic": q["topic"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "options": q["options"],
            "answer": q["answer"],
            "explanation": q["explanation"],
            "source": q["sources"][0],
        })
    BANK_FILE.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"bank.json: {len(bank)} total ({len(draft)} new)")

    # Update INDEX.md
    update_index(draft)
    return True


def update_index(draft):
    """Add new questions to INDEX.md."""
    if not INDEX_FILE.exists():
        return

    index_text = INDEX_FILE.read_text(encoding="utf-8")
    topics_in_draft = sorted(set(q["topic"] for q in draft))

    for topic in topics_in_draft:
        if f"## {topic}" not in index_text:
            # Insert new topic section before the last existing section or at end
            section = f"\n## {topic}\n\n| ID | Difficulty | Sources |\n|----|-----------|---------|\n"
            topic_questions = [q for q in draft if q["topic"] == topic]
            for q in topic_questions:
                src = q["sources"][0] if q["sources"] else ""
                section += f"| {q['id']} | {q['difficulty']} | {src} |\n"
            # Insert after Statistics table
            stats_end = index_text.find("\n##", index_text.find("## Statistics") + 1)
            if stats_end == -1:
                stats_end = len(index_text)
            index_text = index_text[:stats_end] + section + index_text[stats_end:]
        else:
            # Topic exists, add new rows
            topic_questions = [q for q in draft if q["topic"] == topic]
            topic_start = index_text.find(f"## {topic}")
            topic_end = index_text.find("\n##", topic_start + 1)
            if topic_end == -1:
                topic_end = len(index_text)
            topic_section = index_text[topic_start:topic_end]
            for q in topic_questions:
                if q["id"] not in topic_section:
                    src = q["sources"][0] if q["sources"] else ""
                    new_row = f"| {q['id']} | {q['difficulty']} | {src} |\n"
                    # Insert after header row (second |----| line)
                    insert_at = topic_section.find("\n", topic_section.find("|----|") + 1)
                    topic_section = topic_section[:insert_at] + "\n" + new_row + topic_section[insert_at:]
            index_text = index_text[:topic_start] + topic_section + index_text[topic_end:]

    # Update Statistics table
    all_topics = {}
    for m in __import__("re").finditer(r'^##\s+(\w[\w-]*)$', index_text, __import__("re").MULTILINE):
        t = m.group(1).strip()
        if t not in ("Statistics",):
            count = len(__import__("re").findall(rf'^\|\s*{t}-', index_text, __import__("re").MULTILINE))
            all_topics[t] = count

    import re
    stats_pattern = re.compile(r'(## Statistics\n\n\| Topic \| Count \|\n\|-------\|-------\|\n)(.*?)(\n\n##)', re.DOTALL)
    new_stats_rows = "\n".join(f"| {t} | {c} |" for t, c in sorted(all_topics.items()))
    index_text = stats_pattern.sub(rf'\1{new_stats_rows}\3', index_text)

    INDEX_FILE.write_text(index_text, encoding="utf-8")
    print(f"INDEX.md updated")


def main():
    parser = argparse.ArgumentParser(description="Validate question draft JSON")
    parser.add_argument("draft", help="Path to draft JSON file")
    parser.add_argument("--write", action="store_true", help="Validate and write files on pass")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    ok, errors, draft = validate_draft(args.draft)

    if args.write:
        if ok:
            write_files(args.draft)
        else:
            print(f"Validation failed with {len(errors)} error(s). Use without --write to see details.",
                  file=sys.stderr)
            sys.exit(1)
    elif args.json:
        print(json.dumps({"valid": ok, "questionCount": len(draft), "errors": errors},
                         ensure_ascii=False, indent=2))
    else:
        if ok:
            print(f"OK  {len(draft)} questions valid — ready to write")
        else:
            print(f"FAIL  {len(errors)} error(s):")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
