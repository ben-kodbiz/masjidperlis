#!/usr/bin/env python3
"""Tests for tools/security_audit.py (Stage 20 security gate).

Usage:
    python3 tests/test_security.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "tools" / "security_audit.py"

sys.path.insert(0, str(ROOT / "tools"))
import security_audit as sa  # noqa: E402


def test_audit_clean_on_committed_repo():
    res = subprocess.run([sys.executable, str(AUDIT)], capture_output=True, text=True)
    assert res.returncode == 0, "audit failed:\n" + res.stdout
    assert "SECURITY AUDIT CLEAN" in res.stdout


def test_secret_patterns_catch_credentials():
    samples = [
        "token=ghp_" + "A" * 30,  # ::gitleaks
        "x-api-key: REDACTED",  # ::gitleaks
        "-----BEGIN REDACTED KEY-----\nMIIE",  # ::gitleaks
        "stripe_token_redacted",  # ::gitleaks
        'client_secret = "REDACTED"',  # ::gitleaks
    ]
    for s in samples:
        assert sa.SECRET_RE.search(s) is not None, "not flagged: {!r}".format(s[:40])


def test_secret_patterns_do_not_flag_placeholders_or_docs():
    clean = [
        '"Authorization": "Bearer ${FEED_API_TOKEN}"',
        "# Secrets — never commit\n*.pem",
        "Google service-account credentials",
        "spreadsheet_id: ''",
        "never commit secrets",
    ]
    for s in clean:
        assert sa.SECRET_RE.search(s) is None, "false positive: {!r}".format(s[:40])


def test_public_js_has_no_innerhtml():
    problems = sa.scan_public_sinks()
    assert problems == [], problems


def test_admin_id_attrs_all_escaped():
    problems = sa.scan_admin_id_attrs()
    assert problems == [], problems


def test_deploy_boundary_admin_not_public():
    assert (ROOT / "public" / "admin").exists() is False, "admin/ inside public/"


def test_secrets_never_in_public_or_admin():
    for root in (ROOT / "public", ROOT / "admin"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in (".js", ".html", ".css"):
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if sa.SECRET_RE.search(line):
                    raise AssertionError("{}:{}: possible secret".format(
                        path.relative_to(ROOT), i))


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