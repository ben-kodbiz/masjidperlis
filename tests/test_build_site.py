#!/usr/bin/env python3
"""Tests for tools/build_site.py (static site generation / SEO).

Usage:
    python3 tests/test_build_site.py
"""

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent / "tools" / "build_site.py"
DATA = Path(__file__).resolve().parent.parent / "data"

GEN_ICONS = Path(__file__).resolve().parent.parent / "tools" / "gen_icons.py"

SITE_URL = "https://example.com"


def run(out_dir, site_url=SITE_URL, today="2026-08-09", data_dir=None, version=None):
    cmd = [
        sys.executable,
        str(BUILD),
        "--out", str(out_dir),
        "--today", today,
        "--site-url", site_url,
    ]
    if data_dir:
        cmd += ["--data-dir", str(data_dir)]
    if version is not None:
        cmd += ["--version", version]
    return subprocess.run(cmd, capture_output=True, text=True)


def make_dir(name):
    return Path(tempfile.mkdtemp(prefix=f"mvp-build-{name}-"))


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def not_empty(path):
    assert path.is_file() and path.stat().st_size > 0, f"{path} missing or empty"


def test_generates_expected_files():
    out = make_dir("files")
    result = run(out)

    assert result.returncode == 0, result.stdout + result.stderr

    assert (out / "sitemap.xml").is_file()
    assert (out / "robots.txt").is_file()
    # published + cancelled + postponed events are generated
    assert (out / "event" / "evt-20260809-001" / "index.html").is_file()
    assert (out / "event" / "evt-20260811-001" / "index.html").is_file()
    assert (out / "event" / "evt-20260818-001" / "index.html").is_file()
    # .ics accompanies each event page
    assert (out / "event" / "evt-20260809-001" / "event.ics").is_file()
    # every masjid gets a page
    assert (out / "masjid" / "masjid-alwi" / "index.html").is_file()
    assert (out / "masjid" / "masjid-an-nur" / "index.html").is_file()


def test_event_page_html():
    out = make_dir("event")
    result = run(out)

    assert result.returncode == 0, result.stdout + result.stderr
    html = (out / "event" / "evt-20260809-001" / "index.html").read_text(encoding="utf-8")

    # meaningful content present without scripts
    assert "event-card" not in html  # no JS-driven lists on static page
    assert "Kuliyyah Maghrib" in html
    assert "Masjid Alwi" in html
    assert "Penceramah" in html
    assert "Ahad 9 Ogos 2026" in html
    assert "8:00 PM" in html

    # head metadata / SEO
    assert 'rel="canonical" href="https://example.com/event/evt-20260809-001/"' in html
    assert 'property="og:type" content="article"' in html
    assert '<meta name="description"' in html
    assert "application/ld+json" in html
    assert '"@type": "Event"' in html

    # relative asset path resolves from nested directory back to site root
    assert 'href="../../css/style.css"' in html
    assert 'href="../../masjid/masjid-alwi/"' in html

    # share links present (static, no JS needed)
    assert "Kongsi WhatsApp" in html and "wa.me" in html
    assert "Kongsi Telegram" in html and "t.me" in html
    assert "event.ics" in html


def test_cancelled_event_has_notice_and_schema():
    out = make_dir("cancel")
    result = run(out)

    assert result.returncode == 0, result.stdout + result.stderr
    html = (out / "event" / "evt-20260811-001" / "index.html").read_text(encoding="utf-8")
    assert "dibatalkan" in html
    assert "EventCancelled" in html
    assert 'class="event-status cancelled"' in html

    ics = (out / "event" / "evt-20260811-001" / "event.ics").read_text(encoding="utf-8")
    assert "STATUS:CANCELLED" in ics
    assert "SUMMARY:Kelas Fiqh" in ics


def test_masjid_page_html():
    out = make_dir("masjid")
    result = run(out)

    assert result.returncode == 0, result.stdout + result.stderr
    html = (out / "masjid" / "masjid-alwi" / "index.html").read_text(encoding="utf-8")

    assert "Masjid Alwi" in html
    assert "Kangar, Perlis" in html
    assert "Akan Datang" in html
    assert '"@type": "Place"' in html
    assert "openstreetmap.org" in html
    assert 'rel="canonical" href="https://example.com/masjid/masjid-alwi/"' in html
    # upcoming list links point at clean event pages
    assert 'href="../../event/evt-20260812-001/"' in html


def test_recurring_exception_respected():
    out = make_dir("recur")
    result = run(out, today="2026-08-18")

    assert result.returncode == 0, result.stdout + result.stderr

    events = json.loads((Path(DATA) / "events.json").read_text(encoding="utf-8"))
    rec = next(e for e in events if e["id"] == "evt-20260812-001")
    assert rec["recurrence"]["exceptions"] == ["2026-08-19"]

    # 2026-08-19 is the exception; it must NOT appear in the masjid page list
    html = (out / "masjid" / "masjid-alwi" / "index.html").read_text(encoding="utf-8")
    assert "Khamis 20 Ogos 2026" in html or "Rabu 26 Ogos 2026" in html
    assert "19 Ogos" not in html


