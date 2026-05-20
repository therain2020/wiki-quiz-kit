#!/usr/bin/env python3
"""Knowledge Base Health Check — 8 checks, cross-platform.

Usage:
  python3 scripts/health-check.py                # summary only
  python3 scripts/health-check.py --verbose       # per-issue details
  python3 scripts/health-check.py --strict        # include symmetric link check
  python3 scripts/health-check.py --json          # JSON output for pipeline consumption
"""

import argparse
import json
import os
import re
import sys
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

# ── Terminal colors ──────────────────────────────────────────
CYAN = "\033[36m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"
GRAY = "\033[90m"; RESET = "\033[0m"; BOLD = "\033[1m"

def color(c, text):
    return f"{c}{text}{RESET}"

VAULT_ROOT = Path(__file__).resolve().parent.parent

# ── Helpers ──────────────────────────────────────────────────

def get_markdown_files(under=None):
    """Recursively find .md files, excluding non-vault directories."""
    base = VAULT_ROOT / under if under else VAULT_ROOT
    if not base.exists():
        return []
    files = []
    for f in base.rglob("*.md"):
        s = str(f)
        if any(x in s for x in [".obsidian", ".trash", "templates", "prompts", "evals"]):
            continue
        if ".claude/skills" in s.replace("\\", "/"):
            continue
        if f.parent == VAULT_ROOT:
            continue
        files.append(f)
    return files


def parse_frontmatter(content):
    """Extract YAML frontmatter as dict using yaml.safe_load."""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = yaml.safe_load(parts[1])
    return fm if isinstance(fm, dict) else {}


def get_note_body(content):
    """Return content after frontmatter block."""
    m = re.search(r'^---\s*\n.*?\n---\s*\n(.*)', content, re.DOTALL)
    return m.group(1).strip() if m else content.strip()


def extract_wikilinks(content):
    """Return list of wikilink targets."""
    links = []
    for m in re.finditer(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]', content):
        target = m.group(1).strip()
        if not target.startswith("http") and not re.search(r'\.(png|jpg|jpeg|gif|svg|pdf)$', target):
            links.append(target)
    return links


def resolve_note_path(link_target):
    """Find the .md file matching a wikilink target."""
    candidate = VAULT_ROOT / f"{link_target}.md"
    if candidate.exists():
        return candidate
    for f in get_markdown_files():
        if f.stem == link_target:
            return f
    return None


