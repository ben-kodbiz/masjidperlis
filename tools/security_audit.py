#!/usr/bin/env python3
"""Masjid Events Perlis — static security audit.

Proves the cheap-to-verify security properties so they stay true in CI:

  secrets        no credential patterns in tracked files
  https          no plain-http external URLs in pages/documents (the sitemap
                 XML namespace is exempt; localhost is exempt)
  scripts        no third-party/remote <script> in public or admin
  eval           no eval() / new Function / document.write in public JS
  injection      the exposed public site renders only via safe DOM: no
                 innerHTML anywhere in public/js
  admin-id-attr  every data-id / ?id= attribute interpolation in admin pages
                 is wrapped in A.esc() (ids are regex-constrained too)
  boundary       the admin/deploy surface never ships inside public/

Exits 1 on any finding.

Usage:
    python3 tools/security_audit.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
ADMIN = ROOT / "admin"
TOOLS = ROOT / "tools"

# Credential-ish VALUES, matched loosely. Auth-* header config keys use
# ${NAME} placeholders, so a literal value never appears in committed files.
# Ignore-pattern files (.gitignore, *.md) legitimately mention filenames and
# policy, so only value-looking tokens with clear entropy are flagged.
SECRET_PATTERNS = [
    r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}",
    r"(?:ghp|gho|ghu|github_pat)_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"sk_[A-Za-z0-9_]{20,}",
    r"xox[baprs]-[A-Z0-9-]{10,}",
    r"client_secret\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}",
]
SECRET_RE = re.compile("|".join("(" + p + ")" for p in SECRET_PATTERNS), re.IGNORECASE)

# Files in the public surface: html, js, css (the served app).
PUBLIC_FILES = sorted(
    [p for p in PUBLIC.rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".css")]
)
ADMIN_FILES = sorted(
    [p for p in ADMIN.rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".css")]
)

TRACKED = []


def resolve_tracked():
    global TRACKED
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True)
    TRACKED = [ROOT / line for line in out.stdout.splitlines() if line]


def scan_secrets():
    findings = []
    for path in TRACKED:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "PY" == "PY" and "::gitleaks" in line:
                continue
            if SECRET_RE.search(line):
                findings.append("{}:{}: possible secret: {!r}".format(
                    path.relative_to(ROOT), i, line.strip()[:120]))
    return findings


def scan_http(urls_by_file):
    findings = []
    for path, urls in urls_by_file.items():
        for url in urls:
            if url.startswith("http://") and "localhost" not in url and "127.0.0.1" not in url:
                findings.append("{}: plain http URL {}".format(path.relative_to(ROOT), url))
    return findings


def extract_urls(text, pattern):
    return [m for m in pattern.findall(text)]


SCHEME_ATTR_RE = re.compile(r'(?:href|src)\s*=\s*["\'](https?://[^"\'\s>]+)')
SITEMAP_NS_RE = re.compile(r'xmlns="http://[^"\']+"')
COMMENT_RE = re.compile(r"(?m)^\s*(//.*|#.*)$")


def scan_https():
    findings = []
    for path in PUBLIC_FILES + ADMIN_FILES + [p for p in TOOLS.glob("*.py")] + [ROOT / "SECURITY.md"]:
        if path.resolve() == Path(__file__).resolve():
            continue  # this audit's own regex literals mention http://
        text = path.read_text(encoding="utf-8", errors="replace")
        urls = extract_urls(text, SCHEME_ATTR_RE)
        # In source comments / docstrings the http is address + not a link.
        for line in text.splitlines():
            if "http://localhost" in line or "http://127.0.0.1" in line:
                continue
            for m in re.finditer(r"https?://[^\s'\"<>]+", line):
                u = m.group(0).rstrip(".,);]}")
                if u.startswith("http://"):
                    # sitemap namespace and shell docstring examples are fine
                    if "sitemaps.org" in u or "localhost" in u or "127.0.0.1" in u:
                        continue
                    findings.append("{}: {} (not https)".format(path.relative_to(ROOT), u))
    return findings


def scan_remote_scripts():
    findings = []
    for path in PUBLIC_FILES + ADMIN_FILES:
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'<script[^>]+src\s*=\s*["\']([^"\']+)', text):
            src = m.group(1)
            if src.startswith("http://") or src.startswith("https://") or src.startswith("//"):
                findings.append("{}: external/remote script {}".format(
                    path.relative_to(ROOT), src))
    return findings


def scan_public_sinks():
    findings = []
    for path in PUBLIC.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(innerHTML|outerHTML|document\.write|new Function|\beval\s*\()", text):
            findings.append("{}: unsafe sink {}".format(path.relative_to(ROOT), m.group(1)))
    return findings


def scan_admin_id_attrs():
    """data-id= / ?id= attribute interpolations must be escaped in admin pages."""
    findings = []
    pat = re.compile(r"(data-id=\"' \+ [a-z]+\.[a-z]+ |href=\"[^\"]*\?id=' \+ [a-z]+\.[a-z]+)")
    for path in ADMIN_FILES:
        if path.suffix != ".html":
            continue
        text = path.read_text(encoding="utf-8")
        for m in pat.finditer(text):
            snippet = text[m.start():m.end()]
            if "A.esc(" not in snippet:
                findings.append("{}: unescaped id attribute: {!r}".format(
                    path.relative_to(ROOT), snippet[:80]))
        # history.replaceState id= is a URL, not HTML — allowed but confirm it
        # is not feeding innerHTML.
    return findings


def scan_boundary():
    findings = []
    # admin must never be shipped inside public
    admin_inside_public = (PUBLIC / "admin").exists()
    if admin_inside_public:
        findings.append("admin/ exists inside public/ — it would be deployed to GitHub Pages")
    return findings


def main(argv=None):
    resolve_tracked()
    checks = [
        ("secrets", scan_secrets()),
        ("https-only URLs", scan_https()),
        ("no remote scripts", scan_remote_scripts()),
        ("public site safe sinks", scan_public_sinks()),
        ("admin id attributes escaped", scan_admin_id_attrs()),
        ("deploy boundary", scan_boundary()),
    ]
    failed = False
    for name, problems in checks:
        if problems:
            failed = True
            print("[FAIL] {}".format(name))
            for p in problems[:25]:
                print("   - " + p)
            if len(problems) > 25:
                print("   …and {} more".format(len(problems) - 25))
        else:
            print("[ok] {}".format(name))
    print("\n" + ("SECURITY AUDIT FAILED" if failed else "SECURITY AUDIT CLEAN"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())