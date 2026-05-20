#!/usr/bin/env python3
"""Eval Runner — deterministic checks for wiki compilation output.

Usage:
  python3 scripts/eval.py                  # run all cases
  python3 scripts/eval.py --verbose         # per-check details
  python3 scripts/eval.py --json            # JSON output
"""

import argparse
import json
import re
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

CYAN = "\033[36m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"
GRAY = "\033[90m"; RESET = "\033[0m"
def c(col, text): return f"{col}{text}{RESET}"

VAULT_ROOT = Path(__file__).resolve().parent.parent

def parse_frontmatter(content):
    """Extract YAML frontmatter as dict using yaml.safe_load."""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = yaml.safe_load(parts[1])
    return fm if isinstance(fm, dict) else {}

def extract_wikilinks(content):
    links = []
    for m in re.finditer(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]', content):
        target = m.group(1).strip()
        if not target.startswith("http") and not re.search(r'\.(png|jpg|jpeg|gif|svg|pdf)$', target):
            links.append(target)
    return links

def resolve_note(link):
    for base in [VAULT_ROOT, *[d for d in VAULT_ROOT.rglob("*") if d.is_dir()]]:
        c = base / f"{link}.md"
        if c.exists():
            return c
    return None

def check_frontmatter(content, required_type=None):
    fm = parse_frontmatter(content)
    if "type" not in fm:
        return False, "Missing 'type' in frontmatter"
    if required_type and fm["type"] != required_type:
        return False, f"Expected type='{required_type}', got '{fm['type']}'"
    if "created" not in fm:
        return False, "Missing 'created' in frontmatter"
    return True, f"Frontmatter valid (type={fm['type']})"

def check_links(content):
    links = extract_wikilinks(content)
    broken = [l for l in links if not resolve_note(l)]
    if broken:
        return False, f"Broken links: {', '.join(broken)}"
    return True, f"All {len(links)} wikilinks resolve"

def check_body(content):
    m = re.search(r'^---\s*\n.*?\n---\s*\n(.+)', content, re.DOTALL)
    if m and len(m.group(1).strip()) > 20:
        return True, f"Body present ({len(m.group(1).strip())} chars)"
    return False, "No body content beyond frontmatter"

def check_state_update(case_path):
    results = []
    given_file = case_path / "given-state.json"
    sess_file = case_path / "session.json"
    exp_file = case_path / "expected-state.json"
    for f, name in [(given_file, "given-state.json"), (sess_file, "session.json"), (exp_file, "expected-state.json")]:
        if not f.exists():
            return [{"pass": False, "reason": f"Missing {name}"}]
    try:
        given = json.loads(given_file.read_text(encoding="utf-8"))
        sess = json.loads(sess_file.read_text(encoding="utf-8"))
        exp = json.loads(exp_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError) as e:
        return [{"pass": False, "reason": f"Parse error: {e}"}]

    actual = {}
    for qid, v in given.items():
        actual[qid] = dict(v)

    for a in sess.get("answers", []):
        qid = a["id"]
        if qid not in actual:
            actual[qid] = {"attempts": 0, "correct": 0, "wrong": 0, "last_result": "", "last_attempt": ""}
        actual[qid]["attempts"] += 1
        if a.get("result") == "correct":
            actual[qid]["correct"] += 1
        else:
            actual[qid]["wrong"] += 1
        actual[qid]["last_result"] = a.get("result", "")
        actual[qid]["last_attempt"] = sess.get("date", "")

    for qid, e in exp.items():
        if qid not in actual:
            results.append({"pass": False, "reason": f"Expected state for '{qid}' but not in actual"})
            continue
        a = actual[qid]
        for field in ["attempts", "correct", "wrong", "last_result"]:
            if a.get(field) != e.get(field):
                results.append({"pass": False, "reason": f"'{qid}' {field}: expected {e.get(field)}, got {a.get(field)}"})
                break
        else:
            results.append({"pass": True, "reason": f"'{qid}' state matches expected"})

    for qid in actual:
        if qid not in exp:
            results.append({"pass": False, "reason": f"Unexpected state for '{qid}'"})

    return results


def main():
    parser = argparse.ArgumentParser(description="Eval Runner")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    evals_dir = VAULT_ROOT / "evals/cases"
    if not evals_dir.exists():
        print(c(RED, "ERROR: evals/cases/ not found"))
        sys.exit(2)

    cases = sorted([d for d in evals_dir.rglob("*") if d.is_dir()])
    total = 0; passed = 0; failed = 0; all_results = []

    print(c(CYAN, "=== Eval Runner ==="))
    print(f"Vault: {VAULT_ROOT}")
    print(f"Evals: {evals_dir}")
    print()

    for case in cases:
        total += 1
        meta = {}
        meta_file = case / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        expected_type = meta.get("expectedType")
        if expected_type == "question-gen":
            print(f"[{case.name}] {c(GRAY, 'SKIP — use eval-llm.py')}")
            continue
        if expected_type == "state-update":
            expected_file = case / "expected-state.json"
        else:
            expected_file = case / "expected.md"

        if not expected_file.exists():
            reason = "no expected-state.json" if expected_type == "state-update" else "no expected.md"
            print(f"[{case.name}] {c(GRAY, f'SKIP — {reason}')}")
            continue

        expect_fail = meta.get("expectFail", False)
        expected_content = expected_file.read_text(encoding="utf-8")

        print(f"[{case.name}] ", end="")

        checks = []
        if expected_type == "state-update":
            checks = check_state_update(case)
        else:
            ok, reason = check_frontmatter(expected_content, expected_type)
            checks.append({"pass": ok, "reason": reason})
            ok, reason = check_body(expected_content)
            checks.append({"pass": ok, "reason": reason})
            ok, reason = check_links(expected_content)
            checks.append({"pass": ok, "reason": reason})

        all_ok = all(c["pass"] for c in checks)

        if expect_fail:
            if not all_ok:
                print(c(GREEN, "PASS (expected failure)"))
                passed += 1
            else:
                print(c(RED, "FAIL (expected failure but all checks passed)"))
                failed += 1
        else:
            if all_ok:
                print(c(GREEN, "PASS"))
                passed += 1
            else:
                print(c(RED, "FAIL"))
                failed += 1

        if args.verbose:
            for ck in checks:
                tag = "  OK" if ck["pass"] else "  XX"
                col = GRAY if ck["pass"] else RED
                print(f"    {c(col, tag)} {ck['reason']}")

        all_results.append({
            "case": case.name, "passed": not all_ok if expect_fail else all_ok,
            "expectFail": expect_fail,
            "checks": [{"pass": c["pass"], "reason": c["reason"]} for c in checks]
        })

    print()
    col = GREEN if failed == 0 else RED
    print(f"Results: {c(col, f'{passed} / {total} passed')}")

    if args.json:
        output = {"total": total, "passed": passed, "failed": failed, "cases": all_results}
        print(json.dumps(output, ensure_ascii=False, indent=2))

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
