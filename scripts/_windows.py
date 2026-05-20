"""Shared Windows encoding fix — DRY import for all scripts that print Chinese/emoji.

Usage (at top of script, right after imports):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _windows import fix_encoding
    fix_encoding()
"""

import sys


def fix_encoding():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
