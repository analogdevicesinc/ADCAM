#!/usr/bin/env python3
# extract_details.py
# Usage:
#   python3 extract_details.py <source-file> [output-file]
#   python3 extract_details.py <source-file> tof-viewer.md --replace-header "## Configuration JSON File" --skip-first 2 --drop-last 8
#
# This reads a local file and writes any <details>...</details> blocks that include
# a <summary>ADIToFGUI (C++)</summary> to the output file.

import sys
import re
from pathlib import Path
import argparse

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def extract_details_blocks(text: str):
    blocks = []
    cur_lines = []
    in_block = False
    for line in text.splitlines(True):
        if not in_block and re.match(r'^\s*<details>', line):
            in_block = True
            cur_lines = [line]
            continue
        if in_block:
            cur_lines.append(line)
            if re.search(r'</details>\s*$', line):
                blocks.append(''.join(cur_lines))
                in_block = False
                cur_lines = []
    return blocks

def main(argv):
    p = argparse.ArgumentParser(description="Extract <details> blocks containing ADIToFGUI (C++) from a local markdown file")
    p.add_argument("source", type=Path, help="Path to local markdown file")
    p.add_argument("output", nargs="?", default="tof-viewer.md", help="Output file (defaults to 'tof-viewer.md' when omitted)")
    p.add_argument("--replace-header", help="Replace the initial '### ADIToFGUI (C++)' line in the block with this text")
    p.add_argument("--skip-first", type=int, default=0, help="Skip the first N lines from the extracted output")
    p.add_argument("--drop-last", type=int, default=0, help="Drop the last N lines from the extracted output")
    args = p.parse_args(argv)

    if not args.source.is_file():
        print(f"Source file not found: {args.source}", file=sys.stderr)
        sys.exit(2)

    text = read_file(args.source)
    blocks = extract_details_blocks(text)
    pattern = re.compile(r'<summary>[^<]*ADIToFGUI\s*\(C\+\+\)[^<]*<\/summary>', re.IGNORECASE)
    matched = [b for b in blocks if pattern.search(b)]

    if not matched:
        print("No matching <details> block found.", file=sys.stderr)
        sys.exit(1)

    combined = "\n".join(matched)
    lines = combined.splitlines()

    # Optionally skip first N lines
    if args.skip_first > 0:
        if args.skip_first >= len(lines):
            lines = []
        else:
            lines = lines[args.skip_first:]

    # Optionally replace the first heading line inside the block(s)
    if args.replace_header:
        # find the first line that looks like "### ADIToFGUI (C++)" and replace it
        hdr_re = re.compile(r'^\s*###\s*ADIToFGUI\s*\(C\+\+\)\s*$', re.IGNORECASE)
        for i, ln in enumerate(lines):
            if hdr_re.match(ln):
                lines[i] = args.replace_header
                break

    # Optionally drop last N lines
    if args.drop_last > 0:
        if args.drop_last >= len(lines):
            lines = []
        else:
            lines = lines[:-args.drop_last]

    out_path = Path(args.output)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {out_path}")

if __name__ == "__main__":
    main(sys.argv[1:])
