#!/usr/bin/env python3
"""Masjid Events Perlis — Google Sheets importer (adapter).

Optional data source. Reads published Google Sheets tabs (or local CSV files)
and merges their rows into the canonical JSON data set, then validates.

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
                        "columns": {"Nama": "name", "Daerah": "district"} },
        "speakers":   { "tab": "Penceramah" },
        "categories": { "tab": "Kategori" },
        "events":     { "tab": "Acara" }
      }
    }

Each source:
  - "tab"      descriptive name (used in reports).
  - "gid"      Google tab id for remote export. Omit to use the first tab.
  - "file"     local CSV path (testing / offline). If set, "gid" is ignored
               and spreadsheet_id is not required.
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
import io
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "tools"))

from serve import (  # noqa: E402  (reuse the admin editor's normalization)
    VALID_RECURRENCE_TYPES,
    VALID_STATUSES,
    VALID_WEEKDAYS,
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

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json", "settings.json")
KINDS = ("categories", "speakers", "masjids", "events")
ORDER_OF_KINDS = ("categories", "speakers", "masjids", "events")


class ImportConfig:
    def __init__(self, config, spreadsheet_id_override=None, strict=False, dry_run=False, data_dir=None):
        self.config = config
        self.spreadsheet_id = spreadsheet_id_override or config.get("spreadsheet_id") or ""
        self.strict = strict
        self.dry_run = dry_run
        self.data_dir = Path(data_dir) if data_dir else ROOT / "data"
        self.paths = {f: self.data_dir / f for f in DATA_FILES}

    def source(self, kind):
        return self.config.get("sources", {}).get(kind)


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
    for row in reader:
        if row is None:
            continue
        rows.append({str(k).strip(): (v or "").strip() for k, v in row.items()})
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


def load_rows(source, spreadsheet_id):
    """Return (rows, source_label) for one sheet source."""
    if source is None:
        return None, None
    if source.get("file"):
        path = Path(source["file"]).resolve()
        if not path.is_file():
            raise RuntimeError(f"local file not found: {path}")
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
        missing = [k for k in KINDS if self.cfg.source(k) is None]
        if missing:
            raise RuntimeError("config has no source for: " + ", ".join(missing))
        for kind in ORDER_OF_KINDS:
            source = self.cfg.source(kind)
            rows, label = load_rows(source, self.cfg.spreadsheet_id)
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

        # 1) categories  (resolved first for event.category refs)
        merged["categories"] = self._normalize_kind("categories", existing, skipped)
        # 2) speakers
        merged["speakers"] = self._normalize_kind("speakers", existing, skipped)
        # 3) masjids
        merged["masjids"] = self._normalize_kind("masjids", existing, skipped)
        # 4) events   (may reference the above via id or name)
        merged["events"] = self._normalize_events(existing, merged, skipped)

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
        # settings pass through untouched
        merged["settings.json"] = existing["settings.json"]

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
        default = ROOT / "tools" / "sheets_import.json"
        config_path = default if default.exists() else ROOT / "tools" / "sheets_import.example.json"
    if not config_path.is_file():
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 2

    with open(config_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)

    cfg = ImportConfig(config, spreadsheet_id_override=args.spreadsheet_id,
                       strict=args.strict, dry_run=args.dry_run,
                       data_dir=args.data_dir)
    try:
        return Importer(cfg).run()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())