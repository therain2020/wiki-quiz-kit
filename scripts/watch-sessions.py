#!/usr/bin/env python3
"""Watch Downloads folder for quiz session files, auto-update state.

Usage:
  python3 scripts/watch-sessions.py                  watch ~/Downloads
  python3 scripts/watch-sessions.py --dir ~/Desktop  watch custom dir
  python3 scripts/watch-sessions.py --once            scan once, process, exit

Zero LLM cost. Runs in background, polls every 5 seconds.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding

fix_encoding()

VAULT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = VAULT_ROOT / "sessions"
PROCESSED_FILE = VAULT_ROOT / "temp" / ".watched-sessions"


def find_downloads():
    """Cross-platform Downloads folder detection."""
    home = Path.home()
    candidates = [
        home / "Downloads",
        home / "downloads",
        home / "Téléchargements",
    ]
    if os.name == "nt":
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x000F, None, 0, buf) == 0:
            candidates.insert(0, Path(buf.value))
    for d in candidates:
        if d.exists():
            return d
    return home / "Downloads"


def process_session(filepath):
    """Copy to sessions/ and update state."""
    filepath = Path(filepath)
    dest = SESSIONS_DIR / filepath.name
    shutil.copy2(filepath, dest)

    result = subprocess.run(
        [sys.executable, str(VAULT_ROOT / "scripts" / "update-state.py"), str(dest)],
        capture_output=True, text=True, encoding="utf-8"
    )
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {filepath.name}")
    if result.stdout and result.stdout.strip():
        for line in result.stdout.strip().split('\n'):
            print(f"  {line}")
    if result.returncode != 0:
        print(f"  ERROR:\n{result.stderr}")
    return dest


def scan(watch_dir, processed):
    """Scan for new session files, process them."""
    found = False
    for f in sorted(watch_dir.glob("quiz-session-*.json")):
        if str(f) in processed:
            continue
        process_session(f)
        processed.add(str(f))
        found = True
    if not found:
        now = datetime.now().strftime('%H:%M:%S')
        # Don't print "no new" on every poll — too noisy. Only on --once
    return processed


def main():
    parser = argparse.ArgumentParser(
        description="Watch for quiz session downloads, auto-update state")
    parser.add_argument("--dir", default=None, help="Directory to watch (default: Downloads)")
    parser.add_argument("--once", action="store_true", help="Scan once and exit")
    args = parser.parse_args()

    watch_dir = Path(args.dir) if args.dir else find_downloads()
    if not watch_dir.exists():
        print(f"ERROR: {watch_dir} not found", file=sys.stderr)
        sys.exit(1)

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load previously processed files
    processed = set()
    if PROCESSED_FILE.exists():
        try:
            processed = set(json.loads(PROCESSED_FILE.read_text(encoding='utf-8')))
        except json.JSONDecodeError:
            pass

    print(f"Watching: {watch_dir}")
    print(f"Sessions: {SESSIONS_DIR}")

    if args.once:
        processed = scan(watch_dir, processed)
        PROCESSED_FILE.write_text(json.dumps(list(processed), ensure_ascii=False, indent=2), encoding='utf-8')
        return

    print("Polling every 5s. Ctrl+C to stop.\n")
    try:
        while True:
            processed = scan(watch_dir, processed)
            PROCESSED_FILE.write_text(json.dumps(list(processed), ensure_ascii=False, indent=2), encoding='utf-8')
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