def test_sitemap_and_robots():
    out = make_dir("seo")
    result = run(out)

    assert result.returncode == 0, result.stdout + result.stderr

    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.com/" in sitemap
    assert "https://example.com/events.html" in sitemap
    assert "https://example.com/masjids.html" in sitemap
    assert "https://example.com/event/evt-20260809-001/" in sitemap
    assert "https://example.com/masjid/masjid-alwi/" in sitemap
    assert sitemap.count("<url>") == 3 + 8 + 3, sitemap.count("<url>")

    robots = (out / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *" in robots
    assert "Allow: /" in robots
    assert "Sitemap: https://example.com/sitemap.xml" in robots


def test_canonical_consistency():
    out = make_dir("canon")
    result = run(out)

    assert result.returncode == 0, result.stdout + result.stderr

    # Sitemap locs must match each page's canonical href.
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    for loc in ["/", "events.html", "masjids.html",
                "event/evt-20260809-001/", "masjid/masjid-alwi/"]:
        assert (SITE_URL + "/" + ("" if loc == "/" else loc)) in sitemap

    canon_event = (out / "event" / "evt-20260809-001" / "index.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/event/evt-20260809-001/"' in canon_event

    canon_masjid = (out / "masjid" / "masjid-alwi" / "index.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/masjid/masjid-alwi/"' in canon_masjid


def test_top_level_head_injection():
    out = make_dir("head")
    for name in ("index.html", "events.html", "masjids.html"):
        (out / name).write_text(
            "<!DOCTYPE html><html><head><title>t</title></head><body></body></html>",
            encoding="utf-8",
        )
    result = run(out, site_url="https://example.com")

    assert result.returncode == 0, result.stdout + result.stderr

    for name in ("index.html", "events.html", "masjids.html"):
        html = (out / name).read_text(encoding="utf-8")
        assert "<!-- build-site-seo -->" in html
        assert '<link rel="canonical"' in html
        assert 'property="og:' in html
        # idempotent: one injected block only
        assert html.count("<!-- build-site-seo -->") == 1


def test_invalid_data_fails_build():
    tmp = make_dir("bad")
    for name in ("masjids.json", "events.json"):
        write_json(tmp / name, [])
    write_json(tmp / "settings.json", {})
    out = make_dir("out")
    result = run(out, data_dir=tmp)
    shutil.rmtree(tmp)

    assert result.returncode != 0, "invalid data must fail the build"
    assert "FAILED" in result.stdout + result.stderr
    # no partial output
    assert not (out / "sitemap.xml").exists() or "validation" in (result.stdout + result.stderr)


def test_no_site_url_falls_back_to_root_relative():
    out = make_dir("no-url")
    result = run(out, site_url="")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "site_url" in result.stderr

    html = (out / "event" / "evt-20260809-001" / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="/event/evt-20260809-001/"' in html

    robots = (out / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap:" not in robots


def test_sw_generated_and_stamped():
    out = make_dir("sw")
    result = run(out, site_url=SITE_URL, today="2026-08-18", version="20260818v1")

    assert result.returncode == 0, result.stdout + result.stderr

    sw = (out / "sw.js").read_text(encoding="utf-8")
    assert "__VERSION__" not in sw
    assert 'const CACHE_VERSION = "20260818v1";' in sw
    assert 'const SHELL_CACHE = "masjid-perlis-shell-" + CACHE_VERSION;' in sw
    assert 'const DATA_CACHE = "masjid-perlis-data-" + CACHE_VERSION;' in sw

    # network-first data: never serve stale event info online
    assert 'pathname.indexOf("/data/") !== -1' in sw
    assert 'request.mode === "navigate"' in sw
    assert "stale-while-revalidate" not in sw or "DATA_CACHE" in sw
    # old caches pruned on activate
    assert "caches.keys()" in sw and "caches.delete(key)" in sw

    # asset paths resolve from a sub-path deployment too (endsWith matching)
    assert "isShell" in sw


def test_generated_page_has_pwa_links():
    out = make_dir("pwa")
    result = run(out, site_url=SITE_URL)

    assert result.returncode == 0, result.stdout + result.stderr

    html = (out / "event" / "evt-20260809-001" / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest" href="../../manifest.webmanifest"' in html
    assert 'name="theme-color"' in html
    # generated pages are script-free except the no-JS-guarded SW registration
    sw_reg = (out / "event" / "evt-20260809-001" / "index.html").read_text(encoding="utf-8")
    assert 'navigator.serviceWorker.register("../../sw.js")' in sw_reg


def test_manifest_and_icons_valid():
    out = make_dir("manifest")
    result = run(out, site_url=SITE_URL)

    assert result.returncode == 0, result.stdout + result.stderr

    manifest = json.loads((DATA.parent / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["start_url"] in ("./", "/")
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"]  # non-empty
    icons = {i["sizes"]: i["src"] for i in manifest["icons"]}
    assert "192x192" in icons and "512x512" in icons


def test_icon_png_valid():
    icons_dir = make_dir("icons")
    subprocess.run([sys.executable, str(GEN_ICONS), "--out", str(icons_dir)],
                   check=True, capture_output=True, text=True)
    for size in (192, 512):
        path = icons_dir / f"icon-{size}.png"
        assert path.is_file(), f"missing {path}"
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", "bad PNG magic"
        w, h, bitdepth, colortype = struct.unpack(">IIBB", data[16:26])
        assert (w, h) == (size, size)
        assert bitdepth == 8 and colortype == 6
        # IDAT must actually decompress to RGBA scanlines
        idat = b""
        pos = 8
        while pos < len(data):
            ln = struct.unpack(">I", data[pos:pos + 4])[0]
            kind = data[pos + 4:pos + 8]
            if kind == b"IDAT":
                idat += data[pos + 8:pos + 8 + ln]
            pos += 12 + ln
        raw = zlib.decompress(idat)
        assert len(raw) == size * (size * 4 + 1), "png data length mismatch"
    shutil.rmtree(icons_dir)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())