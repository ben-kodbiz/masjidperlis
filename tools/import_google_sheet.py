#!/usr/bin/env python3
"""Masjid Events Perlis — Google Sheets importer (adapter).

Optional data source. Reads published Google Sheets tabs (or local CSV / .xlsx
files) and merges their rows into the canonical JSON data set, then validates.

.xlsx workbooks are read natively with the Python standard library only
(zipfile + ElementTree, no third-party dependencies): Excel dates/times are
converted from their serial-number storage into the YYYY-MM-DD / HH:MM text
the importer expects, so you can keep editing files in Excel and save them
straight back as .xlsx — no CSV export step needed.

Pipeline:  Import rows -> Normalize to canonical JSON -> Merge (never
destroys existing records) -> Validate the merged set -> Write data/ only if
valid.

Constraints honoured (see DATA_SCHEMA.md / TODO_AGENT Stage 14):
  - No API key / secret needed. Sheets must be *published to the web*
    (File > Share > Publish to web), which provides a public CSV export URL.
  - Existing records that are not mentioned in the sheet are kept
    (records are only added or updated by ID, never deleted).
  - Invalid rows are reported with their row number and skipped; a row that
    fails is never written.
  - Duplicate IDs inside one sheet are detected and only the first row is
    used.
  - The merged result must pass tools/validate_data.py *before* anything is
    written; on failure the local data is untouched.

Usage:
    python3 tools/import_google_sheet.py                     # use config
    python3 tools/import_google_sheet.py --config tools/sheets_import.example.json
    python3 tools/import_google_sheet.py --spreadsheet-id 1AbC... --dry-run
    python3 tools/import_google_sheet.py --strict            # abort if any row skipped

Config (default: tools/sheets_import.json, else the .example.json):
    {
      "spreadsheet_id": "1AbCdE...",      # optional override on the CLI
      "sources": {
        "masjids":    { "tab": "Masjids",    "gid": "0",
                        "columns": {"Nama": "name", "Mukim": "mukim"} },
        "speakers":   { "tab": "Penceramah" },
        "categories": { "tab": "Kategori" },
        "events":     { "tab": "Acara" }
      }
    }

Each source:
  - "tab"      descriptive name (used in reports).
  - "gid"      Google tab id for remote export. Omit to use the first tab.
  - "file"     local CSV or .xlsx path (testing / offline / daily use). If set,
               "gid" is ignored and spreadsheet_id is not required.
  - "sheet"    optional worksheet name to read inside an .xlsx workbook.
               Defaults to the first (visible) worksheet.
  - "columns"  optional map of sheet column header -> canonical field name.
               When absent, headers must already equal canonical field names.
  - "id_column" optional header whose values are explicit canonical ids.
               When absent, stable ids are derived from the name (masjid /
               speaker / category) or date (event).

Event reference cells may contain either the canonical id or the display
name of a masjid / speaker / category (resolved against the merged data).
"""

import argparse
import csv
import datetime
import io
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "tools"))

from serve import (  # noqa: E402  (reuse the admin editor's normalization)
    VALID_RECURRENCE_TYPES,
    VALID_STATUSES,
    VALID_WEEKDAYS,
    mukim_id_for,
    next_category_id,
    next_event_id,
    next_masjid_id,
    next_speaker_id,
    validate_category,
    validate_event,
    validate_masjid,
    validate_speaker,
)
from validate_data import validate_directory  # noqa: E402

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json",
              "settings.json", "mukims.json", "editors.json")
KINDS = ("categories", "speakers", "masjids", "events")
ORDER_OF_KINDS = ("categories", "speakers", "masjids", "events")


