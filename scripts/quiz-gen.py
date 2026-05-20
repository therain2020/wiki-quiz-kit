#!/usr/bin/env python3
"""Generate quiz HTML from question bank. Zero LLM cost.

Usage:
  python3 scripts/quiz-gen.py                              all topics, 10 random
  python3 scripts/quiz-gen.py --tags llm                   llm only
  python3 scripts/quiz-gen.py --tags ontology,llm --count 5
  python3 scripts/quiz-gen.py --mode wrong                 last_result=wrong
  python3 scripts/quiz-gen.py --mode new                   unattempted
  python3 scripts/quiz-gen.py --mode consolidate           0 < accuracy < 80%
  python3 scripts/quiz-gen.py --difficulty hard
"""

import argparse
import json
import random
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

VAULT_ROOT = Path(__file__).resolve().parent.parent
BANK_FILE = VAULT_ROOT / "questions" / "bank.json"
STATE_DIR = VAULT_ROOT / "state"
TEMPLATE_FILE = VAULT_ROOT / ".claude" / "skills" / "review" / "quiz-template.html"
OUTPUT_DIR = VAULT_ROOT / "output"


def load_bank():
    if not BANK_FILE.exists():
        print(f"ERROR: {BANK_FILE} not found. Run /ingest first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(BANK_FILE.read_text(encoding="utf-8"))


def load_state(qid):
    sf = STATE_DIR / f"{qid}.json"
    if sf.exists():
        return json.loads(sf.read_text(encoding="utf-8"))
    return None


def filter_by_mode(pool, mode):
    """Filter questions by attempt state."""
    if mode == "random":
        return pool

    scored = []
    for q in pool:
        st = load_state(q["id"])
        if mode == "new" and st is None:
            scored.append((q, 0))
        elif mode == "wrong" and st and st.get("last_result") == "wrong":
            scored.append((q, st.get("wrong", 0)))
        elif mode == "consolidate" and st and st.get("attempts", 0) > 0:
            accuracy = st.get("correct", 0) / st["attempts"]
            if accuracy < 0.8:
                scored.append((q, accuracy))
        elif mode == "random" and st is None:
            scored.append((q, 0))

    if mode == "new":
        return [q for q, _ in scored]  # no sorting needed
    elif mode == "wrong":
        # Most wrong first
        scored.sort(key=lambda x: -x[1])
    elif mode == "consolidate":
        # Lowest accuracy first
        scored.sort(key=lambda x: x[1])

    return [q for q, _ in scored]


def select(pool, count):
    """Shuffle and pick count questions, shuffle options within each."""
    selected = pool[:]
    random.shuffle(selected)
    selected = selected[:min(count, len(selected))]

    for q in selected:
        opts = q["options"][:]
        correct = q["answer"]
        paired = [(o, i) for i, o in enumerate(opts)]
        random.shuffle(paired)
        q["options"] = [o for o, _ in paired]
        q["answer"] = next(i for i, (_, old_idx) in enumerate(paired) if old_idx == correct)
        # Normalize source field
        if "source" not in q and "sources" in q:
            q["source"] = q["sources"][0] if isinstance(q["sources"], list) and q["sources"] else ""

    return selected


def render(pool, pick, tags_str, mode, topic_tags):
    """Render HTML from template."""
    template = TEMPLATE_FILE.read_text(encoding="utf-8")

    today = datetime.now().strftime("%Y-%m-%d")
    date_time = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    slug = f"{tags_str or 'all'}-{today}"
    title_parts = ["知识复习"]
    if tags_str:
        title_parts.append(tags_str)
    title_parts.append(f"{pick} 题")
    title = " · ".join(title_parts)

    bank_json = json.dumps(pool, ensure_ascii=False)

    tags_html = "".join(
        f'<span class="tag on">{t}</span>' for t in topic_tags
    ) if topic_tags else ""

    html = template.replace("{{QUIZ_TITLE}}", title)
    html = html.replace("{{QUIZ_SLUG}}", slug)
    html = html.replace("{{SESSION_ID}}", f"s{today}-{tags_str or 'all'}-{pick}")
    html = html.replace("{{SESSION_DATE}}", today)
    html = html.replace("{{MODE}}", mode)
    html = html.replace("{{TOTAL}}", str(pick))
    html = html.replace("{{BANK_JSON}}", bank_json)
    html = html.replace("{{TOPICS}}", tags_html)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"quiz-{tags_str or 'all'}-{date_time}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path, bank_json


def main():
    parser = argparse.ArgumentParser(description="Generate quiz HTML from question bank")
    parser.add_argument("--tags", default="", help="Topic filter, comma-separated (e.g. llm,ontology)")
    parser.add_argument("--count", type=int, default=10, help="Questions per round (default: 10)")
    parser.add_argument("--mode", choices=["random", "new", "wrong", "consolidate"], default="random")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser")
    args = parser.parse_args()

    # 1. Load bank
    bank = load_bank()

    # 2. Filter by tags
    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    if tag_list:
        pool = [q for q in bank if q.get("topic", "") in tag_list]
    else:
        pool = list(bank)
        tag_list = list(set(q.get("topic", "") for q in bank))

    if not pool:
        print(f"No questions found for tags: {args.tags}", file=sys.stderr)
        sys.exit(1)

    # 3. Filter by difficulty
    if args.difficulty:
        pool = [q for q in pool if q.get("difficulty") == args.difficulty]
        if not pool:
            print(f"No questions with difficulty: {args.difficulty}", file=sys.stderr)
            sys.exit(1)

    # 4. Filter by mode (state-based)
    pool = filter_by_mode(pool, args.mode)
    if not pool:
        print(f"No questions match mode: {args.mode}", file=sys.stderr)
        sys.exit(1)

    # 5. Select and shuffle
    pick = min(args.count, len(pool))
    selected = select(pool, pick)

    # 6. Render + open
    out_path, _ = render(pool, pick, args.tags.replace(",", "-"), args.mode, tag_list)

    size_kb = out_path.stat().st_size / 1024
    print(f"{out_path}  ({size_kb:.0f}KB, bank={len(pool)}, pick={pick}, mode={args.mode})")

    if not args.no_open:
        webbrowser.open(str(out_path))
        # Auto-start background watcher to catch session download
        watcher = VAULT_ROOT / "scripts" / "watch-sessions.py"
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [sys.executable, str(watcher)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **kwargs
        )
        print("  (watcher auto-started, stops when terminal closes)")


if __name__ == "__main__":
    main()
