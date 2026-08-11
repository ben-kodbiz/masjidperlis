#!/usr/bin/env python3
"""Masjid Events Perlis — performance measurement and budget gate.

Reports, for every public page, the initial payload: the HTML document plus
every asset the browser must fetch to render it (CSS, the page's JS modules,
the shared data JSON, the PWA manifest). Two size figures are given:
  - "raw"      — bytes as served when minified (deploy-time minify_assets.py)
  - "gzip"     — a close approximation of what a host with automatic
                 compression (GitHub Pages serves gzip/brotli) transfers

PWA icons are reported but excluded from the "initial load" total, because
they are only fetched when a visitor installs the app.

Fails (exit 1) when a shared budget is exceeded, so CI catches size
regressions. Budgets live at the bottom of this file.

Usage:
    python3 tools/perf_report.py              # uses public/ + minified sizes
    python3 tools/perf_report.py --dir out    # audit an arbitrary build dir
    python3 tools/perf_report.py --raw        # size committed (unminified) files
"""

import argparse
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "public"

# Data JSON files the public DataLoader (public/js/data.js) fetches.
DATA_JSON = ("events.json", "masjids.json", "speakers.json", "categories.json", "settings.json")

# minify_assets.py is the deploy-time transformer for JS/CSS.
MINIFIER = Path(__file__).resolve().parent / "minify_assets.py"
sys.path.insert(0, str(MINIFIER.parent))
import minify_assets as m

# ---- budgets (see section headers in the report) ---------------------------
BUDGET_INITIAL_RAW_KB = 80      # uncompressed (minified) bytes for first load
BUDGET_INITIAL_GZIP_KB = 30     # approx transferred bytes after host compression
# Requests are kept low but data intentionally arrives as several tiny, highly
# cacheable JSON/JS files (per-collection caching means stable files are never
# re-fetched; HTTP/2 serves them in parallel), so 15 is the realistic ceiling.
BUDGET_REQUESTS = 15
BUDGET_JS_RAW_KB = 60           # total per-page JS before compression
BUDGET_CSS_RAW_KB = 20          # total per-page CSS before compression
BUDGET_HTML_RAW_KB = 40         # per-page HTML document


def served_bytes(path, mode):
    """The exact bytes a visitor receives: minified for js/css at deploy time
    (mode != raw), otherwise the raw committed file."""
    if path.suffix in (".js", ".css") and mode != "raw":
        kind = "js" if path.suffix == ".js" else "css"
        return m.minify(path, kind).encode("utf-8")
    return path.read_bytes()


