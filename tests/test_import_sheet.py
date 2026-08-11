#!/usr/bin/env python3
"""Tests for tools/import_google_sheet.py (Google Sheets / CSV adapter).

Runs the importer against offline CSV fixtures and a throwaway data dir so
the repo's real data/ is never touched.

Usage:
    python3 tests/test_import_sheet.py
"""

import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPORTER = ROOT / "tools" / "import_google_sheet.py"
DATA = ROOT / "data"

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json", "settings.json")

# Malay column headers + field mapping matching tools/sheets_import.example.json
COLS = {
    "masjids": ["id", "Nama", "Mukim", "Negeri", "Alamat", "Latitud", "Longitud", "Kenalan", "Laman web"],
    "speakers": ["id", "Nama", "Penerangan"],
    "categories": ["id", "Nama"],
    "events": [
        "id", "Tajuk", "Masjid", "Tarikh", "Mula", "Tamat", "Penceramah",
        "Kategori", "Lokasi", "Penerangan", "Status",
        "Jenis ulangan", "Hari ulangan", "Mula ulangan", "Tamat ulangan", "Pengecualian",
    ],
}

MAP = {
    "masjids": {"id": "id", "Nama": "name", "Mukim": "mukim", "Negeri": "state",
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


_XLSX_NS_URL = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def build_xlsx(path, headers, rows, fmt_cols=None, sheet_name="Acara"):
    """Write a minimal .xlsx workbook (stdlib only) for importer tests.

    fmt_cols maps column letter -> (numfmt_id, format_code); data cells in
    those columns carry that style and are emitted as numbers (Excel serials)
    so the reader converts them with the workbook's number formats. Header
    cells and all other string cells use the shared-string table.
    """
    fmt_cols = fmt_cols or {}
    shared = []
    shared_idx = {}
    letters = [chr(ord("A") + i) for i in range(len(headers))]

    # xf index 0 = plain cells; each formatted column points at the xf entry
    # built from its numFmtId (in sorted order).
    xf_index = {fid: i + 1 for i, fid in enumerate(sorted({fid for fid, _ in fmt_cols.values()}))}
    style_for_col = {col: xf_index[fid] for col, (fid, _) in fmt_cols.items()}

    def _cell(ref, value, styled=False):
        if value is None:
            return f'<c r="{ref}"/>'
        if styled:
            return f'<c r="{ref}" s="{style_for_col[ref.rstrip("0123456789")]}"><v>{value}</v></c>'
        if value in shared_idx:
            return f'<c r="{ref}" t="s"><v>{shared_idx[value]}</v></c>'
        shared_idx[value] = len(shared)
        shared.append(value)
        return f'<c r="{ref}" t="s"><v>{shared_idx[value]}</v></c>'

    def _row(r, values):
        cells = []
        for letter, value in zip(letters, values):
            styled = r > 1 and letter in style_for_col
            cells.append(_cell(letter + str(r), value, styled=styled))
        return f'<row r="{r}">{"".join(cells)}</row>'

    sheet_data = _row(1, headers)
    for r, values in enumerate(rows, start=2):
        sheet_data += _row(r, values)

    numfmts = "".join(
        f'<numFmt numFmtId="{fid}" formatCode="{code}"/>' for fid, code in fmt_cols.values())
    xfs = '<xf numFmtId="0" applyNumberFormat="0"/>' + "".join(
        f'<xf numFmtId="{fid}" applyNumberFormat="1"/>' for fid in sorted(xf_index))
    sst = "".join(f"<si><t>{v}</t></si>" for v in shared)

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<workbook xmlns="{_XLSX_NS_URL}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<worksheet xmlns="{_XLSX_NS_URL}"><sheetData>{sheet_data}</sheetData></worksheet>'
    )
    shared_strings = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<sst xmlns="{_XLSX_NS_URL}" count="{len(shared)}" uniqueCount="{len(shared)}">{sst}</sst>'
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<styleSheet xmlns="{_XLSX_NS_URL}">'
        f'<numFmts count="{len(fmt_cols)}">{numfmts}</numFmts>'
        f'<cellXfs count="{len(xf_index) + 1}">{xfs}</cellXfs>'
        '</styleSheet>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet)
        zf.writestr("xl/sharedStrings.xml", shared_strings)
        zf.writestr("xl/styles.xml", styles)


def excel_serial(date_or_time):
    """Convert a date or (hours, minutes) into an Excel serial number."""
    if isinstance(date_or_time, tuple):  # (h, m) -> fraction of a day
        return round(date_or_time[0] / 24 + date_or_time[1] / 1440, 12)
    return (date_or_time - datetime.date(1899, 12, 30)).days


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
        # mukim_id derived from the free-text mukim column
        assert by_id["masjid-alwi"]["mukim_id"] == "kangar", by_id["masjid-alwi"]
        # new masjid added (kept others, not pruned)
        assert "masjid-import-satu" in by_id
        assert by_id["masjid-import-satu"]["mukim_id"] == "arau", by_id["masjid-import-satu"]
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


def test_unquoted_comma_is_reported_not_crashing():
    # A comma-separated value (e.g. unquoted "monday,friday") becomes extra
    # CSV columns; the importer must fail with a clear message, never crash
    # with a traceback or silently drop data.
    tmp, data_dir = make_env()
    header = COLS["events"]
    row = ["", "Ceramah", "Masjid Alwi", "2026-08-20", "20:00", "21:00",
           "Ustaz A", "Kuliah", "", "", "published", "weekly",
           "monday,friday", "2026-08-20", "2026-12-31", "2026-08-28"]
    # force the row unquoted so "monday,friday" splits into two CSV columns
    (tmp / "events.csv").write_text(",".join(header) + "\n" + ",".join(row) + "\n", encoding="utf-8")
    write_csv(tmp, "masjids.csv", COLS["masjids"], [[None, "Masjid Alwi", "Kangar", None, None, None, None, None, None]])
    write_csv(tmp, "speakers.csv", COLS["speakers"], [])
    write_csv(tmp, "categories.csv", COLS["categories"], [])
    write_config(tmp)
    result = run(tmp, data_dir)
    try:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "extra column" in result.stderr, result.stderr
        assert "Traceback" not in result.stderr, result.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_partial_import_events_only():
    # Only the events source is configured; the other collections must pass
    # through unchanged (daily-driver scenario: maintain only events).
    tmp, data_dir = make_env()
    (tmp / "config.json").write_text(json.dumps({
        "spreadsheet_id": "",
        "sources": {
            "events": {"file": "acara.csv", "id_column": "id",
                       "columns": MAP["events"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    (tmp / "acara.csv").write_text(csv_str(COLS["events"], [
        [None, "Acara Sahaja", "Masjid Alwi", "2026-09-01", "09:00", "10:00",
         None, None, None, None, "published", None, None, None, None, None],
    ]), encoding="utf-8")
    before = read_json(data_dir, "masjids.json")
    result = run(tmp, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "kept unchanged" in result.stdout, result.stdout
        assert read_json(data_dir, "masjids.json") == before
        events = read_json(data_dir, "events.json")
        assert any(e["title"] == "Acara Sahaja" for e in events)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_relative_file_paths_resolve_against_config_dir():
    # A config that uses bare relative "file" names must resolve them against
    # the config file's directory, not the CWD.
    tmp, data_dir = make_env()
    cfg_dir = tmp / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "acara.csv").write_text(csv_str(COLS["events"], [
        [None, "Acara Relatif", "Masjid Alwi", "2026-09-02", "10:00", "11:00",
         None, None, None, None, "published", None, None, None, None, None],
    ]), encoding="utf-8")
    (cfg_dir / "config.json").write_text(json.dumps({
        "spreadsheet_id": "",
        "sources": {
            "events": {"file": "acara.csv", "id_column": "id",
                       "columns": MAP["events"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(IMPORTER), "--config", str(cfg_dir / "config.json"),
         "--data-dir", str(data_dir)],
        capture_output=True, text=True,
    )
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        assert any(e["title"] == "Acara Relatif" for e in read_json(data_dir, "events.json"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_xlsx_import_dates_times_and_comma_strings():
    # A native .xlsx workbook (as a non-technical user would save straight
    # from Excel) must import end to end: Excel date/time serials become
    # YYYY-MM-DD / HH:MM, and comma-containing strings such as "monday,friday"
    # are single cells — no CSV quoting foot-gun.
    tmp, data_dir = make_env()
    fmt = {"D": (164, "yyyy-mm-dd"), "E": (165, "hh:mm"),
           "F": (165, "hh:mm"), "N": (164, "yyyy-mm-dd")}
    build_xlsx(tmp / "acara.xlsx", COLS["events"], [[
        None, "Ceramah Excel", "masjid-alwi",
        excel_serial(datetime.date(2026, 8, 20)),  # Tarikh as a date serial
        excel_serial((20, 0)),                     # Mula as a time serial
        excel_serial((21, 0)),                     # Tamat as a time serial
        None, None, None, None, "published", "weekly",
        "monday,friday",                           # comma value = one cell
        excel_serial(datetime.date(2026, 8, 20)),  # Mula ulangan as date serial
        "2026-12-31", "2026-08-28,2026-09-04",
    ]], fmt_cols=fmt)
    (tmp / "config.json").write_text(json.dumps({
        "spreadsheet_id": "",
        "sources": {
            "events": {"file": "acara.xlsx", "id_column": "id",
                       "columns": MAP["events"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    result = run(tmp, data_dir)
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        events = read_json(data_dir, "events.json")
        ev = next(e for e in events if e["title"] == "Ceramah Excel")
        assert ev["date"] == "2026-08-20", ev
        assert ev["start_time"] == "20:00", ev
        assert ev["end_time"] == "21:00", ev
        assert ev["masjid_id"] == "masjid-alwi", ev
        assert ev["recurrence"]["days"] == ["monday", "friday"], ev
        assert ev["recurrence"]["start_date"] == "2026-08-20", ev
        assert ev["recurrence"]["exceptions"] == ["2026-08-28", "2026-09-04"], ev
        assert "extra column" not in result.stderr, result.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_xlsx_wrong_sheet_name_reports_clear_error():
    # A "sheet" entry that doesn't exist in the workbook must fail with a
    # clear message, never a traceback.
    tmp, data_dir = make_env()
    build_xlsx(tmp / "acara.xlsx", COLS["events"], [])
    (tmp / "config.json").write_text(json.dumps({
        "spreadsheet_id": "",
        "sources": {
            "events": {"file": "acara.xlsx", "sheet": "TidakWujud",
                       "id_column": "id", "columns": MAP["events"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    result = run(tmp, data_dir)
    try:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "TidakWujud" in result.stderr, result.stderr
        assert "Traceback" not in result.stderr, result.stderr
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