class ImportConfig:
    def __init__(self, config, spreadsheet_id_override=None, strict=False, dry_run=False,
                 data_dir=None, config_path=None):
        self.config = config
        self.spreadsheet_id = spreadsheet_id_override or config.get("spreadsheet_id") or ""
        self.strict = strict
        self.dry_run = dry_run
        self.data_dir = Path(data_dir) if data_dir else ROOT / "data"
        self.config_dir = Path(config_path).resolve().parent if config_path else None
        self.paths = {f: self.data_dir / f for f in DATA_FILES}

    def source(self, kind):
        return self.config.get("sources", {}).get(kind)

    def source_file(self, kind):
        """Local CSV path for a source, resolved relative to the config file
        when possible (so 'file' entries work regardless of the CWD)."""
        source = self.source(kind)
        if not source or not source.get("file"):
            return None
        path = Path(source["file"])
        if not path.is_absolute() and self.config_dir is not None:
            path = self.config_dir / path
        return path.resolve()


def read_json(path, fallback=[]):
    if not Path(path).exists():
        return fallback
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_csv(stream):
    """Read CSV lines with a header row into a list of dicts (values trimmed)."""
    text = stream
    if hasattr(stream, "read"):
        text = stream.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    else:
        text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row_no, row in enumerate(reader, start=2):
        if row is None:
            continue
        # csv.DictReader stores any extra (beyond-header) columns under key
        # None as a list. Unquoted commas inside a field produce these, so
        # report a clear error instead of crashing or silently dropping data.
        extras = row.pop(None, None)
        if extras and any((e or "").strip() for e in extras):
            raise RuntimeError(
                f"CSV row {row_no}: {len(extras)} extra column(s) — a field "
                f"containing a comma must be quoted, e.g. \"monday,friday\" "
                f"(got {extras[:3]!r}).")
        rows.append({str(k).strip(): (v or "").strip() for k, v in row.items()})
    return rows


_XLSX_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_XLSX_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_XLSX_OFFICE_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# Excel built-in number-format ids (styles.xml) that render a date or a time.
# 14-22 and 27-36 are the classic date/time codes; 45-47 elapsed time.
_XLSX_DATE_FMTS = frozenset(
    (14, 15, 16, 17, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 50, 51, 52, 53, 54, 55, 56, 57, 58))
_XLSX_TIME_FMTS = frozenset((18, 19, 20, 21, 45, 46, 47))

# Excel serial-number epoch: serial 1 == 1900-01-01 (with the leap-year bug,
# serial 60 = the non-existent 1900-02-29, which no real user hits).
_XLSX_EPOCH = datetime.date(1899, 12, 30)


def _xlsx_col_index(cell_ref):
    letters = "".join(ch for ch in str(cell_ref) if ch.isalpha()).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1  # 0-based column index


def _xlsx_fmt_kind(format_code):
    """Classify a number-format code as 'date', 'time', or None (plain number)."""
    if not format_code:
        return None
    code = re.sub(r'"[^"]*"', "", format_code)      # drop quoted literals
    code = re.sub(r"\\.", "", code)                  # drop escaped chars
    # drop bracket sections that carry no date/time letters ([Red], [$-409]...)
    code = re.sub(r"\[([^\]hdmsy]*)\]", "", code)
    has_date = "y" in code or "d" in code or "mmm" in code
    has_time = "h" in code or "s" in code
    if has_date and has_time:
        return "datetime"
    if has_date:
        return "date"
    if has_time:
        return "time"
    # bare 'm' is ambiguous (month vs minute); with no h/s/y/d treat minute-only
    # formats like "mm:ss" as time.
    if "m" in code:
        return "time"
    return None


def _xlsx_serial_to_text(number, kind):
    """Turn an Excel serial into the text the importer expects."""
    number = float(number)
    if kind == "time":
        return _xlsx_fraction_to_time(number % 1)
    if kind == "datetime":
        if number % 1:
            return _xlsx_fraction_to_time(number % 1)
        return (_XLSX_EPOCH + datetime.timedelta(days=int(number))).isoformat()
    if kind == "date":
        return (_XLSX_EPOCH + datetime.timedelta(days=int(number))).isoformat()
    return str(number)


