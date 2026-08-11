#!/usr/bin/env python3
"""Tests for tools/federate.py (multiple event feeds).

Runs the federation tool against JSON fixtures (local files + a local HTTP
endpoint) and offline CSV "Google Sheets" feeds on throwaway data dirs so the
repo's real data/ is never touched.

Usage:
    python3 tests/test_federate.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEDERATE = ROOT / "tools" / "federate.py"
DATA = ROOT / "data"

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json",
              "settings.json", "mukims.json", "editors.json")


def run(feeds_path, data_dir, *extra):
    return subprocess.run(
        [sys.executable, str(FEDERATE), "--config", str(feeds_path),
         "--data-dir", str(data_dir), *extra],
        capture_output=True, text=True,
    )


def make_env():
    tmp = Path(tempfile.mkdtemp(prefix="mvp-federate-"))
    data_dir = tmp / "data"
    shutil.copytree(DATA, data_dir)
    return tmp, data_dir


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_config(tmp, feeds):
    path = tmp / "config.json"
    write_json(path, {"feeds": feeds})
    return path


def csv_str(header, rows):
    def cell(c):
        c = "" if c is None else str(c)
        return '"' + c.replace('"', '""') + '"' if ("," in c or '"' in c) else c
    return "\n".join([",".join(header)] +
                     [",".join(cell(c) for c in row) for row in rows]) + "\n"


# ---------------------------------------------------------------------------
# local-json feeds
# ---------------------------------------------------------------------------

def test_federation_aggregates_and_updates():
    tmp, data_dir = make_env()
    feed1 = tmp / "feed1.json"
    write_json(feed1, {
        "masjids": [
            {"name": "Masjid Zakat Kangar", "mukim": "Kangar"}
        ],
        "speakers": [
            {"name": "Ustaz Satu", "description": "juru dakwah"}
        ],
        "events": [
            {"title": "Kuliyyah Zakat", "masjid_id": "Masjid Zakat Kangar",
             "date": "2026-11-01", "start_time": "20:00", "speaker_id": "Ustaz Satu"},
        ],
    })
    feed2 = tmp / "feed2.json"
    write_json(feed2, {
        "masjids": [
            {"id": "masjid-zakat-kangar", "name": "Masjid Zakat Kangar (Baharu)",
             "mukim": "Kangar"},
        ],
        "events": [
            {"title": "Ceramah Cawangan", "masjid_id": "Masjid Zakat Kangar (Baharu)",
             "date": "2026-11-02", "start_time": "21:00"},
        ],
    })
    config = write_config(tmp, [
        {"name": "f1", "type": "local-json", "path": str(feed1),
         "collections": ["masjids", "speakers", "events"]},
        {"name": "f2", "type": "local-json", "path": str(feed2),
         "collections": ["masjids", "events"]},
    ])
    result = run(config, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        masjids = read_json(data_dir / "masjids.json")
        events = read_json(data_dir / "events.json")
        speakers = read_json(data_dir / "speakers.json")

        by_id = {m["id"]: m for m in masjids}
        # feed2 updates the masjid created by feed1 (by id), mukim preserved
        assert by_id["masjid-zakat-kangar"]["name"] == "Masjid Zakat Kangar (Baharu)"
        assert by_id["masjid-zakat-kangar"]["mukim_id"] == "kangar"
        # existing real masjids are kept (no pruning)
        assert "masjid-alwi" in by_id

        # speakers merged
        assert any(s["name"] == "Ustaz Satu" for s in speakers)

        # both events present with unique ids; references resolved by display name
        ev_titles = {e["title"]: e for e in events}
        assert "Kuliyyah Zakat" in ev_titles
        assert "Ceramah Cawangan" in ev_titles
        assert ev_titles["Kuliyyah Zakat"]["masjid_id"] == "masjid-zakat-kangar"
        assert ev_titles["Ceramah Cawangan"]["masjid_id"] == "masjid-zakat-kangar"
        ids = [e["id"] for e in events]
        assert len(ids) == len(set(ids)), ids

        # existing real events preserved
        assert any(e["id"] == "evt-20260809-001" for e in events)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_invalid_rows_and_unknown_reference_skipped():
    tmp, data_dir = make_env()
    feed = tmp / "feed.json"
    write_json(feed, {
        "events": [
            {"title": "Acara Sah", "masjid_id": "masjid-alwi",
             "date": "2026-11-03", "start_time": "20:00"},
            {"title": "Tarikh Buruk", "masjid_id": "masjid-alwi",
             "date": "05/11/2026", "start_time": "20:00"},
            {"title": "Rujukan Buruk", "masjid_id": "Masjid Tak Wujud",
             "date": "2026-11-04", "start_time": "20:00"},
        ],
    })
    config = write_config(tmp, [
        {"name": "badfeed", "type": "local-json", "path": str(feed),
         "collections": ["events"]},
    ])
    result = run(config, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        events = read_json(data_dir / "events.json")
        titles = {e["title"] for e in events}
        assert "Acara Sah" in titles
        assert "Tarikh Buruk" not in titles       # invalid date -> skipped
        assert "Rujukan Buruk" not in titles      # unknown reference -> skipped
        assert "Skipped rows" in result.stdout
        assert "invalid date" in result.stdout
        assert "unknown reference" in result.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_validation_failure_aborts_without_writing():
    tmp, data_dir = make_env()
    feed = tmp / "feed.json"
    # unrecognised mukim => mukim_id stays None => merged set invalid
    write_json(feed, {
        "masjids": [{"name": "Masjid Jauh", "mukim": "Fakelande"}],
    })
    config = write_config(tmp, [
        {"name": "badmasjid", "type": "local-json", "path": str(feed),
         "collections": ["masjids"]},
    ])
    before = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
    result = run(config, data_dir)
    try:
        assert result.returncode == 2, result.stdout + result.stderr
        assert "ABORTED" in result.stdout + result.stderr
        assert "mukim_id" in result.stdout + result.stderr
        after = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        assert before == after, "abort must leave data/ untouched"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_dry_run_writes_nothing():
    tmp, data_dir = make_env()
    feed = tmp / "feed.json"
    write_json(feed, {
        "events": [{"title": "Acara Dry", "masjid_id": "masjid-alwi",
                    "date": "2026-11-05", "start_time": "20:00"}],
    })
    config = write_config(tmp, [
        {"name": "dry", "type": "local-json", "path": str(feed),
         "collections": ["events"]},
    ])
    before = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
    result = run(config, data_dir, "--dry-run")
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        after = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        assert before == after, "--dry-run must not modify data"
        assert "Dry run" in result.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_strict_aborts_on_skip():
    tmp, data_dir = make_env()
    feed = tmp / "feed.json"
    write_json(feed, {
        "events": [
            {"title": "Baik", "masjid_id": "masjid-alwi",
             "date": "2026-11-06", "start_time": "20:00"},
            {"title": "Buruk", "masjid_id": "masjid-alwi",
             "date": "not-a-date", "start_time": "20:00"},
        ],
    })
    config = write_config(tmp, [
        {"name": "strict", "type": "local-json", "path": str(feed),
         "collections": ["events"]},
    ])
    # non-strict: runs, one row skipped
    result = run(config, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr

        # strict: abort, nothing written
        before = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        result = run(config, data_dir, "--strict")
        assert result.returncode == 2, result.stdout + result.stderr
        after = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        assert before == after, "strict failure must not write"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# json-url feed (local HTTP endpoint)
# ---------------------------------------------------------------------------

class _FeedHandler(BaseHTTPRequestHandler):
    payload = b"{}"

    def do_GET(self):
        body = self.payload
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output clean
        pass


def test_json_url_feed():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FeedHandler)
    _FeedHandler.payload = json.dumps({
        "masjids": [{"name": "Masjid Web", "mukim": "Arau"}],
        "events": [{"title": "Acara Web", "masjid_id": "Masjid Web",
                    "date": "2026-11-07", "start_time": "20:00"}],
    }, ensure_ascii=False).encode("utf-8")
    url = f"http://127.0.0.1:{server.server_address[1]}/events.json"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    tmp, data_dir = make_env()
    try:
        config = write_config(tmp, [
            {"name": "web", "type": "json-url", "url": url,
             "collections": ["masjids", "events"]},
        ])
        result = run(config, data_dir)
        assert result.returncode == 0, result.stdout + result.stderr
        masjids = read_json(data_dir / "masjids.json")
        events = read_json(data_dir / "events.json")
        assert any(m["id"] == "masjid-web" and m["mukim_id"] == "arau" for m in masjids)
        assert any(e["title"] == "Acara Web" for e in events)
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# google-sheet feed (offline CSV) + cross-feed resolution
# ---------------------------------------------------------------------------

COLS = {
    "masjids": ["id", "Nama", "Mukim", "Negeri"],
    "speakers": ["id", "Nama", "Penerangan"],
    "categories": ["id", "Nama"],
    "events": ["id", "Tajuk", "Masjid", "Tarikh", "Mula", "Penceramah",
               "Kategori", "Status"],
}
MAP = {
    "masjids": {"Nama": "name", "Mukim": "mukim", "Negeri": "state"},
    "speakers": {"Nama": "name", "Penerangan": "description"},
    "categories": {"Nama": "name"},
    "events": {"Tajuk": "title", "Masjid": "masjid_id", "Tarikh": "date",
               "Mula": "start_time", "Penceramah": "speaker_id",
               "Kategori": "category_id", "Status": "status"},
}


def write_csv(tmp, name, rows):
    (tmp / (name + ".csv")).write_text(csv_str(COLS[name], rows), encoding="utf-8")


def sheet_feed(tmp):
    write_csv(tmp, "masjids", [
        [None, "Masjid Cawangan", "Kangar", "Perlis"],
    ])
    write_csv(tmp, "speakers", [[None, "Ustaz Cawangan", "Penceramah"]])
    write_csv(tmp, "categories", [[None, "Kuliyyah Cawangan"]])
    write_csv(tmp, "events", [
        [None, "Kuliyyah Cawangan", "Masjid Cawangan", "2026-11-08", "20:00",
         "Ustaz Cawangan", "Kuliyyah Cawangan", "published"],
    ])

    def src(kind):
        return {"tab": kind, "file": str(tmp / (kind + ".csv")),
                "columns": MAP[kind]}

    return {"name": "sheet", "type": "google-sheet", "spreadsheet_id": "",
            "sources": {k: src(k) for k in ("masjids", "speakers", "categories", "events")}}


def test_google_sheet_feed_with_cross_feed_json():
    tmp, data_dir = make_env()
    feed_json = tmp / "json.json"
    # json feed references the sheet-created masjid by display name
    write_json(feed_json, {
        "events": [{"title": "Acara Gabungan", "masjid_id": "Masjid Cawangan",
                    "date": "2026-11-09", "start_time": "21:00"}],
    })
    config = write_config(tmp, [
        sheet_feed(tmp),
        {"name": "json", "type": "local-json", "path": str(feed_json),
         "collections": ["events"]},
    ])
    result = run(config, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        masjids = read_json(data_dir / "masjids.json")
        events = read_json(data_dir / "events.json")
        assert any(m["id"] == "masjid-cawangan" and m["mukim_id"] == "kangar"
                   for m in masjids)
        by_title = {e["title"]: e for e in events}
        assert "Kuliyyah Cawangan" in by_title
        assert "Acara Gabungan" in by_title
        assert by_title["Acara Gabungan"]["masjid_id"] == "masjid-cawangan", by_title["Acara Gabungan"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
        except Exception as exc:
            failed += 1
            print(f"ERROR {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())