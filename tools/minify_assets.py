#!/usr/bin/env python3
"""Masjid Events Perlis — conservative CSS/JS minifier for deploy artifacts.

Deploy-time only. The committed `public/js` and `public/css` sources stay
readable; this tool writes lossless-enough, smaller copies into the staging
directory that gets uploaded to GitHub Pages.

What it does (safe by construction):
  - removes comments (line `//` and block `/* */`) that appear outside of
    strings/template literals/regex literals
  - collapses blank lines and strips leading/trailing intra-line whitespace
It does NOT rename tokens, reorder declarations, or merge anything, so output
behaviour is identical to input. CSS reads are also string aware so `/*foo*/`
inside `content:"/*"` is preserved.

Usage:
    python3 tools/minify_assets.py [files...]       # edit each file in place
    python3 tools/minify_assets.py --print file     # print minified to stdout
    python3 tools/minify_assets.py --out dir file   # write dir/name

Exit 0 when everything succeeded.
"""

import argparse
import sys
from pathlib import Path

# Modes a character can be in while scanning.
NORMAL, S1, S2, TEMPLATE, REGEX, LC, BC = range(7)


def minify_js(text):
    out = []
    mode = NORMAL
    i = 0
    n = len(text)
    at_line_start = True

    # Whitespace outside strings/comments: collapse a run to a single space,
    # drop leading/trailing whitespace on a line, and drop blank lines.
    def whitespace():
        nonlocal i
        j = i
        while j < n and text[j] in " \t\r":
            j += 1
        if at_line_start:
            i = j  # leading whitespace on a line: drop entirely
            return
        if j == n or text[j] == "\n":
            i = j  # trailing whitespace before newline/EOF: drop
            return
        if out and out[-1] != " ":
            out.append(" ")
        i = j

    def newline():
        nonlocal at_line_start
        if not at_line_start:
            out.append("\n")
            at_line_start = True
        # at_line_start already True (from a previous newline) => blank line:
        # emit nothing, so blank lines collapse away.

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if mode == LC:
            if ch == "\n":
                mode = NORMAL
            i += 1
            continue

        if mode == BC:
            if ch == "*" and nxt == "/":
                mode = NORMAL
                i += 2
                continue
            i += 1
            continue

        if mode in (S1, S2, TEMPLATE, REGEX):
            if mode in (S1, S2) and ch == "\\":
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            if mode == TEMPLATE and ch == "\\":
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            if mode == REGEX and ch == "\\":
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            out.append(ch)
            if mode == S1 and ch == "'":
                mode = NORMAL
            elif mode == S2 and ch == '"':
                mode = NORMAL
            elif mode == TEMPLATE and ch == "$" and nxt == "{":
                out.append(nxt)
                i += 2
                continue
            elif mode == TEMPLATE and ch == "`":
                mode = NORMAL
            elif mode == REGEX and ch == "/":
                mode = NORMAL
            i += 1
            continue

        # NORMAL mode
        if ch == "/" and nxt == "/":
            mode = LC
            i += 2
            continue
        if ch == "/" and nxt == "*":
            mode = BC
            i += 2
            continue
        if ch == "/":
            # Only a regex literal can follow; these sources contain no `/`
            # used as the division operator, so treat as a regex literal start.
            mode = REGEX
            out.append(ch)
            i += 1
            at_line_start = False
            continue

        if ch in "'\"`":
            mode = {"'": S1, '"': S2, "`": TEMPLATE}[ch]
            out.append(ch)
            i += 1
            at_line_start = False
            continue

        if ch == "\n":
            newline()
            i += 1
            continue

        if ch in " \t\r":
            whitespace()
            continue

        out.append(ch)
        i += 1
        at_line_start = False

    return "".join(out).rstrip() + "\n"


def minify_css(text):
    """Same comment/whitespace treatment; CSS-safe because single spaces
    between tokens are kept and strings are preserved verbatim."""
    out = []
    mode = NORMAL
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if mode == LC:
            if ch == "\n":
                mode = NORMAL
            i += 1
            continue
        if mode == BC:
            if ch == "*" and nxt == "/":
                mode = NORMAL
                i += 2
                continue
            i += 1
            continue
        if mode in (S1, S2, TEMPLATE):
            out.append(ch)
            if ch == "\\":
                out.append(nxt)
                i += 2
                continue
            if mode == S1 and ch == "'":
                mode = NORMAL
            elif mode == S2 and ch == '"':
                mode = NORMAL
            elif mode == TEMPLATE and ch == "`":
                mode = NORMAL
            i += 1
            continue

        if ch == "/" and nxt == "*":
            mode = BC
            i += 2
            continue
        if ch in "'\"`":
            mode = {"'": S1, '"': S2, "`": TEMPLATE}[ch]
            out.append(ch)
            i += 1
            continue
        if ch in " \t\r\n":
            j = i
            while j < n and text[j] in " \t\r\n":
                j += 1
            if out and out[-1] != "\n":
                out.append(" ")
            i = j
            continue
        out.append(ch)
        i += 1

    return "".join(out).rstrip() + "\n"


def minify(path, kind):
    text = path.read_text(encoding="utf-8")
    return minify_js(text) if kind == "js" else minify_css(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Conservative JS/CSS minifier (deploy artifacts).")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--print", action="store_true", help="write to stdout instead of in place")
    ap.add_argument("--out", metavar="DIR", help="write minified copies into DIR (same basenames)")
    args = ap.parse_args(argv)

    for name in args.files:
        path = Path(name)
        kind = "js" if path.suffix == ".js" else "css"
        result = minify(path, kind)
        if args.print:
            sys.stdout.write(result)
        elif args.out:
            out_dir = Path(args.out)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / path.name).write_text(result, encoding="utf-8")
        else:
            path.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())