def relative_path(full_path):
    """Convert absolute path to vault-relative path."""
    try:
        return str(full_path.relative_to(VAULT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(full_path).replace("\\", "/")

# ── Check 1: Broken Wiki-Links ─────────────────────────────

def check_broken_links():
    results = []
    for f in get_markdown_files():
        content = f.read_text(encoding="utf-8")
        for link in extract_wikilinks(content):
            if not resolve_note_path(link):
                results.append({
                    "type": "error", "check": "broken-link",
                    "file": relative_path(f), "target": link,
                    "message": f"Broken link: [[{link}]]"
                })
    return results

# ── Check 2: Orphan Notes ──────────────────────────────────

def check_orphan_notes():
    results = []
    all_files = get_markdown_files()
    all_paths = {str(f) for f in all_files}

    referenced = set()
    for f in all_files:
        content = f.read_text(encoding="utf-8")
        for link in extract_wikilinks(content):
            resolved = resolve_note_path(link)
            if resolved:
                referenced.add(str(resolved))

    wiki_files = [f for f in all_files
                  if "/wiki/" in str(f).replace("\\", "/")
                  and "/wiki/daily/" not in str(f).replace("\\", "/")
                  and "/wiki/moc/" not in str(f).replace("\\", "/")]

    cutoff = datetime.now() - timedelta(hours=24)
    for f in wiki_files:
        if str(f) not in referenced:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                results.append({
                    "type": "warning", "check": "orphan",
                    "file": relative_path(f),
                    "message": "Orphan note: no incoming links"
                })
    return results

# ── Check 3: Empty Files ───────────────────────────────────

def check_empty_files():
    results = []
    for f in get_markdown_files(under="wiki"):
        content = f.read_text(encoding="utf-8")
        body = get_note_body(content)
        if not body:
            results.append({
                "type": "error", "check": "empty-file",
                "file": relative_path(f),
                "message": "Empty file: no body content beyond frontmatter"
            })
    return results

# ── Check 4: Frontmatter Consistency ───────────────────────

REQUIRED_FIELDS = {
    "permanent":  ["type", "tags", "created"],
    "literature": ["type", "sources", "created"],
    "daily":      ["type", "created"],
    "moc":        ["type", "tags", "created"],
    "fleeting":   ["type", "created"],
    "meeting":    ["type", "date"],
    "video":      ["type", "sources", "created"],
    "article":    ["type", "sources", "created"],
    "question":   ["type", "topic", "sources", "difficulty", "created"],
    "log":        ["type", "created"],
    "lint":       ["type", "date"],
}

def check_frontmatter():
    results = []
    for f in get_markdown_files():
        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        note_type = fm.get("type")

        if not note_type:
            results.append({
                "type": "error", "check": "frontmatter",
                "file": relative_path(f),
                "message": "Missing 'type' field in frontmatter"
            })
            continue

        if note_type not in REQUIRED_FIELDS:
            continue

        for field in REQUIRED_FIELDS[note_type]:
            if field not in fm or fm[field] == "":
                results.append({
                    "type": "error", "check": "frontmatter",
                    "file": relative_path(f),
                    "message": f"Missing required field '{field}' for type '{note_type}'"
                })
    return results

# ── Check 5: Symmetric Links (--strict only) ───────────────

def check_symmetric_links():
    results = []
    files = get_markdown_files(under="wiki/permanent")
    file_set = {str(f) for f in files}

    for f in files:
        content = f.read_text(encoding="utf-8")
        for link in extract_wikilinks(content):
            resolved = resolve_note_path(link)
            if resolved and str(resolved) in file_set:
                target_content = resolved.read_text(encoding="utf-8")
                back_links = extract_wikilinks(target_content)
                # Normalize: check if f's stem appears as a link in the target
                if f.stem not in back_links:
                    results.append({
                        "type": "warning", "check": "symmetric-link",
                        "file": relative_path(f),
                        "target": link,
                        "message": f"Symmetric link: [[{f.stem}]] links to [[{link}]] but not back"
                    })
    return results

# ── Check 6: Question Bank Integrity ────────────────────────

def check_question_bank():
    results = []
    q_dir = VAULT_ROOT / "questions"
    if not q_dir.exists():
        return results

    # Scan question files
    topics = {}
    q_ids = {}
    for qf in sorted(q_dir.glob("*.md")):
        if qf.name == "INDEX.md":
            continue
        content = qf.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        topic = fm.get("topic", "(unknown)")
        topics[topic] = topics.get(topic, 0) + 1
        qid = fm.get("id", qf.stem)
        q_ids[qid] = qf

        # Validate body format
        if not re.search(r'\*\*答案:\*\*\s*[A-D]', content):
            results.append({
                "type": "error", "check": "question-bank",
                "file": relative_path(qf),
                "message": "Missing '**答案:** X' in question body"
            })
        if not re.search(r'\*\*解析:\*\*', content):
            results.append({
                "type": "error", "check": "question-bank",
                "file": relative_path(qf),
                "message": "Missing '**解析:**' section in question body"
            })

        # Count options
        opt_count = len(re.findall(r'^[A-D]\.\s', content, re.MULTILINE))
        if opt_count < 2:
            results.append({
                "type": "error", "check": "question-bank",
                "file": relative_path(qf),
                "message": f"Fewer than 2 options found (got {opt_count})"
            })

        # Source link check
        is_deprecated = fm.get("deprecated", "").lower() == "true"
        src_list = []
        raw_src = fm.get("sources", fm.get("source", ""))
        if isinstance(raw_src, list):
            src_list = [str(s) for s in raw_src]
        elif raw_src:
            # Legacy string format: single value or "[a, b]"
            m_arr = re.match(r'^\[(.+)\]$', raw_src)
            if m_arr:
                src_list = [s.strip().strip('"').strip("'") for s in m_arr.group(1).split(",") if s.strip()]
            else:
                src_list = [raw_src.strip()]

        for src in src_list:
            found = any((VAULT_ROOT / d / f"{src}.md").exists()
                       for d in ["wiki/permanent", "wiki/literature"])
            if not found:
                level = "info" if is_deprecated else "error"
                results.append({
                    "type": level, "check": "question-bank",
                    "file": relative_path(qf),
                    "message": f"Source '{src}' not found in wiki/"
                })

    # INDEX consistency
    index_file = q_dir / "INDEX.md"
    if index_file.exists():
        index_content = index_file.read_text(encoding="utf-8")
        index_topics = {}
        for m in re.finditer(r'^##\s+(.+)$', index_content, re.MULTILINE):
            index_topics[m.group(1).strip()] = True

        index_ids = {}
        for m in re.finditer(r'^\|\s*([\w-]+)\s*\|', index_content, re.MULTILINE):
            idx_id = m.group(1).strip()
            if not re.match(r'^[a-zA-Z0-9][\w-]+$', idx_id):
                continue
            if idx_id in {"ID", "Topic", "Count", "Difficulty", "Sources", "Source"}:
                continue
            if idx_id in index_topics:
                continue
            index_ids[idx_id] = True

        for t in topics:
            if t not in index_topics:
                results.append({
                    "type": "warning", "check": "question-bank",
                    "file": "questions/INDEX.md",
                    "message": f"Topic '{t}' has questions but not listed in INDEX.md"
                })

        for qid in q_ids:
            if index_ids and qid not in index_ids:
                results.append({
                    "type": "warning", "check": "question-bank",
                    "file": "questions/INDEX.md",
                    "message": f"Question '{qid}' not listed in INDEX.md"
                })

        for idx_id in index_ids:
            if idx_id not in q_ids:
                results.append({
                    "type": "error", "check": "question-bank",
                    "file": "questions/INDEX.md",
                    "message": f"INDEX.md lists '{idx_id}' but file questions/{idx_id}.md does not exist"
                })

    # bank.json consistency
    bank_file = q_dir / "bank.json"
    if not bank_file.exists():
        results.append({
            "type": "warning", "check": "question-bank",
            "file": "questions/bank.json",
            "message": "bank.json does not exist. /review performance will degrade."
        })
    else:
        try:
            bank = json.loads(bank_file.read_text(encoding="utf-8"))
            bank_ids = {}
            for bq in bank:
                bid = bq.get("id")
                if not bid:
                    continue
                bank_ids[bid] = bq
                if bid not in q_ids:
                    results.append({
                        "type": "error", "check": "question-bank",
                        "file": "questions/bank.json",
                        "message": f"bank.json lists '{bid}' but file questions/{bid}.md does not exist"
                    })
            for qid in q_ids:
                if qid not in bank_ids:
                    results.append({
                        "type": "warning", "check": "question-bank",
                        "file": "questions/bank.json",
                        "message": f"Question '{qid}' has .md file but not in bank.json"
                    })
            # Content consistency
            for qid in q_ids:
                if qid not in bank_ids:
                    continue
                bq = bank_ids[qid]
                qf = q_ids[qid]
                q_content = qf.read_text(encoding="utf-8")
                q_fm = parse_frontmatter(q_content)
                q_topic = q_fm.get("topic", "")
                q_diff = q_fm.get("difficulty", "")
                b_topic = bq.get("topic", "")
                b_diff = bq.get("difficulty", "")
                if q_topic != b_topic:
                    results.append({
                        "type": "error", "check": "question-bank",
                        "file": f"questions/{qid}.md",
                        "message": f"Topic mismatch: .md='{q_topic}', bank.json='{b_topic}'"
                    })
                if q_diff != b_diff:
                    results.append({
                        "type": "error", "check": "question-bank",
                        "file": f"questions/{qid}.md",
                        "message": f"Difficulty mismatch: .md='{q_diff}', bank.json='{b_diff}'"
                    })
        except json.JSONDecodeError as e:
            results.append({
                "type": "error", "check": "question-bank",
                "file": "questions/bank.json",
                "message": f"Cannot parse bank.json: {e}"
            })

    return results

# ── Check 7: State Integrity ───────────────────────────────

def check_state_integrity():
    results = []
    state_dir = VAULT_ROOT / "state"
    sess_dir = VAULT_ROOT / "sessions"

    # Build known question ID set
    known_qids = {}
    q_dir = VAULT_ROOT / "questions"
    if q_dir.exists():
        for qf in q_dir.glob("*.md"):
            if qf.name == "INDEX.md":
                continue
            content = qf.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            qid = fm.get("id", qf.stem)
            known_qids[qid] = True

    if not sess_dir.exists() or not any(sess_dir.iterdir()):
        # Check state→question links even without sessions
        if state_dir.exists():
            for sf in state_dir.glob("*.json"):
                qid = sf.stem
                if known_qids and qid not in known_qids:
                    results.append({
                        "type": "error", "check": "state-integrity",
                        "file": f"state/{sf.name}",
                        "message": f"State file for '{qid}' but question does not exist"
                    })
        return results

    # Replay all sessions to compute expected state
    expected = {}
    for sf in sorted(sess_dir.glob("*.json")):
        try:
            sdata = json.loads(sf.read_text(encoding="utf-8"))
            for a in sdata.get("answers", []):
                qid = a["id"]
                if known_qids and qid not in known_qids:
                    results.append({
                        "type": "warning", "check": "state-integrity",
                        "file": relative_path(sf),
                        "message": f"Session references question '{qid}' which does not exist"
                    })
                if qid not in expected:
                    expected[qid] = {"attempts": 0, "correct": 0, "wrong": 0,
                                     "last_result": "", "last_attempt": ""}
                expected[qid]["attempts"] += 1
                if a.get("result") == "correct":
                    expected[qid]["correct"] += 1
                else:
                    expected[qid]["wrong"] += 1
                expected[qid]["last_result"] = a.get("result", "")
                expected[qid]["last_attempt"] = sdata.get("date", "")
        except (json.JSONDecodeError, KeyError) as e:
            results.append({
                "type": "warning", "check": "state-integrity",
                "file": relative_path(sf),
                "message": f"Could not parse session file: {e}"
            })

    # Compare against actual state files
    if state_dir.exists():
        for qid in expected:
            state_file = state_dir / f"{qid}.json"
            if not state_file.exists():
                results.append({
                    "type": "error", "check": "state-integrity",
                    "file": f"state/{qid}.json",
                    "message": f"State file missing for '{qid}'. Concurrent write likely failed."
                })
                continue
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                exp = expected[qid]
                if st.get("attempts", 0) < exp["attempts"]:
                    results.append({
                        "type": "warning", "check": "state-integrity",
                        "file": f"state/{qid}.json",
                        "message": f"State attempts={st['attempts']} but sessions expect {exp['attempts']}"
                    })
                elif st.get("attempts", 0) > exp["attempts"]:
                    results.append({
                        "type": "warning", "check": "state-integrity",
                        "file": f"state/{qid}.json",
                        "message": f"State attempts={st['attempts']} exceeds session total {exp['attempts']}"
                    })
            except (json.JSONDecodeError, KeyError) as e:
                results.append({
                    "type": "warning", "check": "state-integrity",
                    "file": f"state/{qid}.json",
                    "message": f"Could not parse state file: {e}"
                })

        # Check for state files without session history + state→question links
        for sf in state_dir.glob("*.json"):
            qid = sf.stem
            if known_qids and qid not in known_qids:
                results.append({
                    "type": "error", "check": "state-integrity",
                    "file": f"state/{sf.name}",
                    "message": f"State file for '{qid}' but question does not exist"
                })
            if qid not in expected:
                results.append({
                    "type": "warning", "check": "state-integrity",
                    "file": f"state/{sf.name}",
                    "message": f"State file for '{qid}' has no matching sessions. Orphan state."
                })

    return results

# ── Check 8: Log Integrity ─────────────────────────────────

def check_log_integrity():
    results = []
    log_file = VAULT_ROOT / "wiki/log.md"
    if not log_file.exists():
        results.append({
            "type": "warning", "check": "log-integrity",
            "file": "wiki/log.md",
            "message": "log.md does not exist. Operations are not being logged."
        })
        return results

    content = log_file.read_text(encoding="utf-8")
    entries = re.findall(r'^##\s*\[([^\]]+)\]\s*(\w+)\s*\|', content, re.MULTILINE)

    prev_date = None
    for i, (date_str, op) in enumerate(entries):
        try:
            cur_date = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            results.append({
                "type": "error", "check": "log-integrity",
                "file": "wiki/log.md",
                "message": f"Invalid date format in entry: [{date_str}]"
            })
            continue

        if prev_date and cur_date < prev_date:
            results.append({
                "type": "warning", "check": "log-integrity",
                "file": "wiki/log.md",
                "message": f"Non-chronological entry: [{date_str}] after [{prev_date.strftime('%Y-%m-%d %H:%M')}]"
            })
        prev_date = cur_date

    return results

# ── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Health Check")
    parser.add_argument("--verbose", action="store_true", help="Show per-issue details")
    parser.add_argument("--strict", action="store_true", help="Include symmetric link check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    all_results = []
    checks = [
        ("Broken Wiki-Links", check_broken_links),
        ("Orphan Notes", check_orphan_notes),
        ("Empty Files", check_empty_files),
        ("Frontmatter Consistency", check_frontmatter),
    ]
    if args.strict:
        checks.append(("Symmetric Links", check_symmetric_links))

    checks += [
        ("Question Bank Integrity", check_question_bank),
        ("State Integrity", check_state_integrity),
        ("Log Integrity", check_log_integrity),
    ]

    errors = []
    warnings = []
    infos = []

    for name, fn in checks:
        results = fn()
        all_results.extend(results)
        for r in results:
            if r["type"] == "error":
                errors.append(r)
            elif r["type"] == "warning":
                warnings.append(r)
            else:
                infos.append(r)

    if args.json:
        output = {
            "vault": str(VAULT_ROOT),
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "results": all_results,
            "checks": {}
        }
        for name, fn in checks:
            results = fn()
            output["checks"][name] = {
                "errors": sum(1 for r in results if r["type"] == "error"),
                "warnings": sum(1 for r in results if r["type"] == "warning"),
                "details": results
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(1 if errors else 0)

    # Pretty output
    total_checks = 8 if args.strict else 7
    print(color(CYAN, "=== Knowledge Base Health Check ==="))
    print(f"Vault: {VAULT_ROOT}")
    print()

    idx = 1
    strict_idx = None
    for name, fn in checks:
        results = fn()
        errs = sum(1 for r in results if r["type"] == "error")
        warns = sum(1 for r in results if r["type"] == "warning")
        label = f"[{idx}/{total_checks}]"
        if name == "Symmetric Links":
            strict_idx = idx
        issues = errs + warns
        if issues == 0:
            print(f"{label:8s} {name:30s} {color(GREEN, '0 issues')}")
        else:
            parts = []
            if errs:
                parts.append(color(RED, f"{errs} errors"))
            if warns:
                parts.append(color(YELLOW, f"{warns} warnings"))
            print(f"{label:8s} {name:30s} {', '.join(parts)}")
        idx += 1

    if not args.strict:
        print(f"{' ':8s} {'Symmetric Links':30s} {color(GRAY, 'skipped (use --strict)')}")

    # Details
    if args.verbose:
        print(f"\n{color(BOLD, '--- Details ---')}")
        for r in all_results:
            c = RED if r["type"] == "error" else YELLOW if r["type"] == "warning" else GRAY
            tag = "ERROR" if r["type"] == "error" else "WARN " if r["type"] == "warning" else "INFO "
            print(f"  {color(c, f'[{tag}]')} {r['file']}: {r.get('message', '')}")

    total_issues = len(errors) + len(warnings)
    print(f"\n{color(BOLD, 'Summary:')} {color(RED, f'{len(errors)} errors')}, "
          f"{color(YELLOW, f'{len(warnings)} warnings')}, "
          f"{len(get_markdown_files())} notes scanned")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