def _xlsx_fraction_to_time(fraction):
    minutes = int(round(fraction * 24 * 60)) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _pick_xlsx_sheet(zf, path, sheet_name):
    """Return the worksheet part path for the named (or first visible) sheet."""
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in zf.namelist():
        for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels")):
            rels[rel.get("Id")] = rel.get("Target")

    def _sheet_target(rid):
        target = rels.get(rid, "")
        if target.startswith("xl/"):
            return target
        return "xl/" + target.lstrip("/")

    sheets = []
    for sh in wb.iter(_XLSX_MAIN_NS + "sheet"):
        sheets.append((sh.get("name"), sh.get(_XLSX_OFFICE_NS + "id"), sh.get("state")))

    if sheet_name:
        for name, rid, _state in sheets:
            if name == sheet_name:
                return _sheet_target(rid)
        raise RuntimeError(f"sheet {sheet_name!r} not found in {path}")
    for _name, rid, state in sheets:
        if state and state.lower() in ("hidden", "veryhidden"):
            continue
        return _sheet_target(rid)
    if sheets:
        return _sheet_target(sheets[0][1])
    raise RuntimeError(f"no worksheets found in {path}")


def read_xlsx(path, sheet_name=None):
    """Read a .xlsx workbook into a list of dicts (first row = headers).

    Uses only the Python standard library (zipfile + ElementTree). Cell values
    are trimmed text; Excel date/time serials are converted to YYYY-MM-DD and
    HH:MM text based on the workbook's number formats, so a column a user typed
    a date into becomes the date string the importer expects.
    """
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())

        # shared string table (Excel stores repeated strings here, referenced
        # by cells with t="s")
        shared = []
        if "xl/sharedStrings.xml" in names:
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.iter(_XLSX_MAIN_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_XLSX_MAIN_NS + "t")))

        # number formats: id -> format code, plus the style-index -> fmt-id map
        numfmt = {}
        style_fmt = []
        if "xl/styles.xml" in names:
            styles = ET.fromstring(zf.read("xl/styles.xml"))
            for nf in styles.iter(_XLSX_MAIN_NS + "numFmt"):
                numfmt[int(nf.get("numFmtId", 0))] = nf.get("formatCode", "")
            for xf in styles.iter(_XLSX_MAIN_NS + "xf"):
                style_fmt.append(int(xf.get("numFmtId", 0)))

        def _cell_kind(style_id):
            fmt_id = 0
            if style_id is not None and style_id:
                try:
                    fmt_id = style_fmt[int(style_id)]
                except (ValueError, IndexError):
                    fmt_id = 0
            if fmt_id in _XLSX_TIME_FMTS:
                return "time"
            if fmt_id in _XLSX_DATE_FMTS:
                return "date"
            return _xlsx_fmt_kind(numfmt.get(fmt_id))

        sheet_path = _pick_xlsx_sheet(zf, path, sheet_name)
        root = ET.fromstring(zf.read(sheet_path))

        rows = []
        header = None
        for row in root.iter(_XLSX_MAIN_NS + "row"):
            cells = {}
            for c in row.iter(_XLSX_MAIN_NS + "c"):
                col = _xlsx_col_index(c.get("r"))
                if col < 0:
                    continue
                cell_type = c.get("t")
                v = c.find(_XLSX_MAIN_NS + "v")
                if cell_type == "s":
                    sid = int(v.text) if v is not None and v.text else 0
                    val = shared[sid] if 0 <= sid < len(shared) else ""
                elif cell_type == "inlineStr":
                    is_node = c.find(_XLSX_MAIN_NS + "is")
                    if is_node is not None:
                        val = "".join(t.text or "" for t in is_node.iter(_XLSX_MAIN_NS + "t"))
                    else:
                        val = ""
                elif v is not None and v.text:
                    val = _xlsx_serial_to_text(v.text, _cell_kind(c.get("s")))
                else:
                    val = ""
                cells[col] = val.strip()
            if not cells:
                continue
            values = [cells.get(i, "") for i in range(max(cells) + 1)]
            if header is None:
                header = [h.strip() for h in values]
                continue
            rows.append({header[i]: values[i] for i in range(min(len(header), len(values)))})
        return rows


