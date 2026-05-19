#!/usr/bin/env python3
"""Update per-question state from a session JSON file. Zero LLM cost.

Usage:
  python3 scripts/update-state.py path/to/session.json
  python3 scripts/update-state.py path/to/session.json --dry-run

The session JSON is the clipboard output from the quiz HTML.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = VAULT_ROOT / "state"
SESSIONS_DIR = VAULT_ROOT / "sessions"
LOG_FILE = VAULT_ROOT / "wiki" / "log.md"


def update(session_path, dry_run=False):
    session_path = Path(session_path)
    if not session_path.exists():
        print(f"ERROR: {session_path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        session = json.loads(session_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {session_path}: {e}", file=sys.stderr)
        sys.exit(1)

    answers = session.get("answers", [])
    if not answers:
        print("No answers in session. Nothing to update.")
        return

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy session to sessions/ if not already there
    dest = SESSIONS_DIR / session_path.name
    if not dest.exists() and not dry_run:
        dest.write_text(session_path.read_text(encoding='utf-8'))

    total = len(answers)
    correct = sum(1 for a in answers if a.get("result") == "correct")
    wrong = total - correct

    if dry_run:
        print(f"[DRY RUN] Would update {total} question states:")
    else:
        print(f"Updating {total} question states:")

    for a in answers:
        qid = a["id"]
        result = a.get("result", "wrong")

        # Load or init state
        state_file = STATE_DIR / f"{qid}.json"
        if state_file.exists():
            try:
                st = json.loads(state_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                st = {"attempts": 0, "correct": 0, "wrong": 0,
                      "last_result": "", "last_attempt": ""}
        else:
            st = {"attempts": 0, "correct": 0, "wrong": 0,
                  "last_result": "", "last_attempt": ""}

        st["attempts"] += 1
        if result == "correct":
            st["correct"] += 1
        else:
            st["wrong"] += 1
        st["last_result"] = result
        st["last_attempt"] = session.get("date", "")

        if dry_run:
            tag = "✓" if result == "correct" else "✗"
            print(f"  {tag} {qid} → attempts={st['attempts']} correct={st['correct']} wrong={st['wrong']}")
        else:
            state_file.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding='utf-8')
            tag = "✓" if result == "correct" else "✗"
            print(f"  {tag} {qid}")

    if not dry_run:
        # Verify all writes succeeded
        for a in answers:
            sf = STATE_DIR / f"{a['id']}.json"
            if not sf.exists():
                print(f"  ERROR: failed to write state for {a['id']}", file=sys.stderr)
            else:
                st = json.loads(sf.read_text(encoding='utf-8'))
                if st["attempts"] < 1:
                    print(f"  ERROR: state for {a['id']} has 0 attempts — write may have failed", file=sys.stderr)

    print(f"\nDone. {correct}/{total} correct this session.")


def main():
    parser = argparse.ArgumentParser(
        description="Update per-question state from a quiz session JSON file")
    parser.add_argument("session", help="Path to session JSON file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    args = parser.parse_args()

    update(args.session, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
