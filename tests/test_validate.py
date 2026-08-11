#!/usr/bin/env python3
"""Tests for tools/validate_data.py.

Usage:
    python3 tests/test_validate.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VALIDATE = Path(__file__).resolve().parent.parent / "tools" / "validate_data.py"
DATA = Path(__file__).resolve().parent.parent / "data"

VALID_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json",
               "settings.json", "mukims.json", "editors.json")


def run(data_dir):
    return subprocess.run(
        [sys.executable, str(VALIDATE), "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
    )


def copy_valid(dest):
    for name in VALID_FILES:
        shutil.copy(DATA / name, dest / name)


def make_dir(name):
    tmp = Path(tempfile.mkdtemp(prefix=f"mvp-{name}-"))
    return tmp


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def test_valid_passes():
    tmp = make_dir("valid")
    copy_valid(tmp)
    result = run(tmp)
    shutil.rmtree(tmp)
    assert result.returncode == 0, result.stdout + result.stderr


def test_broken_data_fails():
    tmp = make_dir("broken")
    copy_valid(tmp)

    bad_categories = [
        {"id": "kuliyyah", "name": "Kuliyyah"},
        {"id": "kuliyyah", "name": "dup"},
    ]
    write_json(tmp / "categories.json", bad_categories)

    bad_events = [
        {
            "id": "evt-20260812-001",
            "title": "Ok",
            "masjid_id": "masjid-alwi",
            "date": "2026-08-12",
            "start_time": "20:00",
            "end_time": "19:00",
            "status": "published",
        },
        {
            "id": "evt-bad",
            "title": "",
            "masjid_id": "masjid-unknown",
            "date": "2026-13-45",
            "start_time": "25:99",
            "status": "weird",
            "recurrence": {"type": "monthly", "days": [], "start_date": "bad"},
        },
    ]
    write_json(tmp / "events.json", bad_events)

    result = run(tmp)
    shutil.rmtree(tmp)
    out = result.stdout + result.stderr
    assert result.returncode != 0, "broken data must fail"
    assert "duplicate id" in out
    assert "end_time" in out
    assert "invalid date" in out
    assert "invalid time" in out
    assert "invalid status" in out
    assert "unknown masjid_id" in out
    assert "invalid recurrence type" in out
    assert "missing required field 'title'" in out


def test_masjid_mukim_reference_fails():
    tmp = make_dir("mukim-ref")
    copy_valid(tmp)

    bad_masjids = [
        {
            "id": "masjid-x",
            "name": "Masjid X",
            "mukim": "Kangar",
            "mukim_id": "kangar",
            "state": "Perlis",
        },
        {
            "id": "masjid-y",
            "name": "Masjid Y",
            "mukim": "Arau",
            "mukim_id": "mukim-tak-wujud",
            "state": "Perlis",
        },
        {
            "id": "masjid-z",
            "name": "Masjid Z",
            "mukim": "Arau",
            "mukim_id": "kangar",
            "state": "Perlis",
        },
    ]
    write_json(tmp / "masjids.json", bad_masjids)

    result = run(tmp)
    shutil.rmtree(tmp)
    out = result.stdout + result.stderr
    assert result.returncode != 0
    assert "unknown mukim_id" in out
    assert "does not match the name of mukim_id" in out


def test_missing_mukim_id_fails():
    tmp = make_dir("no-mukim-id")
    copy_valid(tmp)

    bad_masjids = [{
        "id": "masjid-x",
        "name": "Masjid X",
        "mukim": "Kangar",
        "state": "Perlis",
    }]
    write_json(tmp / "masjids.json", bad_masjids)

    result = run(tmp)
    shutil.rmtree(tmp)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "mukim_id" in result.stdout + result.stderr


def test_recurrence_exceptions_fails():
    tmp = make_dir("exceptions")
    copy_valid(tmp)
    bad_events = [
        {
            "id": "evt-20260812-001",
            "title": "Recurring",
            "masjid_id": "masjid-alwi",
            "date": "2026-08-12",
            "start_time": "20:00",
            "status": "published",
            "recurrence": {
                "type": "weekly",
                "days": ["wednesday"],
                "start_date": "2026-08-12",
                "end_date": None,
                "exceptions": ["2026-08-19", "not-a-date", "2026-08-19"],
            },
        }
    ]
    write_json(tmp / "events.json", bad_events)
    result = run(tmp)
    shutil.rmtree(tmp)
    out = result.stdout + result.stderr
    assert result.returncode != 0, "bad exceptions must fail"
    assert "exceptions" in out
    assert "not-a-date" in out, out
    assert "duplicate" in out, out


def test_valid_recurrence_exceptions_pass():
    tmp = make_dir("exceptions-ok")
    copy_valid(tmp)
    ok_events = [
        {
            "id": "evt-20260812-001",
            "title": "Recurring",
            "masjid_id": "masjid-alwi",
            "date": "2026-08-12",
            "start_time": "20:00",
            "status": "published",
            "recurrence": {
                "type": "weekly",
                "days": ["wednesday"],
                "start_date": "2026-08-12",
                "end_date": None,
                "exceptions": ["2026-08-19", "2026-09-02"],
            },
        }
    ]
    write_json(tmp / "events.json", ok_events)
    result = run(tmp)
    shutil.rmtree(tmp)
    assert result.returncode == 0, result.stdout + result.stderr


def test_malformed_json_fails():
    tmp = make_dir("malformed")
    copy_valid(tmp)
    (tmp / "events.json").write_text('{"id": "evt-1", "title": broken', encoding="utf-8")
    result = run(tmp)
    shutil.rmtree(tmp)
    assert result.returncode != 0
    assert "malformed JSON" in result.stdout + result.stderr


def test_missing_file_fails():
    tmp = make_dir("missing")
    copy_valid(tmp)
    (tmp / "events.json").unlink()
    result = run(tmp)
    shutil.rmtree(tmp)
    assert result.returncode != 0
    assert "events.json" in result.stdout + result.stderr
    assert "file not found" in result.stdout + result.stderr


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