def fetch_tab_csv(spreadsheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
    if gid:
        url += f"&gid={gid}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return read_csv(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"cannot fetch {url}: HTTP {exc.code} "
                           "(is the sheet shared and published to web?)") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot fetch {url}: {exc}") from exc


def load_rows(source, spreadsheet_id, file_path=None):
    """Return (rows, source_label) for one sheet source."""
    if source is None:
        return None, None
    if source.get("file") or file_path is not None:
        path = file_path or Path(source["file"]).resolve()
        if not path.is_file():
            raise RuntimeError(f"local file not found: {path}")
        if path.suffix.lower() == ".xlsx":
            return read_xlsx(path, source.get("sheet")), f"file {path}"
        with open(path, "r", encoding="utf-8-sig") as fh:
            return read_csv(fh), f"file {path}"
    if not spreadsheet_id:
        raise RuntimeError("no spreadsheet_id configured and no local 'file' for this source; "
                           "pass --spreadsheet-id or set config[\"spreadsheet_id\"]")
    return (fetch_tab_csv(spreadsheet_id, source.get("gid")),
            f"tab {source.get('tab') or source.get('gid') or '(first)'}")


def header_to_field(columns):
    mapping = {}
    for header, field in (columns or {}).items():
        mapping[str(header).strip()] = str(field).strip()
    return mapping


def row_fields(row, mapping):
    """Map a parsed row to canonical-field values."""
    fields = {}
    for header, value in row.items():
        field = mapping.get(header, header)
        if field and value != "":
            fields[field] = value
    return fields


def name_to_id_map(records):
    by_name = {}
    for rec in records:
        if rec.get("name"):
            by_name[str(rec["name"]).strip().lower()] = rec.get("id")
    by_id = {rec.get("id"): rec.get("name") for rec in records}
    return by_name, by_id


def resolve_ref(value, records):
    """Cell may be an id or a display name; return the canonical id."""
    v = str(value).strip()
    if not v:
        return None
    by_name, _by_id = name_to_id_map(records)
    if value in {r.get("id") for r in records}:
        return v
    if v.lower() in by_name:
        return by_name[v.lower()]
    raise _RowError(f"unknown reference {v!r}")


class _RowError(Exception):
    pass


