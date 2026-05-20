#!/usr/bin/env python3
"""Eval LLM Runner — question generation output structure validation.

Usage:
  python3 scripts/eval-llm.py                          # run all cases
  python3 scripts/eval-llm.py --verbose                 # per-check details
  python3 scripts/eval-llm.py --json                    # JSON output
  python3 scripts/eval-llm.py --case-dir evals/cases/question-gen
  python3 scripts/eval-llm.py --output-file path/to/output.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

CYAN = "\033[36m"; GREEN = "\033[32m"; RED = "\033[31m"; GRAY = "\033[90m"; RESET = "\033[0m"
def c(col, text): return f"{col}{text}{RESET}"

VAULT_ROOT = Path(__file__).resolve().parent.parent


def check_questions(questions, expected):
    results = []
    min_q = expected.get("minQuestions", 1)
    max_q = expected.get("maxQuestions", 10)
    checks = expected.get("checks", {})

    count = len(questions)
    if count < min_q:
        results.append({"pass": False, "reason": f"Generated {count} questions, min {min_q} required"})
        return results
    if count > max_q:
        results.append({"pass": False, "reason": f"Generated {count} questions, max {max_q} allowed"})
        return results
    results.append({"pass": True, "reason": f"Question count {count} in range [{min_q}-{max_q}]"})

    for idx, q in enumerate(questions):
        qi = idx + 1

        for field in checks.get("requiredFields", []):
            if field not in q:
                results.append({"pass": False, "reason": f"Q{qi}: missing required field '{field}'"})

        expected_opts = checks.get("optionsCount")
        if expected_opts is not None:
            actual_opts = len(q.get("options", []))
            if actual_opts != expected_opts:
                results.append({"pass": False, "reason": f"Q{qi}: expected {expected_opts} options, got {actual_opts}"})
            else:
                results.append({"pass": True, "reason": f"Q{qi}: options={actual_opts} OK"})

        if checks.get("hasExplanation"):
            expl = q.get("explanation", "")
            if not expl or len(expl.strip()) < 10:
                results.append({"pass": False, "reason": f"Q{qi}: explanation missing or too short"})
            else:
                results.append({"pass": True, "reason": f"Q{qi}: explanation OK"})

        if checks.get("answerInRange"):
            opts = q.get("options", [])
            ans = q.get("answer", -1)
            if ans < 0 or ans >= len(opts):
                results.append({"pass": False, "reason": f"Q{qi}: answer index {ans} out of range [0-{len(opts)-1}]"})
            else:
                results.append({"pass": True, "reason": f"Q{qi}: answer={ans} in range OK"})

    return results


def main():
    parser = argparse.ArgumentParser(description="Eval LLM Runner")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--case-dir", default=None)
    parser.add_argument("--output-file", default=None)
    args = parser.parse_args()

    if args.case_dir:
        case_path = Path(args.case_dir) if Path(args.case_dir).exists() else VAULT_ROOT / args.case_dir
    else:
        case_path = VAULT_ROOT / "evals/cases/question-gen"

    print(c(CYAN, "=== Eval LLM Runner ==="))
    print(f"Vault: {VAULT_ROOT}")
    print(f"Cases: {case_path}")
    print()

    if not case_path.exists():
        print(c(RED, f"ERROR: Case directory not found: {case_path}"))
        sys.exit(2)

    cases = sorted([d for d in case_path.iterdir() if d.is_dir()])
    total = 0; passed = 0; failed = 0; all_results = []

    for case in cases:
        total += 1
        expected_file = case / "expected.json"
        meta_file = case / "meta.json"

        if not expected_file.exists():
            print(f"[{case.name}] {c(GRAY, 'SKIP — no expected.json')}")
            continue

        expected = json.loads(expected_file.read_text(encoding="utf-8"))
        meta = {}
        if meta_file.exists():
            try: meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError: pass
        expect_fail = meta.get("expectFail", False)

        if args.output_file:
            output_path = Path(args.output_file) if Path(args.output_file).exists() else VAULT_ROOT / args.output_file
        else:
            output_path = case / "output.json"

        print(f"[{case.name}] ", end="")

        if not output_path.exists():
            print(c(GRAY, f"SKIP — no output.json (generate questions first)"))
            continue

        try:
            questions = json.loads(output_path.read_text(encoding="utf-8"))
            if not isinstance(questions, list):
                questions = [questions]
            check_results = check_questions(questions, expected)
            all_ok = all(c["pass"] for c in check_results)

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
                for ck in check_results:
                    tag = "  OK" if ck["pass"] else "  XX"
                    col = GRAY if ck["pass"] else RED
                    print(f"    {c(col, tag)} {ck['reason']}")

            all_results.append({
                "case": case.name, "passed": not all_ok if expect_fail else all_ok,
                "expectFail": expect_fail,
                "checks": [{"pass": c["pass"], "reason": c["reason"]} for c in check_results]
            })
        except (json.JSONDecodeError, KeyError) as e:
            print(c(RED, f"FAIL — parse error: {e}"))
            failed += 1
            all_results.append({"case": case.name, "passed": False, "expectFail": expect_fail,
                               "checks": [{"pass": False, "reason": f"Parse error: {e}"}]})

    print()
    col = GREEN if failed == 0 else RED
    print(f"Results: {c(col, f'{passed} / {total} passed')}")

    if args.json:
        output = {"total": total, "passed": passed, "failed": failed, "cases": all_results}
        print(json.dumps(output, ensure_ascii=False, indent=2))

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