def audit_dir(dir_path, mode):
    """Return (page dicts, pwa icon paths)."""
    pages = []
    for html in sorted(dir_path.glob("*.html")):
        text = html.read_text(encoding="utf-8")
        scripts = re.findall(r'<script\s+src="([^"]+\.js)"', text)
        styles = set(re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', text))
        styles |= set(re.findall(r'<link[^>]+href="([^"]+)"[^>]+rel="stylesheet"', text))
        has_manifest = '<link rel="manifest"' in text or 'rel="manifest"' in text
        pages.append({
            "name": html.name,
            "html": html,
            "scripts": scripts,
            "styles": styles,
            "has_manifest": has_manifest,
        })

    report = []
    for page in pages:
        assets = []  # (label, served bytes)

        def add(label, payload):
            assets.append((label, payload))

        add("html", served_bytes(page["html"], mode))
        for s in page["scripts"]:
            p = dir_path / s if not s.startswith("../") else (dir_path.parent / s.split("../", 1)[1])
            add("js:" + s, served_bytes(p, mode))
        for st in page["styles"]:
            p = dir_path / st
            add("css:" + st, served_bytes(p, mode))
        manifest = dir_path / "manifest.webmanifest"
        if page["has_manifest"] and manifest.is_file():
            add("manifest", served_bytes(manifest, mode))
        if "js:js/data.js" in [a[0] for a in assets]:
            for name in DATA_JSON:
                p = dir_path / "data" / name
                if p.is_file():
                    add("data:" + name, served_bytes(p, mode))

        total_raw = sum(len(b) for _, b in assets)
        total_gz = sum(len(gzip.compress(b, mtime=0)) for _, b in assets)

        js_raw = sum(len(b) for lbl, b in assets if lbl.startswith("js:"))
        css_raw = sum(len(b) for lbl, b in assets if lbl.startswith("css:"))
        html_raw = len(served_bytes(page["html"], mode))

        report.append({
            "name": page["name"],
            "assets": assets,
            "total_raw": total_raw,
            "total_gz": total_gz,
            "requests": len(assets),
            "html_raw": html_raw,
            "js_raw": js_raw,
            "css_raw": css_raw,
        })
    icons = sorted((dir_path / "assets").glob("*.png")) if (dir_path / "assets").is_dir() else []
    return report, icons


def format_kb(num):
    return "{:>7.1f} kB".format(num / 1024.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--raw", action="store_true",
                    help="measure committed (unminified) file sizes instead of deploy-minified")
    args = ap.parse_args(argv)

    target = Path(args.dir)
    mode = "raw" if args.raw else "gzip"
    report, pwa_icons = audit_dir(target, mode)

    print("Perf report — {} {}s\n".format(target, "raw committed" if mode == "raw" else "minified + gzip approx"))

    def fmt(label, kb):
        return "{} {}".format(format_kb(kb), label)

    for page in report:
        print("=== {} ===".format(page["name"]))
        for lbl, payload in page["assets"]:
            print("   {:9} {}".format(format_kb(len(payload)), lbl))
        print("   ----------")
        print("   requests:   {}".format(page["requests"]))
        print("   initial:    {} raw".format(format_kb(page["total_raw"])))
        print("               {} approx gzip (host-compressed)".format(format_kb(page["total_gz"])))
        print()

    if pwa_icons:
        icons_kb = sum(p.stat().st_size for p in pwa_icons) / 1024.0
        print("PWA icons (not part of initial load): {} for {}".format(format_kb(icons_kb * 1024), ", ".join(p.name for p in pwa_icons)))
    else:
        print("PWA icons: none found")

    # ---- budget gate ----
    failures = []
    for page in report:
        if page["total_raw"] / 1024.0 > BUDGET_INITIAL_RAW_KB:
            failures.append("{} initial raw {:.1f} kB > {:.0f} kB".format(
                page["name"], page["total_raw"] / 1024.0, BUDGET_INITIAL_RAW_KB))
        if mode == "gzip" and page["total_gz"] / 1024.0 > BUDGET_INITIAL_GZIP_KB:
            failures.append("{} initial gzip {:.1f} kB > {:.0f} kB".format(
                page["name"], page["total_gz"] / 1024.0, BUDGET_INITIAL_GZIP_KB))
        if page["requests"] > BUDGET_REQUESTS:
            failures.append("{} requests {} > {}".format(page["name"], page["requests"], BUDGET_REQUESTS))
        if page["js_raw"] / 1024.0 > BUDGET_JS_RAW_KB:
            failures.append("{} js {:.1f} kB > {:.0f} kB".format(page["name"], page["js_raw"] / 1024.0, BUDGET_JS_RAW_KB))
        if page["css_raw"] / 1024.0 > BUDGET_CSS_RAW_KB:
            failures.append("{} css {:.1f} kB > {:.0f} kB".format(page["name"], page["css_raw"] / 1024.0, BUDGET_CSS_RAW_KB))
        if page["html_raw"] / 1024.0 > BUDGET_HTML_RAW_KB:
            failures.append("{} html {:.1f} kB > {:.0f} kB".format(page["name"], page["html_raw"] / 1024.0, BUDGET_HTML_RAW_KB))

    if failures:
        print("\nBUDGET VIOLATIONS:")
        for f in failures:
            print("  - " + f)
        return 1

    print("\nBudgets OK (raw <= {} kB/page, gzip <= {} kB/page, {} requests, "
          "js <= {} kB, css <= {} kB, html <= {} kB)".format(
              BUDGET_INITIAL_RAW_KB, BUDGET_INITIAL_GZIP_KB, BUDGET_REQUESTS,
              BUDGET_JS_RAW_KB, BUDGET_CSS_RAW_KB, BUDGET_HTML_RAW_KB))
    return 0


if __name__ == "__main__":
    sys.exit(main())