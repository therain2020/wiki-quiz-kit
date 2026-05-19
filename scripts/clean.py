#!/usr/bin/env python3
"""Data cleaner for /ingest pipeline — strips format noise and UI chrome.

Usage:
  python3 scripts/clean.py --mode vtt --input video.vtt --output clean.txt
  python3 scripts/clean.py --mode web --input page.md --output clean.md
  python3 scripts/clean.py --mode article --input article.md
  cat video.vtt | python3 scripts/clean.py --mode vtt    (stdin, Mac/Linux)

Warnings go to stderr. Use --output to avoid platform encoding issues.
"""

import argparse
import re
import sys
from collections import Counter

# ── Blocklist: whole-line match only (no substring matching) ──

UI_LINES = {
    # Navigation
    "Skip navigation", "Skip to content", "Search",
    "Search with your voice",
    # Buttons
    "Subscribe", "Subscribed", "Share", "Save", "Download",
    "Show more", "Show less",
    # Platform
    "Watch full video", "Live", "Transcript", "Follow along",
    "Auto-dubbed", "How this was made", "Learn more",
    "Include playlist", "Show transcript",
    # Meta
    "An error occurred while retrieving sharing information.",
    "VideosAbout",
    # Cookie / GDPR / Newsletter
    "Accept all cookies", "Privacy Policy", "GDPR", "Cookie Settings",
    "Newsletter", "Join our newsletter",
    # Social
    "Share this", "Follow us on", "Connect with",
    # Related content
    "Related", "Recommended", "You might also like", "Popular posts",
}

# Patterns for whole-line regex matching
UI_PATTERNS = [
    r'^\d+[\.\d]*[KMB]?\s*views?(\s*·.*)?$',   # "10K views", "10,179 views · 2 months ago"
    r'^\d+[\.\d]*[KMB]?\s*subscribers?$',        # "18.1K subscribers"
    r'^\d+\s+(years?|months?|weeks?|days?|hours?)\s+ago$',  # "2 months ago"
    r'^Image\s+\d+$',                             # "Image 7"
    r'^\[\w+\]\s+.*$',                             # "[x] Include playlist"
    r'^\d+/\d+/\d+$',                              # "0:00 / 24:38"
    r'^Mix\s*\(50\+\)$',                           # "Mix (50+)"
    r'^Live Playlist.*$',                          # "Live Playlist (10)"
    r'^Palantir Developers\s*$',                   # Channel name (genericized in usage)
    r'^•Watch full video$',
    r'^•$',
]


def step1_strip_format(text, mode):
    """Remove format-specific noise: timestamps, XML tags, HTML residue."""
    if mode == "vtt":
        # Remove WEBVTT header block (WEBVTT through first blank line)
        text = re.sub(r'^WEBVTT.*?\n\n', '', text, flags=re.DOTALL)
        # Remove timestamp lines
        text = re.sub(r'^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*$', '', text, flags=re.MULTILINE)
        # Remove alignment metadata
        text = re.sub(r'^align:start position:\d+%$', '', text, flags=re.MULTILINE)
        # Remove inline timestamps
        text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', text)
        # Remove XML tags
        text = re.sub(r'</?c>', '', text)

    # Common format cleanup for all modes
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove markdown image references (often noise in page extracts)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove CSS-like fragments
    text = re.sub(r'\{[^}]*\}', '', text)

    return text


def step2_strip_ui(text):
    """Remove UI chrome lines. Whole-line match only — no substring matching."""
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        # Exact match against blocklist
        if stripped in UI_LINES:
            continue

        # Regex pattern match
        matched = False
        for pat in UI_PATTERNS:
            if re.match(pat, stripped):
                matched = True
                break
        if matched:
            continue

        result.append(line)
    return '\n'.join(result)


def step3_dedup(text):
    """Deduplicate adjacent identical lines. Remove lines appearing >=3 times non-adjacently."""
    lines = text.split('\n')
    result = []
    prev = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            prev = None
            continue
        if stripped == prev:
            continue
        result.append(line)
        prev = stripped

    # Count non-adjacent occurrences
    non_empty = [l.strip() for l in result if l.strip()]
    counts = Counter(non_empty)
    # Remove lines that appear >=3 times (keep first occurrence)
    seen = {}
    deduped = []
    for line in result:
        stripped = line.strip()
        if not stripped:
            deduped.append(line)
            continue
        if counts[stripped] >= 3:
            if stripped not in seen:
                seen[stripped] = True
                deduped.append(line)
            # else: skip duplicate
        else:
            deduped.append(line)

    return '\n'.join(deduped)


def step4_normalize_whitespace(text):
    """Collapse multiple blank lines, trim edges."""
    lines = text.split('\n')
    result = []
    blank_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_count += 1
        else:
            if blank_count >= 1:
                result.append('')
            blank_count = 0
            result.append(line.rstrip())
    # Trim leading/trailing blanks
    while result and result[0] == '':
        result.pop(0)
    while result and result[-1] == '':
        result.pop()
    return '\n'.join(result)


def step5_truncation_check(text):
    """Warn if content is very large, hard-truncate if enormous."""
    data = text.encode('utf-8')
    size = len(data)
    if size > 100_000:
        # Truncate at byte boundary, not char boundary
        truncated = data[:100_000]
        # Walk back to last complete UTF-8 char and newline
        try:
            truncated_str = truncated.decode('utf-8')
        except UnicodeDecodeError:
            # Cut at last valid UTF-8 boundary
            for cut in range(99_997, 99_990, -1):
                try:
                    truncated_str = data[:cut].decode('utf-8')
                    break
                except UnicodeDecodeError:
                    continue
            else:
                truncated_str = data[:99_990].decode('utf-8', errors='replace')
        last_nl = truncated_str.rfind('\n')
        if last_nl > 80_000:
            truncated_str = truncated_str[:last_nl]
        truncated_str += "\n\n[... truncated at 100KB]"
        print(f"clean: WARNING content truncated from {size}B to 100KB", file=sys.stderr)
        return truncated_str
    elif size > 50_000:
        print(f"clean: WARNING content is {size}B (>50KB), consider reviewing", file=sys.stderr)
    return text


def clean(text, mode):
    """Run the 5-step cleaning pipeline."""
    orig_size = len(text.encode('utf-8'))

    text = step1_strip_format(text, mode)
    text = step2_strip_ui(text)
    text = step3_dedup(text)
    text = step4_normalize_whitespace(text)
    text = step5_truncation_check(text)

    clean_size = len(text.encode('utf-8'))
    if orig_size > 0:
        ratio = (1 - clean_size / orig_size) * 100
        if ratio > 5:
            print(f"clean: reduced {orig_size}B → {clean_size}B ({ratio:.0f}% removed)", file=sys.stderr)

    return text


def main():
    parser = argparse.ArgumentParser(description="Data cleaner for /ingest pipeline")
    parser.add_argument("--mode", choices=["vtt", "web", "article"], default="web",
                        help="Cleaning mode (default: web)")
    parser.add_argument("--input", "-i", default=None,
                        help="Input file path (reads stdin if not set)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path (writes to stdout if not set)")
    args = parser.parse_args()

    if args.input:
        with open(args.input, encoding='utf-8') as f:
            text = f.read()
    else:
        text = sys.stdin.buffer.read().decode('utf-8')

    if not text.strip():
        print("clean: WARNING empty input, nothing to clean", file=sys.stderr)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(text)
        else:
            sys.stdout.write(text)
        return

    result = clean(text, args.mode)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"clean: wrote {len(result.encode('utf-8'))}B to {args.output}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
