#!/usr/bin/env python3
"""Tests for tools/import_google_sheet.py (Google Sheets / CSV adapter).

Runs the importer against offline CSV fixtures and a throwaway data dir so
the repo's real data/ is never touched.

Usage:
    python3 tests/test_import_sheet.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPORTER = ROOT / "tools" / "import_google_sheet.py"
DATA = ROOT / "data"

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json", "settings.json")

# Malay column headers + field mapping matching tools/sheets_import.example.json
COLS = {
    "masjids": ["id", "Nama", "Daerah", "Negeri", "Alamat", "Latitud", "Longitud", "Kenalan", "Laman web"],
    "speakers": ["id", "Nama", "Penerangan"],
    "categories": ["id", "Nama"],
    "events": [
        "id", "Tajuk", "Masjid", "Tarikh", "Mula", "Tamat", "Penceramah",
        "Kategori", "Lokasi", "Penerangan", "Status",
        "Jenis ulangan", "Hari ulangan", "Mula ulangan", "Tamat ulangan", "Pengecualian",
    ],
}

MAP = {
    "masjids": {"id": "id", "Nama": "name", "Daerah": "district", "Negeri": "state",
                "Alamat": "address", "Latitud": "latitude", "Longitud": "longitude",
                "Kenalan": "contact", "Laman web": "website"},
    "speakers": {"id": "id", "Nama": "name", "Penerangan": "description"},
    "categories": {"id": "id", "Nama": "name"},
    "events": {
        "id": "id", "Tajuk": "title", "Masjid": "masjid_id", "Tarikh": "date",
        "Mula": "start_time", "Tamat": "end_time", "Penceramah": "speaker_id",
        "Kategori": "category_id", "Lokasi": "location", "Penerangan": "description",
        "Status": "status", "Jenis ulangan": "recurrence_type",
        "Hari ulangan": "recurrence_days", "Mula ulangan": "recurrence_start_date",
        "Tamat ulangan": "recurrence_end_date", "Pengecualian": "recurrence_exceptions",
    },
}


def csv_str(header, rows):
    out = [",".join(header)]
    for row in rows:
        cells = ["" if v is None else str(v) for v in row]
        out.append(",".join('"' + c.replace('"', '""') + '"' if ("," in c or '"' in c) else c for c in cells))
    return "\n".join(out) + "\n"


def make_env():
    tmp = Path(tempfile.mkdtemp(prefix="mvp-sheet-"))
    data_dir = tmp / "data"
    shutil.copytree(DATA, data_dir)
    return tmp, data_dir


def write_csv(tmp, name, header, rows):
    (tmp / name).write_text(csv_str(header, rows), encoding="utf-8")


def write_config(tmp, spreadsheet_id=None):
    tabs = {"masjids": "Masjids", "speakers": "Penceramah",
            "categories": "Kategori", "events": "Acara"}

    def src(kind):
        return {"tab": tabs[kind], "file": str(tmp / (kind + ".csv")),
                "columns": MAP[kind], "id_column": "id"}

    cfg = {
        "spreadsheet_id": spreadsheet_id or "",
        "sources": {k: src(k) for k in ("masjids", "speakers", "categories", "events")},
    }
    path = tmp / "config.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return path


def run(tmp, data_dir, *extra):
    return subprocess.run(
        [sys.executable, str(IMPORTER), "--config", str(tmp / "config.json"),
         "--data-dir", str(data_dir), *extra],
        capture_output=True, text=True,
    )


def read_json(data_dir, name):
    return json.loads((data_dir / name).read_text(encoding="utf-8"))


def test_happy_merge_add_update_skip():
    tmp, data_dir = make_env()
    write_csv(tmp, "masjids.csv", COLS["masjids"], [
        ["masjid-alwi", "Masjid Alwi (Baharu)", "Kangar", "Perlis", None, None, None, None, None],
        [None, "Masjid Import Satu", "Arau", "Perlis", None, None, None, None, None],
    ])
    write_csv(tmp, "speakers.csv", COLS["speakers"], [
        [None, "Ustaz Import Satu", "Penceramah jemputan"],
    ])
    write_csv(tmp, "categories.csv", COLS["categories"], [
        [None, "Kuliyyah Import"],
    ])
    write_csv(tmp, "events.csv", COLS["events"], [
        # new event referencing the new masjid/speaker/category by NAME
        [None, "Ceramah Import", "Masjid Import Satu", "2026-10-05", "20:00", "21:00",
         "Ustaz Import Satu", "Kuliyyah Import", None, "Keterangan ujian", "published", None, None, None, None, None],
        # update an existing event (change start time)
        ["evt-20260809-001", "Kuliyyah Maghrib: Keutamaan Ilmu", "masjid-alwi",
         "2026-08-09", "21:15", None, None, None, None, None, "published", None, None, None, None, None],
        # invalid date -> skipped
        [None, "Acara Tak Sah", "masjid-alwi", "05/10/2026", "20:00", None, None, None,
         None, None, "published", None, None, None, None, None],
        # references an unknown masjid name -> skipped
        [None, "Acara Rujukan Buruk", "Masjid Tak Wujud", "2026-10-06", "20:00", None,
         None, None, None, None, "published", None, None, None, None, None],
    ])
    write_config(tmp)

    result = run(tmp, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        masjids = read_json(data_dir, "masjids.json")
        events = read_json(data_dir, "events.json")
        speakers = read_json(data_dir, "speakers.json")
        categories = read_json(data_dir, "categories.json")

        by_id = {m["id"]: m for m in masjids}
        # update applied
        assert by_id["masjid-alwi"]["name"] == "Masjid Alwi (Baharu)", by_id["masjid-alwi"]
        # district_id derived from the free-text district column
        assert by_id["masjid-alwi"]["district_id"] == "kangar", by_id["masjid-alwi"]
        # new masjid added (kept others, not pruned)
        assert "masjid-import-satu" in by_id
        assert by_id["masjid-import-satu"]["district_id"] == "arau", by_id["masjid-import-satu"]
        assert "masjid-ar-rahmah" in by_id and "masjid-an-nur" in by_id

        # new speaker/category added
        assert any(s["name"] == "Ustaz Import Satu" for s in speakers)
        assert any(c["name"] == "Kuliyyah Import" for c in categories)

        ev_by_title = {e["title"]: e for e in events}
        assert "Ceramah Import" in ev_by_title
        new_ev = ev_by_title["Ceramah Import"]
        assert new_ev["masjid_id"] == "masjid-import-satu"
        assert new_ev["speaker_id"] == "speaker-ustaz-import-satu", new_ev
        assert new_ev["category_id"] == "kuliyyah-import", new_ev
        assert new_ev["id"].startswith("evt-20261005-"), new_ev["id"]

        # existing records untouched (count preserved + updated one)
        assert not any(e["title"] == "Acara Tak Sah" for e in events)
        assert not any(e["title"] == "Acara Rujukan Buruk" for e in events)
        updated = next(e for e in events if e["id"] == "evt-20260809-001")
        assert updated["start_time"] == "21:15", updated

        # skipped rows were reported
        assert "rst row" not in result.stdout  # sanity: header offsets reported
        assert "unknown reference" in result.stdout
        assert "invalid date" in result.stdout
        assert "skipped" in result.stdout.lower()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_duplicate_explicit_id_skipped_strict_aborts():
    tmp, data_dir = make_env()
    write_csv(tmp, "masjids.csv", COLS["masjids"], [
        ["masjid-dupe", "Masjid Dupe Satu", "Padang Besar", None, None, None, None, None, None],
        ["masjid-dupe", "Masjid Dupe Dua", "Padang Besar", None, None, None, None, None, None],
    ])
    write_csv(tmp, "speakers.csv", COLS["speakers"], [])
    write_csv(tmp, "categories.csv", COLS["categories"], [])
    write_csv(tmp, "events.csv", COLS["events"], [])
    write_config(tmp)

    # non-strict: runs, one row skipped, nothing broken
    result = run(tmp, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "duplicate id" in result.stdout
        masjids = read_json(data_dir, "masjids.json")
        dupes = [m for m in masjids if m["id"] == "masjid-dupe"]
        assert len(dupes) == 1, dupes  # first occurrence kept, duplicate skipped

        # strict: abort, nothing written
        before = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        result = run(tmp, data_dir, "--strict")
        assert result.returncode == 2, result.stdout + result.stderr
        after = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        assert before == after, "strict failure must not write"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_validation_failure_aborts_without_writing():
    import importlib.util
    tmp, data_dir = make_env()
    write_csv(tmp, "masjids.csv", COLS["masjids"], [[None, "Masjid X", None, None, None, None, None, None, None]])
    write_csv(tmp, "speakers.csv", COLS["speakers"], [])
    write_csv(tmp, "categories.csv", COLS["categories"], [])
    write_csv(tmp, "events.csv", COLS["events"], [])
    config_path = write_config(tmp)

    # Load the module in-process so validate_directory can be patched (the
    # CLI subprocess would import a fresh copy and ignore the patch).
    spec = importlib.util.spec_from_file_location("import_google_sheet", IMPORTER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["import_google_sheet"] = mod
    spec.loader.exec_module(mod)
    original = mod.validate_directory

    def _fake(_data_dir):
        return ["synthetic validation problem"]

    mod.validate_directory = _fake
    try:
        code = mod.main(["--config", str(config_path), "--data-dir", str(data_dir)])
    finally:
        mod.validate_directory = original
        sys.modules.pop("import_google_sheet", None)

    assert code == 2, code
    # untouched == same as a pristine copy
    pristine = Path(tempfile.mkdtemp(prefix="mvp-sheet-pristine-"))
    shutil.copytree(DATA, pristine / "data")
    try:
        for f in DATA_FILES:
            assert (data_dir / f).read_bytes() == (pristine / "data" / f).read_bytes(), f
    finally:
        shutil.rmtree(pristine, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


def test_dry_run_writes_nothing():
    tmp, data_dir = make_env()
    write_csv(tmp, "masjids.csv", COLS["masjids"], [[None, "Masjid Dry", "Kangar", None, None, None, None, None, None]])
    write_csv(tmp, "speakers.csv", COLS["speakers"], [])
    write_csv(tmp, "categories.csv", COLS["categories"], [])
    write_csv(tmp, "events.csv", COLS["events"], [])
    write_config(tmp)
    before = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
    result = run(tmp, data_dir, "--dry-run")
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        after = {f: (data_dir / f).read_bytes() for f in DATA_FILES}
        assert before == after, "--dry-run must not modify data"
        assert "Dry run" in result.stdout
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