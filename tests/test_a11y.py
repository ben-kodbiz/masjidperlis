#!/usr/bin/env python3
"""Stage 18 — accessibility audit of committed and generated HTML.

A lightweight static audit (no headless browser): relies on the checks that
can be proven from the markup alone.

  - <html lang>, one (and only one) <h1> on content pages
  - a skip link pointing at an existing, focusable <main> landmark
  - every <input>/<select>/<textarea> has a label or accessible name
  - every target="_blank" link also has rel="noopener"
  - no duplicate element ids
  - <title> present

Covers: committed public top-level pages, committed admin pages, and the
server-rendered event/masjid pages produced by tools/build_site.py.

Usage:
    python3 tests/test_a11y.py
"""

import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
ADMIN = ROOT / "admin"
BUILD = ROOT / "tools" / "build_site.py"

# Pages whose main content is rendered client-side (no static h1 until JS runs).
JS_RENDERED_H1_OK = {
    (PUBLIC / "event.html").resolve(),
    (PUBLIC / "masjid.html").resolve(),
}

VOID_INPUTS = {"input", "img", "br", "hr", "meta", "link"}


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_lang = None
        self.ids = {}
        self.tags = {}
        self.h1 = 0
        self.skip_links = []          # [(attrs dict, filename)]
        self.inputs = []              # dicts of attrs
        self.labels_for = []          # for= values
        self.target_blank = []        # anchor attrs dicts
        self.has_title = False
        self.current_tag = None
        self.attr_stack = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.attr_stack.append((tag, d))
        if tag == "html" and "lang" in d:
            self.html_lang = d["lang"]
        if tag == "title":
            self.has_title = True
        if "id" in d:
            self.ids.setdefault(d["id"], []).append(tag)
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and d.get("class") == "skip-link":
            self.skip_links.append(d)
        if tag in ("input", "select", "textarea") and not (
                d.get("type") in ("hidden", "submit", "button", "reset")):
            self.inputs.append(d)
        if tag == "label":
            if "for" in d:
                self.labels_for.append(d["for"])
        if tag == "a" and "target" in d and d["target"] == "_blank":
            self.target_blank.append(d)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def pop(self, tag=None):
        if self.attr_stack:
            popped = self.attr_stack.pop()
            if tag is not None:
                return popped if popped[0] == tag else None
            return popped
        return None


def parse(html_text):
    p = AuditParser()
    p.feed(html_text)
    p.close()
    return p


def named(attrs):
    """True when the element already carries an accessible name."""
    return bool(attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("title"))


def audit(path):
    """Return a list of human-readable problems for one HTML file."""
    problems = []
    text = path.read_text(encoding="utf-8")
    p = parse(text)

    if not p.html_lang:
        problems.append("missing <html lang>")
    if not p.has_title:
        problems.append("missing <title>")

    # one h1 on content pages (client-rendered shells may legitimately have 0)
    if p.h1 > 1:
        problems.append("more than one <h1> ({})".format(p.h1))
    resolved = path.resolve()
    if p.h1 == 0 and resolved not in JS_RENDERED_H1_OK:
        problems.append("no <h1> heading")

    # skip link -> existing, focusable main landmark
    if not p.skip_links:
        problems.append("no skip link")
    if "main" not in p.ids:
        problems.append('no <main id="main"> skip target')
    else:
        main_ids = p.ids["main"]
        # find the real <main> element attrs via a targeted re-scan to check tabindex
        for m in re.finditer(r"<main\b[^>]*>", text):
            attrs_text = m.group(0)
            main_ids = main_ids  # keep; tabindex checked below on the raw tag
            if 'tabindex="-1"' not in attrs_text:
                problems.append('<main tabindex="-1"> missing (skip target not focusable)')
            break
    for link in p.skip_links:
        if not re.match(r"^#[\w-]+$", link.get("href", "")):
            problems.append("skip link href is not a local anchor: {}".format(link.get("href")))
        elif link["href"] == "#main" and "main" not in p.ids:
            problems.append('skip link points to #main but no id="main" exists')

    # every control has a label / accessible name
    label_ids = set(p.labels_for)
    for d in p.inputs:
        if named(d):
            continue
        if d.get("id") and d["id"] in label_ids:
            continue
        problems.append("<{}> without a label: {}".format(
            "input[type={}]".format(d.get("type")) if "type" in d else "select/textarea",
            d.get("id") or d.get("name") or d.get("placeholder") or "?"))

    # no duplicate ids
    for iid, tags in p.ids.items():
        if len(tags) > 1:
            problems.append("duplicate id \"{}\" used {}x".format(iid, len(tags)))

    # target=_blank must be noopener
    for d in p.target_blank:
        rel = d.get("rel", "").split()
        if "noopener" not in rel:
            problems.append('target="_blank" link without rel="noopener": {}'.format(d.get("href")))

    return problems


def audit_dir(html_files):
    """Audit a set of HTML files; return dict path -> [problems]."""
    results = {}
    for path in sorted(html_files):
        if path.suffix != ".html":
            continue
        problems = audit(path)
        if problems:
            results[path.name if len(html_files) == 1 else str(path.relative_to(ROOT))] = problems
    return results


def test_committed_public_pages():
    html_files = sorted(PUBLIC.glob("*.html"))
    results = audit_dir(html_files)
    assert not results, "public pages a11y problems: {}".format(results)


def test_admin_pages():
    html_files = sorted(ADMIN.glob("*.html"))
    results = audit_dir(html_files)
    assert not results, "admin pages a11y problems: {}".format(results)


def test_generated_static_pages():
    out = Path(tempfile.mkdtemp(prefix="mvp-a11y-"))
    try:
        cmd = [sys.executable, str(BUILD), "--out", str(out), "--today", "2026-08-09",
               "--site-url", "https://example.com"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr

        html_files = sorted((out / "event").rglob("*.html")) + sorted((out / "masjid").rglob("*.html"))
        assert html_files, "no generated pages to audit"

        problems_total = 0
        for path in html_files:
            problems = audit(path)
            if problems:
                problems_total += 1
                assert False, "{} a11y problems: {}".format(path.relative_to(out), problems)
        assert problems_total == 0
    finally:
        shutil.rmtree(out)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print("PASS {}".format(test.__name__))
        except AssertionError as exc:
            failed += 1
            print("FAIL {}: {}".format(test.__name__, exc))
    print("\n{}/{} passed".format(len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())