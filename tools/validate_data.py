#!/usr/bin/env python3
"""Masjid Events Perlis — canonical data validator.

Validates all data files in the canonical data set:

    data/masjids.json     data/events.json
    data/speakers.json    data/categories.json    data/settings.json
    data/mukims.json   data/editors.json

Checks performed (see DATA_SCHEMA.md):
    - malformed JSON
    - missing required fields
    - invalid / duplicate IDs
    - invalid dates and times
    - invalid event status
    - unknown masjid / speaker / category references
    - unknown mukim / editor references (masjids)
    - invalid recurring-event configuration
    - obviously invalid event ranges (end_time not later than start_time)

Exit codes:
    0   data is valid
    1   data failed validation (errors printed)
    2   usage / setup errors

Usage:
    python3 tools/validate_data.py                 # validate ./data
    python3 tools/validate_data.py --data-dir X    # validate ./X
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FIXED_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json",
               "settings.json", "mukims.json", "editors.json")

REQUIRED_EVENT = ("id", "title", "masjid_id", "date", "start_time", "status")
REQUIRED_ID_NAME = ("id", "name")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Validate Masjid Events Perlis data.")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help=f"path to the data directory (default: {DEFAULT_DATA_DIR})",
    )
    return parser.parse_args(argv)


def _read_file(path):
    """Return (parsed_data, error)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, "file not found"
    except OSError as exc:
        return None, f"cannot read file ({exc.strerror or exc})"
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"


def _valid_date(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _valid_time(value):
    if not isinstance(value, str) or not TIME_RE.match(value):
        return False
    hh, mm = int(value[:2]), int(value[3:])
    return hh <= 23 and mm <= 59


def _check_time(value, label, errors):
    t = str(value or "")
    if not t:
        return
    if not _valid_time(t):
        errors.append(f"{label}: invalid time {t!r} (use HH:MM).")


def _validate_id_list(filename, items, errors, require_name=True):
    """Validate an array of {id, ...} records; returns the list of records (in
    order). Duplicate-id / missing-name problems are reported as errors."""
    records = []
    if items is None:
        return records
    ids = set()
    for index, item in enumerate(items):
        where = f"{filename}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: expected an object, got {type(item).__name__}.")
            continue
        eid = item.get("id")
        if not isinstance(eid, str) or not eid.strip():
            errors.append(f"{where}: missing or non-string 'id'.")
            continue
        if not ID_RE.match(eid):
            errors.append(
                f"{where}: invalid id {eid!r} "
                "(use lowercase letters, digits, and hyphens only)."
            )
        if eid in ids:
            errors.append(f"{where}: duplicate id {eid!r}.")
        ids.add(eid)
        if require_name:
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{where} ({eid!r}): missing required field 'name'.")
        records.append(item)
    return records


def _validate_masjids(masjids, mukims, editors, errors):
    """Check masjid -> mukim / editor references and mukim consistency."""
    mukim_ids = {d.get("id") for d in mukims}
    mukim_names = {str(d.get("name") or "").strip().lower() for d in mukims}
    editor_ids = {e.get("id") for e in editors}

    for index, masjid in enumerate(masjids):
        if not isinstance(masjid, dict):
            continue
        label = "masjids.json[%d]" % index
        eid = masjid.get("id")
        if isinstance(eid, str) and eid:
            label = f"masjid {eid!r}"

        did = str(masjid.get("mukim_id") or "").strip()
        if not did:
            errors.append(f"{label}: missing required field 'mukim_id'.")
        elif did not in mukim_ids:
            errors.append(f"{label}: unknown mukim_id {did!r}.")

        # Free-text 'mukim' should match the selected mukim's name so the
        # public filter list and the linked mukim stay consistent.
        mukim_name = str(masjid.get("mukim") or "").strip()
        if did in mukim_ids and mukim_name:
            matching = str(
                next((d.get("name") for d in mukims if d.get("id") == did), "")
            ).strip()
            if mukim_name.strip().lower() != matching.lower():
                errors.append(
                    f"{label}: mukim {mukim_name!r} does not match the "
                    f"name of mukim_id {did!r} ({matching!r})."
                )

        editor_id = str(masjid.get("editor_id") or "").strip()
        if editor_id and editor_id not in editor_ids:
            errors.append(f"{label}: unknown editor_id {editor_id!r}.")


