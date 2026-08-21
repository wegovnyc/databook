#!/usr/bin/env python3
"""Turn one of our 80-column markdown docs into a HackMD-ready copy.

    python3 scripts/hackmd-format.py docs/some-report.md            # -> stdout
    python3 scripts/hackmd-format.py docs/some-report.md -o out.md

Why this exists
---------------
⚠ **HackMD defaults to `breaks: true`**, meaning every single newline becomes a
`<br>`. Our docs are hard-wrapped at 80 columns for reviewable diffs, so pasting
one in renders every paragraph as a column of short broken lines.

Two independent fixes are applied, deliberately belt-and-braces:

1. A `breaks: false` front matter block, which is the real fix and the one
   documented in CLAUDE.md.
2. Prose paragraphs are re-joined into single long lines anyway — so the copy
   still renders correctly if the front matter is stripped, or if it is pasted
   somewhere else entirely (a GitHub issue, an email, a Google Doc). Front
   matter is easy to lose; unwrapped text survives.

The repo file is never modified: it keeps its 80-column wrapping, and this
writes a separate copy. Regenerate rather than hand-editing the copy, or the
two drift.

What is preserved byte-for-byte
-------------------------------
Anything where a line break carries meaning: fenced code blocks (``` and ~~~),
table rows, headings, horizontal rules, blockquotes, HTML blocks, and the
structure of lists. Only genuine prose is re-joined, and list items are joined
into their own single line rather than into the surrounding text.
"""

import argparse
import re
import sys

FRONT_MATTER = "---\nbreaks: false\n---\n\n"

FENCE = re.compile(r'^\s*(```|~~~)')
HEADING = re.compile(r'^\s{0,3}#{1,6}\s')
HRULE = re.compile(r'^\s{0,3}([-*_])(\s*\1){2,}\s*$')
TABLE = re.compile(r'^\s*\|')
QUOTE = re.compile(r'^\s{0,3}>')
LIST = re.compile(r'^(\s*)([-*+]|\d{1,9}[.)])\s+')
INDENTED_CODE = re.compile(r'^ {4,}\S')
HTML = re.compile(r'^\s{0,3}<')


def is_structural(line: str) -> bool:
    """True when the line's own break must be kept."""
    return bool(
        not line.strip()
        or HEADING.match(line)
        or HRULE.match(line)
        or TABLE.match(line)
        or QUOTE.match(line)
        or HTML.match(line)
    )


def format_for_hackmd(text: str) -> str:
    lines = text.splitlines()
    out = []
    buf = []                    # the prose paragraph being accumulated
    in_fence = False
    fence_marker = None

    def flush():
        if buf:
            out.append(" ".join(s.strip() for s in buf))
            buf.clear()

    for line in lines:
        m = FENCE.match(line)
        if m:
            # A fence toggles verbatim mode; only a matching marker closes it.
            if not in_fence:
                flush()
                in_fence, fence_marker = True, m.group(1)
            elif line.strip().startswith(fence_marker):
                in_fence, fence_marker = False, None
            out.append(line)
            continue

        if in_fence:
            out.append(line)
            continue

        # An indented code block only starts where a paragraph is not already
        # running — otherwise it is just a continuation line of wrapped prose.
        if INDENTED_CODE.match(line) and not buf:
            flush()
            out.append(line)
            continue

        if is_structural(line):
            flush()
            out.append(line)
            continue

        if LIST.match(line):
            # Each list item becomes its own joined line.
            flush()
            buf.append(line.rstrip())
            continue

        buf.append(line)

    flush()

    # Collapse the runs of blank lines that joining can leave behind, but keep
    # paragraph separation.
    cleaned = []
    for line in out:
        if not line.strip() and cleaned and not cleaned[-1].strip():
            continue
        cleaned.append(line)

    return "\n".join(cleaned).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="source markdown file (never modified)")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    ap.add_argument("--no-front-matter", action="store_true",
                    help="omit the `breaks: false` block (it is the real fix — "
                         "only drop it when pasting somewhere that shows raw "
                         "front matter, such as a GitHub issue)")
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as fh:
        src = fh.read()

    # Never stack a second front-matter block on a file that has one.
    if src.startswith("---\n"):
        end = src.find("\n---", 4)
        if end != -1:
            print(f"[hackmd] {args.path} already has front matter; leaving it",
                  file=sys.stderr)
            args.no_front_matter = True

    body = format_for_hackmd(src)
    result = body if args.no_front_matter else FRONT_MATTER + body

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(result)
        src_lines, out_lines = len(src.splitlines()), len(result.splitlines())
        print(f"[hackmd] {args.path} -> {args.out}  "
              f"({src_lines} lines -> {out_lines})", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
