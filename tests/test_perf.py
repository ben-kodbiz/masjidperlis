#!/usr/bin/env python3
"""Tests for tools/minify_assets.py and tools/perf_report.py (Stage 19).

Usage:
    python3 tests/test_perf.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tools" / "minify_assets.py"
PERF = ROOT / "tools" / "perf_report.py"
PUBLIC = ROOT / "public"

sys.path.insert(0, str(ROOT / "tools"))
import minify_assets as m  # noqa: E402


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def test_js_comments_removed_but_strings_kept():
    src = (
        "// leading line comment\n"
        'var a = "http://example.com"; /* block * comment */\n'
        "function x(q) { return /ab\\/c/.test(q); }\n"
        "var b = '// not a comment';\n"
    )
    out = m.minify_js(src)
    assert "leading line comment" not in out, "line comment kept"
    assert "block * comment" not in out, "block comment kept"
    assert 'var a = "http://example.com";' in out, "string changed"
    assert "var b = '// not a comment';" in out, "string with // changed"
    assert "/ab\\/c/" in out, "regex literal mangled"
    assert out.count("\n") == 3, "blank/comment lines not collapsed: {!r}".format(out)


def test_js_default_jargon_out_passes_node_check():
    for name in ("data", "ui", "events", "masjids", "share", "ics", "maps", "app"):
        path = PUBLIC / "js" / (name + ".js")
        out = m.minify_js(path.read_text(encoding="utf-8"))
        tmp = ROOT / "tests" / ("_tmp_minify_" + name + ".js")
        tmp.write_text(out, encoding="utf-8")
        try:
            res = run(["node", "--check", str(tmp)])
            assert res.returncode == 0, "minified {} fails node --check: {}".format(name, res.stderr)
        finally:
            tmp.unlink()


def test_css_comments_removed_strings_kept():
    src = (
        "/* header */\n"
        ".a { content: \"/* not a comment */\"; background: url('x.png'); }\n"
        "@media (min-width: 640px) { .b { color: red; } }\n"
    )
    out = m.minify_css(src)
    assert "header" not in out, "css comment kept"
    assert '.a { content: "/* not a comment */";' in out, "css string changed"
    assert "url('x.png')" in out, "url() changed"
    assert "@media" in out and "(min-width: 640px)" in out, "media query broken"


def test_minifier_is_in_place_safe_idempotent():
    src = "// c\nfunction f() {\n  return 1;\n}\n"
    once = m.minify_js(src)
    twice = m.minify_js(once)
    assert once == twice, "minifier is not idempotent"
    assert once == "function f() {\nreturn 1;\n}\n", repr(once)


def test_perf_report_passes_budgets_on_committed_site():
    res = run([sys.executable, str(PERF)])
    assert res.returncode == 0, "perf budget gate failed:\n" + res.stdout
    assert "Budgets OK" in res.stdout
    assert "PWA icons" in res.stdout


def test_perf_report_reports_all_pages_and_pwa():
    res = run([sys.executable, str(PERF)])
    for page in ("index.html", "events.html", "event.html", "masjids.html", "masjid.html"):
        assert "=== {} ===".format(page) in res.stdout, "missing {}".format(page)
    assert "icon-192.png" in res.stdout and "icon-512.png" in res.stdout


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print("PASS {}".format(test.__name__))
        except (AssertionError, Exception) as exc:
            failed += 1
            print("FAIL {}: {}".format(test.__name__, exc))
    print("\n{}/{} passed".format(len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())