class Importer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.loaded = {}
        self.report = []  # human-readable skipped/report lines

    # -- loading ----------------------------------------------------------

    def load_all(self):
        for kind in ORDER_OF_KINDS:
            source = self.cfg.source(kind)
            if source is None:
                self.loaded[kind] = None
                self.report.append(f"{kind}: no source — kept unchanged")
                continue
            rows, label = load_rows(source, self.cfg.spreadsheet_id,
                                    file_path=self.cfg.source_file(kind))
            self.loaded[kind] = rows
            self.report.append(f"{kind}: {len(rows)} row(s) read from {label}")
        return self

    # -- normalization ----------------------------------------------------

    def normalize(self, existing):
        """Build new canonical records per kind. Returns (records, skipped).

        'existing' is the current data read from disk (record lists keyed by
        files). Newly generated ids never collide with existing ids and ids
        created earlier in the same import.
        """
        merged = {k: list(existing[f"{k}.json"]) for k in KINDS}
        skipped = {k: [] for k in KINDS}

        # Kinds without a configured source pass through unchanged (partial
        # imports: a daily driver may only maintain events, for example).
        for kind in ORDER_OF_KINDS:
            if self.loaded[kind] is None:
                continue
            if kind == "events":
                merged["events"] = self._normalize_events(existing, merged, skipped)
            else:
                merged[kind] = self._normalize_kind(kind, existing, skipped)

        return {f"{k}.json": merged[k] for k in KINDS}, skipped

    def _normalize_kind(self, kind, existing, skipped):
        rows = self.loaded[kind]
        block = existing[f"{kind}.json"]
        mapping = header_to_field(self.cfg.source(kind).get("columns"))
        id_column = self.cfg.source(kind).get("id_column")
        used = [dict(r) for r in block]  # records, for id generation helpers
        in_payload = set()  # explicit ids seen in this sheet, for dup detection
        new_records = [dict(r) for r in block]  # start from existing (no prune)
        for row_no, row in enumerate(rows, start=2):  # row 1 is the header
            if not row or all(not v for v in row.values()):
                continue
            try:
                fields = row_fields(row, mapping)
                rec = self._build_id_record(kind, row, fields, id_column,
                                            used, in_payload)
            except _RowError as exc:
                skipped[kind].append((row_no, str(exc)))
                continue
            existing_idx = next((i for i, r in enumerate(new_records) if r.get("id") == rec["id"]), None)
            if existing_idx is not None:
                new_records[existing_idx] = rec  # update in place
            else:
                new_records.append(rec)
                used.append(rec)
        return new_records

    def _build_id_record(self, kind, row, fields, id_column, used_ids, in_payload):
        explicit = row.get(id_column) if id_column else None
        if explicit and str(explicit).strip():
            _id = str(explicit).strip()
            if _id in in_payload:
                raise _RowError(f"duplicate id {_id!r} in this import")
            in_payload.add(_id)
        else:
            if kind == "categories":
                _id = next_category_id(fields.get("name", ""), used_ids)
            elif kind == "speakers":
                _id = next_speaker_id(fields.get("name", ""), used_ids)
            else:
                _id = next_masjid_id(fields.get("name", ""), used_ids)
            in_payload.add(_id)

        rec, errors = {
            "categories": validate_category,
            "speakers": validate_speaker,
            "masjids": validate_masjid,
        }[kind](fields)
        if errors:
            raise _RowError("; ".join(errors))
        if kind == "masjids":
            # derive mukim_id from the free-text mukim so imported
            # masjids link to data/mukims.json automatically.
            rec["mukim_id"] = mukim_id_for(rec.get("mukim"))
        return {"id": _id, **rec}

    def _normalize_events(self, existing, merged, skipped):
        rows = self.loaded["events"]
        block = existing["events.json"]
        mapping = header_to_field(self.cfg.source("events").get("columns"))
        id_column = self.cfg.source("events").get("id_column")
        used = [dict(r) for r in block]
        in_payload = set()
        new_records = [dict(r) for r in block]
        for row_no, row in enumerate(rows, start=2):
            if not row or all(not v for v in row.values()):
                continue
            try:
                fields = row_fields(row, mapping)
                rec = self._build_event_record(row, fields, id_column,
                                               merged, used, in_payload)
            except _RowError as exc:
                skipped["events"].append((row_no, str(exc)))
                continue
            existing_idx = next((i for i, r in enumerate(new_records) if r.get("id") == rec["id"]), None)
            if existing_idx is not None:
                new_records[existing_idx] = rec
            else:
                new_records.append(rec)
                used.append(rec)
        new_records.sort(key=lambda e: (e.get("date", ""), e.get("start_time", ""), e.get("id", "")))
        return new_records

    def _collect_recurrence(self, fields):
        rtype = (fields.get("recurrence_type") or "").strip()
        if not rtype:
            return None
        days_raw = (fields.get("recurrence_days") or "").split(",")
        days = [d.strip().lower() for d in days_raw if d.strip()]
        exceptions_raw = (fields.get("recurrence_exceptions") or "").split(",")
        exceptions = [d.strip() for d in exceptions_raw if d.strip()]
        return {
            "type": rtype,
            "days": days,
            "start_date": (fields.get("recurrence_start_date") or "").strip() or None,
            "end_date": (fields.get("recurrence_end_date") or "").strip() or None,
            "exceptions": exceptions,
        }

    def _build_event_record(self, row, fields, id_column, merged, used_ids, in_payload):
        # resolve references (id or name)
        for ref_kind, field in (("masjids", "masjid_id"),
                                ("speakers", "speaker_id"),
                                ("categories", "category_id")):
            value = fields.get(field)
            if value:
                try:
                    fields[field] = resolve_ref(value, merged[ref_kind])
                except _RowError as exc:
                    raise _RowError(f"{field}: {exc}") from exc

        field_errors = []
        if not fields.get("date"):
            field_errors.append("missing date")
        if not fields.get("start_time"):
            field_errors.append("missing start_time")
        if field_errors:
            raise _RowError("; ".join(field_errors))

        explicit = row.get(id_column) if id_column else None
        if explicit and str(explicit).strip():
            _id = str(explicit).strip()
            if _id in in_payload:
                raise _RowError(f"duplicate id {_id!r} in this import")
            in_payload.add(_id)
        else:
            _id = next_event_id(fields["date"], used_ids)
            in_payload.add(_id)

        fields.setdefault("status", "published")
        rec, errors = validate_event(fields)
        if errors:
            raise _RowError("; ".join(errors))
        if not rec.get("recurrence"):
            rec["recurrence"] = self._collect_recurrence(fields)
        return {"id": _id, **rec}

    # -- merge + validate + write ----------------------------------------

    def run(self):
        self.load_all()
        existing = {}
        for f in DATA_FILES:
            existing[f] = read_json(self.cfg.paths[f], [] if f != "settings.json" else {})
        if not self.cfg.data_dir.is_dir():
            raise RuntimeError(f"data dir not found: {self.cfg.data_dir}")

        merged, skipped = self.normalize(existing)
        # settings and reference collections pass through untouched
        for fname in ("settings.json", "mukims.json", "editors.json"):
            merged[fname] = existing[fname]

        # validate the merged set against a throwaway copy (never touch data/)
        with tempfile.TemporaryDirectory(prefix="mvp-import-") as tmp:
            tmpdir = Path(tmp)
            for f, data in merged.items():
                with open(tmpdir / f, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                    fh.write("\n")
            problems = validate_directory(tmpdir)

        self._print_summary(skipped, problems)

        if problems:
            print("\nABORTED — merged data is invalid. Your local data was NOT changed.",
                  file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 2

        if self.cfg.strict and any(skipped[k] for k in skipped):
            print("\nABORTED (--strict) — rows were skipped; nothing written.",
                  file=sys.stderr)
            self._print_skipped(skipped)
            return 2

        if self.cfg.dry_run:
            print("\nDry run — data validated; not writing (no change to data/).")
            return 0

        for f, data in merged.items():
            with open(self.cfg.paths[f], "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        print("\nImported and validated. Wrote canonical JSON to "
              f"{self.cfg.data_dir}.")
        return 0

    def _print_summary(self, skipped, problems):
        print("Import report")
        print("-------------")
        for line in self.report:
            print("  " + line)
        if any(skipped[k] for k in skipped):
            print("\nSkipped rows (invalid / duplicate):")
            self._print_skipped(skipped)
        print(f"\nValidation problems: {len(problems)}")

    def _print_skipped(self, skipped):
        for kind in KINDS:
            for row_no, msg in sorted(skipped[kind], key=lambda t: t[0]):
                print(f"  - {kind} row {row_no}: {msg}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import Google Sheets (or CSV) into canonical JSON.")
    parser.add_argument("--config", default=None,
                        help="JSON config with sheet sources "
                             "(default: tools/sheets_import.json, else the .example.json)")
    parser.add_argument("--spreadsheet-id", default=None,
                        help="Google Sheets id override (applies to all remote sources)")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--strict", action="store_true",
                        help="abort (write nothing) if any row was skipped")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate only; do not write data/")
    args = parser.parse_args(argv)

    if args.config:
        config_path = Path(args.config)
    else:
        # Default chain: Google-sheet config -> daily-driver local CSV config.
        candidates = [ROOT / "tools" / "sheets_import.json",
                      ROOT / "data-entry" / "config.json",
                      ROOT / "tools" / "sheets_import.example.json"]
        config_path = next((c for c in candidates if c.exists()), candidates[-1])
    if not config_path.is_file():
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 2

    with open(config_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)

    cfg = ImportConfig(config, spreadsheet_id_override=args.spreadsheet_id,
                       strict=args.strict, dry_run=args.dry_run,
                       data_dir=args.data_dir, config_path=config_path)
    try:
        return Importer(cfg).run()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())