def _check_recurrence(recurrence, settings, label, errors):
    if not isinstance(recurrence, dict):
        errors.append(f"{label}: recurrence must be an object.")
        return

    allowed_types = set(settings.get("recurrence_types") or ["weekly"])
    rtype = str(recurrence.get("type", ""))
    if rtype not in allowed_types:
        errors.append(f"{label}: invalid recurrence type {rtype!r} (allowed: {sorted(allowed_types)}).")

    days = recurrence.get("days")
    if not isinstance(days, list) or not days:
        errors.append(f"{label}: recurrence.days must be a non-empty list.")
    else:
        weekdays = set(settings.get("weekdays") or [])
        for day in days:
            if day not in weekdays:
                errors.append(f"{label}: invalid weekday {day!r} in recurrence.days.")

    for field in ("start_date", "end_date"):
        value = recurrence.get(field)
        if value in (None, ""):
            continue
        if not _valid_date(value):
            errors.append(f"{label}: invalid recurrence.{field} {value!r} (use YYYY-MM-DD).")

    sd = recurrence.get("start_date") or ""
    ed = recurrence.get("end_date") or ""
    if sd and ed and _valid_date(sd) and _valid_date(ed) and ed < sd:
        errors.append(f"{label}: recurrence.end_date {ed!r} is before start_date {sd!r}.")

    exceptions = recurrence.get("exceptions")
    if exceptions is not None:
        if not isinstance(exceptions, list):
            errors.append(f"{label}: recurrence.exceptions must be a list of dates.")
        else:
            seen = set()
            for ex_date in exceptions:
                if not isinstance(ex_date, str) or not _valid_date(ex_date):
                    errors.append(f"{label}: invalid recurrence.exceptions entry {ex_date!r} (use YYYY-MM-DD).")
                    continue
                if ex_date in seen:
                    errors.append(f"{label}: duplicate recurrence.exceptions date {ex_date!r}.")
                seen.add(ex_date)


def validate_directory(data_dir):
    errors = []

    parsed = {}
    for fname in FIXED_FILES:
        data, err = _read_file(data_dir / fname)
        if err:
            errors.append(f"{fname}: {err}")
            parsed[fname] = [] if fname != "settings.json" else {}
        else:
            parsed[fname] = data

    if errors:
        return errors

    masjids = parsed["masjids.json"]
    events = parsed["events.json"]
    speakers = parsed["speakers.json"]
    categories = parsed["categories.json"]
    settings = parsed["settings.json"]
    mukims = parsed["mukims.json"]
    editors = parsed["editors.json"]

    if not isinstance(masjids, list):
        errors.append("masjids.json: must be an array.")
    if not isinstance(events, list):
        errors.append("events.json: must be an array.")
    if not isinstance(speakers, list):
        errors.append("speakers.json: must be an array.")
    if not isinstance(categories, list):
        errors.append("categories.json: must be an array.")
    if not isinstance(settings, dict):
        errors.append("settings.json: must be an object.")
    if not isinstance(mukims, list):
        errors.append("mukims.json: must be an array.")
    if not isinstance(editors, list):
        errors.append("editors.json: must be an array.")

    if errors:
        return errors

    masjid_records = _validate_id_list("masjids.json", masjids, errors)
    speaker_ids = set(r.get("id") for r in _validate_id_list("speakers.json", speakers, errors))
    category_ids = set(r.get("id") for r in _validate_id_list("categories.json", categories, errors))
    mukim_records = _validate_id_list("mukims.json", mukims, errors)
    editor_records = _validate_id_list("editors.json", editors, errors)

    _validate_masjids(masjid_records, mukim_records, editor_records, errors)

    masjid_ids = {m.get("id") for m in masjid_records}

    event_ids = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"events.json[{index}]: expected an object, got {type(event).__name__}.")
            continue

        label = f"events.json[{index}]"
        eid = event.get("id", "<missing id>")
        if isinstance(eid, str) and eid:
            label = f"event {eid!r}"
            if eid in event_ids:
                errors.append(f"{label}: duplicate id {eid!r}.")
            event_ids.add(eid)
        else:
            errors.append(f"events.json[{index}]: missing or non-string 'id'.")

        # required fields
        for field in REQUIRED_EVENT:
            value = event.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"{label}: missing required field {field!r}.")

        # date
        raw_date = event.get("date", "")
        if not _valid_date(raw_date):
            errors.append(f"{label}: invalid date {raw_date!r} (use YYYY-MM-DD).")

        # times + range
        _check_time(event.get("start_time"), f"{label} start_time", errors)
        _check_time(event.get("end_time"), f"{label} end_time", errors)
        st = str(event.get("start_time", "")).strip()
        et = str(event.get("end_time", "")).strip()
        if st and et and _valid_time(st) and _valid_time(et) and et <= st:
            errors.append(f"{label}: end_time {et!r} is not later than start_time {st!r}.")

        # status
        status = str(event.get("status", ""))
        allowed = set(settings.get("event_statuses") or [])
        if status not in allowed:
            errors.append(f"{label}: invalid status {status!r} (allowed: {sorted(allowed)}).")

        # references
        mid = str(event.get("masjid_id", ""))
        if mid and mid not in masjid_ids:
            errors.append(f"{label}: unknown masjid_id {mid!r}.")

        sid = event.get("speaker_id")
        sid = str(sid) if sid else ""
        if sid and sid not in speaker_ids:
            errors.append(f"{label}: unknown speaker_id {sid!r}.")

        cid = event.get("category_id")
        cid = str(cid) if cid else ""
        if cid and cid not in category_ids:
            errors.append(f"{label}: unknown category_id {cid!r}.")

        # recurrence
        if event.get("recurrence") is not None:
            _check_recurrence(event["recurrence"], settings, label, errors)

    return errors


def main(argv=None):
    parsed_args = parse_args(argv) if argv is not None else parse_args()
    data_dir = Path(parsed_args.data_dir)
    if not data_dir.is_dir():
        print(f"error: {data_dir} is not a directory.", file=sys.stderr)
        return 2

    errors = validate_directory(data_dir)
    if errors:
        print(f"Validation FAILED ({len(errors)} problem(s)) in {data_dir}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"OK — {data_dir} is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())