#!/usr/bin/env python3
"""Download and clean YouTube auto-generated transcript.

Usage:
  python3 scripts/youtube-transcript.py <url>              print to stdout
  python3 scripts/youtube-transcript.py <url> -o file.txt  write to file

Requires: yt-dlp (pip install yt-dlp)
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

# Import clean and encoding fix from sibling script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _windows import fix_encoding  # noqa: E402
from clean import clean  # noqa: E402

fix_encoding()


def list_subs(url):
    """List available subtitle tracks. Returns (auto_subs, manual_subs)."""
    result = subprocess.run(
        ["yt-dlp", "--list-subs", url],
        capture_output=True, text=True
    )
    output = result.stderr + result.stdout

    auto_langs = []
    manual_langs = []
    in_auto = False
    in_manual = False

    for line in output.split('\n'):
        line = line.strip()
        if 'Available automatic captions' in line:
            in_auto = True; in_manual = False; continue
        if 'Available subtitles' in line:
            in_auto = False; in_manual = True; continue
        if in_auto or in_manual:
            parts = line.split()
            if parts and '-' in parts[0]:
                lang = parts[0]
                name = ' '.join(parts[1:]).split('  ')[0].strip() if len(parts) > 1 else ''
                (auto_langs if in_auto else manual_langs).append((lang, name))

    return auto_langs, manual_langs


def pick_best_lang(auto_langs, manual_langs):
    """Pick best language: auto English > manual English > first auto > first manual."""
    for lang, _ in auto_langs:
        if lang.startswith('en'):
            return lang
    for lang, _ in manual_langs:
        if lang.startswith('en'):
            return lang
    if auto_langs:
        return auto_langs[0][0]
    if manual_langs:
        return manual_langs[0][0]
    return None


def download_vtt(url, lang, output_dir):
    """Download VTT subtitles. Returns path to .vtt file."""
    output_tpl = str(Path(output_dir) / '%(id)s')
    result = subprocess.run(
        ["yt-dlp", "--write-auto-subs", "--sub-format", "vtt",
         "--skip-download", "--sub-lang", lang,
         "--output", output_tpl, url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        stderr = result.stderr + result.stdout
        # Try without --write-auto-subs for manual subs
        print(f"yt-dlp: auto-subs failed for '{lang}', trying manual...", file=sys.stderr)
        result2 = subprocess.run(
            ["yt-dlp", "--write-subs", "--sub-format", "vtt",
             "--skip-download", "--sub-lang", lang,
             "--output", output_tpl, url],
            capture_output=True, text=True
        )
        if result2.returncode != 0:
            raise RuntimeError(f"yt-dlp failed for '{lang}':\n{result2.stderr}")

    video_id = url.split('watch?v=')[-1].split('&')[0]
    vtt_path = Path(output_dir) / f"{video_id}.{lang}.vtt"
    if vtt_path.exists():
        return vtt_path
    # Try without lang suffix
    alt = Path(output_dir) / f"{video_id}.en.vtt"
    if alt.exists():
        return alt
    # Search for any .vtt
    vtts = list(Path(output_dir).glob("*.vtt"))
    if vtts:
        return vtts[0]
    raise FileNotFoundError(f"No .vtt file found in {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Download and clean YouTube auto-generated transcript")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-o", "--output", default=None,
                        help="Output file path (stdout if not set)")
    args = parser.parse_args()

    # Step 1: Find best subtitle track
    print("Checking subtitle tracks...", file=sys.stderr)
    auto_langs, manual_langs = list_subs(args.url)
    lang = pick_best_lang(auto_langs, manual_langs)
    if not lang:
        print("ERROR: No subtitle tracks found for this video.", file=sys.stderr)
        sys.exit(1)
    print(f"  Selected: {lang}", file=sys.stderr)

    # Step 2: Download VTT
    print("Downloading transcript...", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmpdir:
        vtt_path = download_vtt(args.url, lang, tmpdir)
        raw = Path(vtt_path).read_text(encoding='utf-8')

    # Step 3: Clean
    print("Cleaning...", file=sys.stderr)
    result = clean(raw, mode='vtt')

    # Step 4: Output
    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"  Wrote {len(result.encode('utf-8'))}B to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
