#!/usr/bin/env python3
"""Knowledge Compiler — incremental change detection + quiz dependency scan.

Usage:
  python3 scripts/compile.py                 # incremental scan
  python3 scripts/compile.py --full           # treat all files as changed
  python3 scripts/compile.py --what-if        # dry run
  python3 scripts/compile.py --interactive    # step through each file
  python3 scripts/compile.py --json           # JSON output
  python3 scripts/compile.py --process        # process + eval gate
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

CYAN = "\033[36m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"
GRAY = "\033[90m"; RESET = "\033[0m"
def c(col, text): return f"{col}{text}{RESET}"

VAULT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = Path(__file__).resolve().parent / ".compile-state.json"

PROMPT_MAP = {
    "raw/inbox":      ("prompts/inbox-triage.md",        "raw/inbox"),
    "raw/fleeting":   ("prompts/fleeting-to-permanent.md", "wiki/permanent"),
    "raw/articles":   ("prompts/article-to-literature.md",  "wiki/literature"),
    "raw/highlights": ("prompts/highlight-to-permanent.md", "wiki/permanent"),
    "raw/meetings":   ("prompts/meeting-to-notes.md",       "raw/meetings"),
    "raw/videos":     ("prompts/video-to-literature.md",    "wiki/literature"),
}

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            pass
    return {"lastCompile": None, "files": {}}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def get_raw_files():
    raw_path = VAULT_ROOT / "raw"
    if not raw_path.exists():
        return []
    files = []
    for f in raw_path.rglob("*.md"):
        if ".cache" not in str(f):
            files.append(f)
    return files

def rel_path(full):
    try:
        return str(full.relative_to(VAULT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(full).replace("\\", "/")

def get_prompt_for(rel):
    for prefix, (prompt_file, output_dir) in PROMPT_MAP.items():
        if rel.startswith(prefix):
            return {"promptFile": prompt_file, "outputDir": output_dir}
    return None

def compute_hash(path):
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except OSError:
        return ""

def detect_changes(state, full=False, use_hash=False):
    files = get_raw_files()
    changed = []
    unchanged = []

    for f in files:
        rp = rel_path(f)
        mtime = f.stat().st_mtime
        last_write = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        file_hash = compute_hash(f) if use_hash else ""

        stored = state.get("files", {}).get(rp)
        is_changed = False
        if not stored or full:
            is_changed = True
        elif last_write > stored.get("lastProcessed", ""):
            is_changed = True
        elif use_hash and file_hash != stored.get("hash", ""):
            is_changed = True

        entry = {
            "path": rp, "lastWrite": last_write, "hash": file_hash,
            "changed": is_changed, "prompt": get_prompt_for(rp)
        }
        if is_changed:
            changed.append(entry)
        else:
            unchanged.append(entry)

    return {"changed": changed, "unchanged": unchanged}

def detect_quiz_deps(changed_files):
    affected = []
    q_dir = VAULT_ROOT / "questions"
    if not q_dir.exists():
        return affected

    changed_slugs = set()
    for f in changed_files:
        if f.get("prompt") and "wiki" in f["prompt"]["outputDir"]:
            changed_slugs.add(Path(f["path"]).stem)

    if not changed_slugs:
        return affected

    for qf in q_dir.glob("*.md"):
        if qf.name == "INDEX.md":
            continue
        content = qf.read_text(encoding="utf-8")
        m = re.search(r'sources:\s*\[(.+?)\]', content)
        if m:
            srcs = [s.strip().strip('"').strip("'") for s in m.group(1).split(",") if s.strip()]
        else:
            m2 = re.search(r'sources:\s*(\S+)', content)
            srcs = [m2.group(1).strip()] if m2 else []
        for src in srcs:
            if src in changed_slugs:
                affected.append({"questionFile": rel_path(qf), "sourceSlug": src})
    return affected


import re

def main():
    parser = argparse.ArgumentParser(description="Knowledge Compiler")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--process", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--use-hash", action="store_true")
    parser.add_argument("--what-if", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    state = load_state()
    last = state.get("lastCompile", "never")
    mode_text = "Full" if args.full else "Incremental"

    if not args.json:
        print(c(CYAN, "=== Knowledge Compiler ==="))
        print(f"Mode: {mode_text}")
        print(f"Last compile: {last}")
        print()

    print(c(CYAN, "Scanning raw/ ..."))
    scan = detect_changes(state, full=args.full, use_hash=args.use_hash)

    if not args.json:
        for f in scan["changed"] + scan["unchanged"]:
            tag = "[CHANGED]" if f["changed"] else "[UNCHANGED]"
            col = YELLOW if f["changed"] else GRAY
            print(f"  {f['path']} {c(col, tag)}")
        print()
        count = len(scan["changed"])
        col = YELLOW if count > 0 else GREEN
        print(f"Files requiring compilation: {c(col, str(count))}")

    if args.json:
        output = {
            "mode": mode_text, "lastCompile": last,
            "totalFiles": len(scan["changed"]) + len(scan["unchanged"]),
            "changedCount": len(scan["changed"]),
            "tasks": [], "quizAffected": []
        }
        for f in scan["changed"]:
            output["tasks"].append({
                "sourceFile": f["path"],
                "promptFile": f["prompt"]["promptFile"] if f["prompt"] else None,
                "outputDir": f["prompt"]["outputDir"] if f["prompt"] else None,
                "lastWrite": f["lastWrite"],
                "status": "pending"
            })
        qdeps = detect_quiz_deps(scan["changed"])
        for d in qdeps:
            output["quizAffected"].append(d)
        print(json.dumps(output, ensure_ascii=False, indent=2))

    if not args.json and scan["changed"]:
        print()
        print(c(CYAN, "Suggested compilation plan:"))
        for f in scan["changed"]:
            prompt_rel = f["prompt"]["promptFile"] if f["prompt"] else "(no prompt mapped)"
            out_rel = f["prompt"]["outputDir"] if f["prompt"] else "(unknown)"
            print(f"  {f['path']}")
            print(f"    Prompt: {prompt_rel}")
            print(f"    Output: {out_rel}")

        qdeps = detect_quiz_deps(scan["changed"])
        if qdeps:
            print()
            print(c(YELLOW, f"Quiz questions affected by changes: {len(qdeps)}"))
            for d in qdeps:
                print(c(YELLOW, f"  {d['questionFile']} (source: {d['sourceSlug']})"))
            print(c(YELLOW, "Consider re-running /ingest Stage 5.5 to regenerate."))

    # Process mode
    if args.process and scan["changed"]:
        print()
        print(c(CYAN, "--- Processing ---"))
        for f in scan["changed"]:
            if not f["prompt"]:
                print(c(GRAY, f"  SKIP {f['path']} — no prompt mapped"))
                continue
            prompt_path = VAULT_ROOT / f["prompt"]["promptFile"]
            if not prompt_path.exists():
                print(c(GRAY, f"  SKIP {f['path']} — prompt not found: {f['prompt']['promptFile']}"))
                continue
            if args.interactive:
                ans = input(f"  PROCESS {f['path']} ? [y/N/skip] ").strip().lower()
                if ans != 'y':
                    print(c(GRAY, "    Skipped."))
                    continue
            if args.what_if:
                print(c(GRAY, f"  [WhatIf] Would process {f['path']} with {f['prompt']['promptFile']}"))
                continue
            print(f"  To compile: {f['path']}")
            print(f"    Run: Read file, apply {f['prompt']['promptFile']}, output to {f['prompt']['outputDir']}/")
            print("    (LLM invocation via agent)")

        # Eval gate
        print()
        print(c(CYAN, "--- Eval Gate ---"))
        eval_script = VAULT_ROOT / "scripts/eval.py"
        if eval_script.exists():
            import subprocess
            result = subprocess.run([sys.executable, str(eval_script), "--json"],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                print(c(RED, "Eval FAILED — fix issues and re-run."))
                sys.exit(1)
            else:
                print(c(GREEN, "Eval PASSED — ready"))
        else:
            print(c(GRAY, "eval.py not found — skipping gate"))

    # Update state
    if not args.what_if and not args.json:
        new_state = {
            "lastCompile": datetime.now(timezone.utc).isoformat(),
            "files": {}
        }
        rescan = detect_changes({"lastCompile": None, "files": {}})
        for f in rescan["changed"] + rescan["unchanged"]:
            new_state["files"][f["path"]] = {
                "lastProcessed": f["lastWrite"],
                "hash": f["hash"]
            }
        save_state(new_state)
        print()
        print(c(GREEN, "Compile state updated."))

    if not args.json:
        print()
        print(c(CYAN, "Done."))


if __name__ == "__main__":
    main()
