#!/usr/bin/env python3
"""Masjid Events Perlis — local admin/data-management server (dev/admin only).

Serves the admin control panel (admin/*.html) and a local HTTP API that
creates/updates/archives masjids, events, speakers and categories, writes
canonical JSON into data/, validates after every mutation (rolling back on
failure), previews public pages, and publishes the data mirror into
public/data/ for the static site build.

It is NOT part of the public site and must NOT be deployed to GitHub Pages.

Usage:
    python3 tools/serve.py                              # http://localhost:8000/admin/
    python3 tools/serve.py --data-dir data --public-data public/data
    python3 tools/serve.py --port 8080

Endpoints (all JSON):
    GET    /api/data
    POST   /api/validate                -> validation report (no mutation)
    POST   /api/publish                 -> validate + sync public/data mirror
    POST   /api/preview                 -> {type, id} -> rendered page HTML
    POST   /api/masjids                 create masjid
    PUT    /api/masjids/{id}            update masjid
    DELETE /api/masjids/{id}            delete masjid (blocked if referenced)
    POST   /api/events                  create event
    PUT    /api/events/{id}             update event
    POST   /api/events/{id}/status      {status} -> draft/published/cancelled/
                                       postponed/completed (archive)
    DELETE /api/events/{id}             delete event
    POST   /api/speakers                create speaker
    PUT    /api/speakers/{id}           update speaker
    DELETE /api/speakers/{id}           delete speaker (blocked if referenced)
    POST   /api/categories              create category
    PUT    /api/categories/{id}         update category
    DELETE /api/categories/{id}         delete category (blocked if referenced)
    POST   /api/mukims               create mukim
    PUT    /api/mukims/{id}          update mukim
    DELETE /api/mukims/{id}          delete mukim (blocked if referenced)
    POST   /api/editors                 create editor
    PUT    /api/editors/{id}            update editor
    DELETE /api/editors/{id}            delete editor (blocked if referenced)
"""

import argparse
import json
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from validate_data import validate_directory
import build_site

ROOT = Path(__file__).resolve().parent.parent

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json",
              "settings.json", "mukims.json", "editors.json")

VALID_STATUSES = {"draft", "published", "cancelled", "postponed", "completed"}
VALID_RECURRENCE_TYPES = {"weekly"}
VALID_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EVENT_ID_RE = re.compile(r"^evt-\d{8}-\d{3}$")


def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        raise SystemExit(f"Error: {path} contains invalid JSON.")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def slugify(text, fallback=""):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or fallback


def valid_date(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def valid_time(value):
    if not isinstance(value, str) or not TIME_RE.match(value):
        return False
    hh, mm = int(value[:2]), int(value[3:])
    return 0 <= hh <= 23 and 0 <= mm <= 59


def next_id(base, existing):
    existing = set(existing)
    candidate = base
    n = 2
    while candidate in existing:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def next_masjid_id(name, masjids):
    base = slugify(name, "masjid")
    base = base if base.startswith("masjid-") else f"masjid-{base}"
    return next_id(base, [m.get("id") for m in masjids])


def next_event_id(raw_date, existing_events):
    day = raw_date.replace("-", "")
    base = f"evt-{day}"
    used = {
        e.get("id")
        for e in existing_events
        if isinstance(e.get("id"), str) and e["id"].startswith(base)
    }
    n = 1
    while f"{base}-{n:03d}" in used:
        n += 1
    return f"{base}-{n:03d}"


def next_speaker_id(name, speakers):
    base = slugify(name, "speaker")
    base = base if base.startswith("speaker-") else f"speaker-{base}"
    return next_id(base, [s.get("id") for s in speakers])


def next_category_id(name, categories):
    return next_id(slugify(name, "lain"), [c.get("id") for c in categories])


# Official Perlis mukims. The name list mirrors data/mukims.json (used to
# derive a mukim_id from a free-text mukim without string-splitting).
KNOWN_MUKIMS = (
    "Kangar", "Arau", "Padang Besar", "Pauh", "Beseri", "Chuping", "Bintong",
    "Kurong Anai", "Kayang", "Mata Ayer", "Oran", "Sanglang", "Simpang Empat",
    "Tambun Tulang", "Wang Bintong",
)

MUKIM_ID_BY_NAME = {
    str(d).strip().lower(): slugify(d) for d in KNOWN_MUKIMS
}


def mukim_id_for(name):
    """Best-effort mukim_id for a free-text mukim name (or None)."""
    return MUKIM_ID_BY_NAME.get(str(name or "").strip().lower())


def mukim_display_name(mukim_id):
    """Display name for a mukim_id (or None when unknown)."""
    for name in KNOWN_MUKIMS:
        if slugify(name) == mukim_id:
            return name
    return None


def validate_mukim(form):
    errors = []
    name = str(form.get("name", "")).strip()
    if not name:
        errors.append("Mukim name is required.")
    return {
        "name": name,
        "description": str(form.get("description", "")).strip(),
    }, errors


def validate_editor(form):
    errors = []
    name = str(form.get("name", "")).strip()
    if not name:
        errors.append("Editor name is required.")
    email = str(form.get("email", "")).strip()
    if email and "@" not in email:
        errors.append("email must look like an email address.")
    return {
        "name": name,
        "email": email,
        "role": str(form.get("role", "")).strip() or "editor",
        "description": str(form.get("description", "")).strip(),
    }, errors


def next_mukim_id(name, mukims):
    return next_id(slugify(name, "mukim"), [d.get("id") for d in mukims])


def next_editor_id(name, editors):
    base = slugify(name, "editor")
    base = base if base.startswith("editor-") else f"editor-{base}"
    return next_id(base, [e.get("id") for e in editors])


# ---------------------------------------------------------------------------
# Record validation (field-level; referential integrity is re-checked by
# validate_directory after every mutation, with rollback on failure).
# ---------------------------------------------------------------------------

def mukim_lookup_name(mukim_id, mukims):
    """Display name for a mukim_id, resolved against live mukims.json."""
    for d in mukims or []:
        if d.get("id") == mukim_id:
            return str(d.get("name") or "").strip()
    return None


def validate_masjid(form, mukims=None):
    errors = []
    name = str(form.get("name", "")).strip()
    if not name:
        errors.append("Masjid name is required.")
    if len(name) > 200:
        errors.append("Masjid name is too long (max 200 characters).")

    latitude = form.get("latitude")
    longitude = form.get("longitude")
    try:
        latitude = float(latitude) if latitude not in (None, "") else None
    except (TypeError, ValueError):
        errors.append("latitude must be a number.")
        latitude = None
    try:
        longitude = float(longitude) if longitude not in (None, "") else None
    except (TypeError, ValueError):
        errors.append("longitude must be a number.")
        longitude = None
    if latitude is not None and not -90 <= latitude <= 90:
        errors.append("latitude must be between -90 and 90.")
    if longitude is not None and not -180 <= longitude <= 180:
        errors.append("longitude must be between -180 and 180.")

    website = str(form.get("website", "")).strip()
    if website and not re.match(r"^https?://", website):
        errors.append("website must start with http:// or https://.")

    mukim_id = str(form.get("mukim_id", "")).strip() or None
    editor_id = str(form.get("editor_id", "")).strip() or None
    mukim = str(form.get("mukim", "")).strip()
    if mukim_id:
        # keep the free-text display name consistent with the linked mukim
        resolved = mukim_lookup_name(mukim_id, mukims)
        if resolved:
            mukim = resolved
        elif not mukim:
            mukim = mukim_display_name(mukim_id) or ""
    elif mukim:
        # derive the mukim link from the free-text mukim when possible
        mukim_id = mukim_id_for(mukim)

    return {
        "name": name,
        "mukim": mukim,
        "mukim_id": mukim_id,
        "state": str(form.get("state", "")).strip() or "Perlis",
        "address": str(form.get("address", "")).strip(),
        "latitude": latitude,
        "longitude": longitude,
        "contact": str(form.get("contact", "")).strip(),
        "website": website,
        "editor_id": editor_id,
    }, errors


def validate_event(form):
    errors = []
    title = str(form.get("title", "")).strip()
    if not title:
        errors.append("event title is required.")
    if len(title) > 300:
        errors.append("event title is too long (max 300 characters).")

    raw_date = str(form.get("date", "")).strip()
    if not valid_date(raw_date):
        errors.append(f"invalid date: {raw_date!r} (use YYYY-MM-DD).")

    start_time = str(form.get("start_time", "")).strip()
    if not valid_time(start_time):
        errors.append(f"invalid start_time: {start_time!r} (use HH:MM).")
    end_time = str(form.get("end_time", "")).strip() or None
    if end_time and not valid_time(end_time):
        errors.append(f"invalid end_time: {end_time!r} (use HH:MM).")
    if valid_time(start_time) and end_time and valid_time(end_time) and end_time <= start_time:
        errors.append(f"end_time must be later than start_time (got {end_time} <= {start_time}).")

    status = str(form.get("status", "")).strip() or "published"
    if status not in VALID_STATUSES:
        errors.append(f"invalid status: {status!r} (allowed: {sorted(VALID_STATUSES)}).")

    masjid_id = str(form.get("masjid_id", "")).strip()
    if not masjid_id:
        errors.append("masjid_id is required.")
    speaker_id = str(form.get("speaker_id", "")).strip() or None
    category_id = str(form.get("category_id", "")).strip() or None
    description = str(form.get("description", "")).strip()
    location = str(form.get("location", "")).strip() or None

    recurrence = form.get("recurrence")
    if recurrence:
        if not isinstance(recurrence, dict):
            errors.append("recurrence must be an object.")
            recurrence = None
        else:
            rtype = str(recurrence.get("type", "")).strip()
            if rtype not in VALID_RECURRENCE_TYPES:
                errors.append(f"invalid recurrence type: {rtype!r}.")
            days = recurrence.get("days") or []
            if not isinstance(days, list) or not days:
                errors.append("recurrence.days must be a non-empty list.")
            else:
                if not all(str(d) in VALID_WEEKDAYS for d in days):
                    errors.append(f"invalid weekday in recurrence.days: {days!r}.")
            end_date = recurrence.get("end_date")
            if end_date not in (None, "") and not valid_date(str(end_date)):
                errors.append(f"invalid recurrence.end_date: {end_date!r}.")
            start_date = recurrence.get("start_date")
            if start_date not in (None, "") and not valid_date(str(start_date)):
                errors.append(f"invalid recurrence.start_date: {start_date!r}.")
            if start_date not in (None, "") and end_date not in (None, "") \
                    and valid_date(str(start_date)) and valid_date(str(end_date)) \
                    and str(end_date) < str(start_date):
                errors.append("recurrence.end_date is before recurrence.start_date.")
            exceptions = recurrence.get("exceptions") or []
            if not isinstance(exceptions, list):
                errors.append("recurrence.exceptions must be a list of dates.")
            else:
                seen = set()
                for ex in exceptions:
                    if not valid_date(str(ex)):
                        errors.append(f"invalid recurrence.exceptions entry: {ex!r}.")
                    elif ex in seen:
                        errors.append(f"duplicate recurrence.exceptions date: {ex!r}.")
                    seen.add(ex)

    return {
        "title": title,
        "masjid_id": masjid_id,
        "date": raw_date,
        "start_time": start_time,
        "end_time": end_time,
        "speaker_id": speaker_id,
        "category_id": category_id,
        "description": description,
        "location": location,
        "status": status,
        "recurrence": recurrence if recurrence and isinstance(recurrence, dict) else None,
    }, errors


def validate_speaker(form):
    errors = []
    name = str(form.get("name", "")).strip()
    if not name:
        errors.append("speaker name is required.")
    return {
        "name": name,
        "description": str(form.get("description", "")).strip(),
    }, errors


def validate_category(form):
    errors = []
    name = str(form.get("name", "")).strip()
    if not name:
        errors.append("category name is required.")
    return {"name": name}, errors


# ---------------------------------------------------------------------------
# Persistence helpers with validate + rollback
# ---------------------------------------------------------------------------

class DataStore:
    def __init__(self, data_dir, public_data_dir):
        self.data_dir = Path(data_dir)
        self.public_data_dir = Path(public_data_dir)
        self.paths = {f: self.data_dir / f for f in DATA_FILES}

    def _ensure_files(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for f in DATA_FILES:
            if not self.paths[f].exists():
                initial = {} if f == "settings.json" else []
                if f == "settings.json":
                    initial = {
                        "site_name": "Masjid Events Perlis",
                        "site_url": "",
                        "language": "ms",
                        "timezone": "Asia/Kuala_Lumpur",
                        "date_format": "YYYY-MM-DD",
                        "time_format": "HH:MM",
                        "event_statuses": sorted(VALID_STATUSES),
                        "recurrence_types": sorted(VALID_RECURRENCE_TYPES),
                        "weekdays": sorted(VALID_WEEKDAYS),
                    }
                elif f == "mukims.json":
                    # fresh data dirs start with the official Perlis mukims
                    # so masjid mukim_id references resolve immediately.
                    initial = [
                        {"id": slugify(d), "name": d, "description": ""}
                        for d in KNOWN_MUKIMS
                    ]
                write_json(self.paths[f], initial)

    def read_all(self):
        return {f: read_json(self.paths[f], {} if f == "settings.json" else []) for f in DATA_FILES}

    def _snapshot(self):
        return {
            f: (self.paths[f].read_text(encoding="utf-8")
                if self.paths[f].exists() else None)
            for f in DATA_FILES
        }

    def _restore(self, snapshot):
        for f, text in snapshot.items():
            if text is None:
                self.paths[f].unlink(missing_ok=True)
            else:
                with open(self.paths[f], "w", encoding="utf-8") as fh:
                    fh.write(text)

    def validate(self):
        self._ensure_files()
        errors = validate_directory(self.data_dir)
        return [str(e) for e in errors]

    def mutate(self, apply_fn):
        """Run apply_fn mutating the parsed data, persist, validate, rollback.

        Returns (ok, payload). apply_fn receives the parsed data dict and
        returns a payload on success, or raises _ValidationError / _NotFound.
        On validation failure the data dir is rolled back to its prior state.
        """
        self._ensure_files()
        snapshot = self._snapshot()
        data = self.read_all()
        try:
            payload = apply_fn(data)
        except (_ValidationError, _NotFound):
            self._restore(snapshot)
            raise
        except KeyError as exc:
            self._restore(snapshot)
            return False, [f"missing key: {exc}"]
        for f in DATA_FILES:
            write_json(self.paths[f], data[f])
        errors = self.validate()
        if errors:
            self._restore(snapshot)
            return False, errors
        return True, payload

    def publish(self):
        errors = self.validate()
        if errors:
            return False, errors
        self.public_data_dir.mkdir(parents=True, exist_ok=True)
        for f in DATA_FILES:
            src = self.paths[f]
            if src.exists():
                write_json(self.public_data_dir / f, read_json(src, [] if f != "settings.json" else {}))
        return True, {}


def store():
    return DataStore(DATA_DIR, PUBLIC_DATA_DIR)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _body(self):
        length = self.headers.get("Content-Length")
        try:
            length = int(length or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, body):
        body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, rel_path):
        target = (ROOT / rel_path).resolve()
        if not str(target).startswith(str(ROOT)):
            self._send_json(403, {"error": "forbidden"})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send_json(404, {"error": "not found"})
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".webmanifest": "application/manifest+json",
            ".png": "image/png",
        }.get(target.suffix.lower(), "application/octet-stream")
        with open(target, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- routing ------------------------------------------------------------

    def _split(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        return parts, parse_qs(parsed.query)

    def do_GET(self):
        parts, _query = self._split()
        if not parts:
            return self._send_file("public/index.html")
        if parts == ["admin"] or parts == ["admin", "index.html"]:
            return self._send_file("admin/index.html")
        if parts == ["api", "data"]:
            raw = store().read_all()
            return self._send_json(200, {
                k.split(".json")[0]: v for k, v in raw.items()
            })
        if parts == ["api", "validate"]:
            errors = store().validate()
            return self._send_json(200, {"ok": not errors, "problems": errors})
        if len(parts) == 2 and parts[0] in ("masjid", "event"):
            static = ROOT / parts[0] / parts[1] / "index.html"
            if not static.is_file():
                html, _title = self._detail_html(parts[0], parts[1])
                if html:
                    return self._send_html(200, html)
        return self._send_file(self.path.lstrip("/"))

    def do_POST(self):
        parts, _query = self._split()
        data = store()
        parsed = self._body()

        if parts == ["api", "validate"]:
            errors = data.validate()
            return self._send_json(200, {"ok": not errors, "problems": errors})

        if parts == ["api", "publish"]:
            ok, payload = data.publish()
            errors = payload if isinstance(payload, list) else []
            return self._send_json(200 if ok else 400, {"ok": ok, "problems": errors})

        if parts == ["api", "add-masjid"]:
            return self._add_masjid_batch(parsed)

        if parts == ["api", "preview"]:
            return self._handle_preview(parsed)

        if parts == ["api", "events"]:
            return self._create_record(parsed, "event")
        if parts == ["api", "masjids"]:
            return self._create_record(parsed, "masjid")
        if parts == ["api", "speakers"]:
            return self._create_record(parsed, "speaker")
        if parts == ["api", "categories"]:
            return self._create_record(parsed, "category")
        if parts == ["api", "mukims"]:
            return self._create_record(parsed, "mukim")
        if parts == ["api", "editors"]:
            return self._create_record(parsed, "editor")

        if len(parts) == 4 and parts[:2] == ["api", "events"] and parts[3] == "status":
            return self._set_event_status(parts[2], parsed)

        if len(parts) == 3 and parts[0] == "api":
            return self._update_record(parts[1], parts[2], parsed)

        return self._send_json(404, {"error": "not found"})

    def do_DELETE(self):
        parts, _query = self._split()
        if len(parts) == 3 and parts[0] == "api":
            return self._delete_record(parts[1], parts[2])
        return self._send_json(404, {"error": "not found"})

    def do_PUT(self):
        parts, _query = self._split()
        parsed = self._body()
        if len(parts) == 3 and parts[0] == "api":
            return self._update_record(parts[1], parts[2], parsed)
        return self._send_json(404, {"error": "not found"})

    # -- record operations ----------------------------------------------------

    def _collection(self, name):
        return {
            "events": "events.json",
            "masjids": "masjids.json",
            "speakers": "speakers.json",
            "categories": "categories.json",
            "mukims": "mukims.json",
            "editors": "editors.json",
        }.get(name)

    def _respond(self, ok, payload, ok_status, not_found=False, errors=None):
        if not_found:
            return self._send_json(404, {"error": "record not found"})
        if isinstance(payload, list):
            return self._send_json(400, {"errors": payload})
        if not ok:
            return self._send_json(400, {"errors": errors or ["operation failed."]})
        return self._send_json(ok_status, payload)

    def _create_record(self, parsed, kind):
        if parsed is None:
            return self._send_json(400, {"errors": ["request body is not valid JSON."]})
        data = store()

        def apply(all_data):
            if kind == "masjid":
                rec, errors = validate_masjid(parsed, all_data["mukims.json"])
            elif kind == "speaker":
                rec, errors = validate_speaker(parsed)
            elif kind == "category":
                rec, errors = validate_category(parsed)
            elif kind == "event":
                rec, errors = validate_event(parsed)
            elif kind == "mukim":
                rec, errors = validate_mukim(parsed)
            elif kind == "editor":
                rec, errors = validate_editor(parsed)
            else:
                raise ValueError("unknown type")
            if errors:
                raise _ValidationError(errors)
            coll = all_data["masjids.json" if kind == "masjid" else "speakers.json" if kind == "speaker"
                                else "categories.json" if kind == "category" else "events.json"
                                if kind == "event" else "mukims.json" if kind == "mukim"
                                else "editors.json"]
            if kind == "masjid":
                rec = {"id": next_masjid_id(rec["name"], coll), **rec}
            elif kind == "speaker":
                rec = {"id": next_speaker_id(rec["name"], coll), **rec}
            elif kind == "category":
                rec = {"id": next_category_id(rec["name"], coll), **rec}
            elif kind == "mukim":
                rec = {"id": next_mukim_id(rec["name"], coll), **rec}
            elif kind == "editor":
                rec = {"id": next_editor_id(rec["name"], coll), **rec}
            else:
                rec = {"id": next_event_id(rec["date"], coll), **rec}
            coll.append(rec)
            return {"ok": True, "id": rec["id"], "record": rec}

        try:
            ok, payload = data.mutate(apply)
            return self._respond(ok, payload, 201)
        except _ValidationError as exc:
            return self._send_json(400, {"errors": list(exc.errors_list)})
        except _NotFound:
            return self._send_json(404, {"error": "record not found"})

    def _add_masjid_batch(self, parsed):
        """Legacy endpoint kept for admin/add-masjid.html: create a masjid and
        its events in one request. {masjid: {...}, events: [{...}]}."""
        if parsed is None or not isinstance(parsed, dict):
            return self._send_json(400, {"errors": ["request body is not valid JSON."]})
        data = store()
        masjid_form = parsed.get("masjid", {})
        events_form = parsed.get("events", [])
        if not isinstance(events_form, list):
            return self._send_json(400, {"errors": ["events must be a list."]})
        if len(events_form) > 200:
            return self._send_json(400, {"errors": ["too many events (max 200)."]})

        def apply(all_data):
            masjid, errors = validate_masjid(masjid_form, all_data["mukims.json"])
            if errors:
                raise _ValidationError(errors)
            coll = all_data["masjids.json"]
            mid = next_masjid_id(masjid["name"], coll)
            categories = all_data["categories.json"]
            speakers = all_data["speakers.json"]
            parsed_events = []
            for idx, ev in enumerate(events_form):
                legacy = dict(ev)
                # legacy form posts category (id) + speaker (display name)
                if "category" in legacy and "category_id" not in legacy:
                    legacy["category_id"] = legacy.get("category")
                if "speaker" in legacy and "speaker_id" not in legacy:
                    legacy["speaker_id"] = legacy.get("speaker")
                legacy["masjid_id"] = legacy.get("masjid_id") or mid
                rec, errs = validate_event(legacy)
                if errs:
                    raise _ValidationError([f"event #{idx + 1}: {e}" for e in errs])
                parsed_events.append(rec)
            # resolve free-text speakers (legacy form posts speaker names)
            for ev in parsed_events:
                spk = str(ev.get("speaker_id") or "").strip()
                if not spk:
                    continue
                # speaker_id was provided as a display name in the legacy form
                sid = next((s.get("id") for s in speakers if s.get("name") == spk), None)
                if not sid:
                    sid = next_speaker_id(spk, speakers)
                    speakers.append({"id": sid, "name": spk, "description": ""})
                ev["speaker_id"] = sid

            coll.append({"id": mid, **masjid})
            evcoll = all_data["events.json"]
            created = []
            for ev in parsed_events:
                ev["masjid_id"] = mid
                ev["id"] = next_event_id(ev["date"], evcoll + created)
                evcoll.append(ev)
                created.append(ev)
            return {"ok": True, "masjid_id": mid,
                    "event_count": len(created),
                    "event_ids": [ev["id"] for ev in created]}

        try:
            ok, payload = data.mutate(apply)
            return self._respond(ok, payload, 200)
        except _ValidationError as exc:
            return self._send_json(400, {"errors": list(exc.errors_list)})

    def _update_record(self, collection, record_id, parsed):
        if parsed is None:
            return self._send_json(400, {"errors": ["request body is not valid JSON."]})
        data = store()
        fname = self._collection(collection)

        def apply(all_data):
            coll = all_data[fname]
            idx = next((i for i, r in enumerate(coll) if r.get("id") == record_id), None)
            if idx is None:
                raise _NotFound()
            if fname == "masjids.json":
                rec, errors = validate_masjid(parsed, all_data["mukims.json"])
            elif fname == "speakers.json":
                rec, errors = validate_speaker(parsed)
            elif fname == "categories.json":
                rec, errors = validate_category(parsed)
            elif fname == "mukims.json":
                rec, errors = validate_mukim(parsed)
            elif fname == "editors.json":
                rec, errors = validate_editor(parsed)
            else:
                rec, errors = validate_event(parsed)
            if errors:
                raise _ValidationError(errors)
            coll[idx] = {"id": record_id, **rec}
            return {"ok": True, "id": record_id, "record": coll[idx]}

        try:
            ok, payload = data.mutate(apply)
            return self._respond(ok, payload, 200)
        except _ValidationError as exc:
            return self._send_json(400, {"errors": list(exc.errors_list)})
        except _NotFound:
            return self._send_json(404, {"error": "record not found"})

    def _set_event_status(self, event_id, parsed):
        if parsed is None:
            return self._send_json(400, {"errors": ["request body is not valid JSON."]})
        status = str((parsed or {}).get("status", "")).strip()
        if status not in VALID_STATUSES:
            return self._send_json(400, {"errors": [f"invalid status: {status!r}."]})
        data = store()

        def apply(all_data):
            coll = all_data["events.json"]
            idx = next((i for i, r in enumerate(coll) if r.get("id") == event_id), None)
            if idx is None:
                raise _NotFound()
            coll[idx]["status"] = status
            return {"ok": True, "id": event_id, "status": status}

        try:
            ok, payload = data.mutate(apply)
            return self._respond(ok, payload, 200)
        except _NotFound:
            return self._send_json(404, {"error": "record not found"})

    def _delete_record(self, collection, record_id):
        data = store()
        fname = self._collection(collection)
        if fname is None:
            return self._send_json(404, {"error": "not found"})

        def apply(all_data):
            events = all_data["events.json"]
            masjids = all_data["masjids.json"]
            if fname == "masjids.json":
                field, refs_source = "masjid_id", events
            elif fname == "speakers.json":
                field, refs_source = "speaker_id", events
            elif fname == "categories.json":
                field, refs_source = "category_id", events
            elif fname == "mukims.json":
                field, refs_source = "mukim_id", masjids
            elif fname == "editors.json":
                field, refs_source = "editor_id", masjids
            else:
                field, refs_source = None, []
            if field:
                refs = [r.get("id") for r in refs_source if r.get(field) == record_id]
                if refs:
                    raise _ValidationError([
                        "cannot delete: still referenced by record(s): " + ", ".join(sorted(refs))])
            coll = all_data[fname]
            idx = next((i for i, r in enumerate(coll) if r.get("id") == record_id), None)
            if idx is None:
                raise _NotFound()
            coll.pop(idx)
            return {"ok": True, "id": record_id}

        try:
            ok, payload = data.mutate(apply)
            return self._respond(ok, payload, 200)
        except _ValidationError as exc:
            return self._send_json(400, {"errors": list(exc.errors_list)})
        except _NotFound:
            return self._send_json(404, {"error": "record not found"})

    def _detail_html(self, kind, rid):
        data = store().read_all()
        masjids = {m.get("id"): m for m in data["masjids.json"]}
        speakers = {s.get("id"): s for s in data["speakers.json"]}
        categories = {c.get("id"): c for c in data["categories.json"]}
        settings = data["settings.json"]
        site_name = settings.get("site_name") or "Masjid Events Perlis"

        if kind == "event":
            ev = next((e for e in data["events.json"] if e.get("id") == rid), None)
            if not ev:
                return None, None
            masjid = masjids.get(ev.get("masjid_id"))
            speaker = speakers.get(ev.get("speaker_id"))
            category = categories.get(ev.get("category_id"))
            body = build_site.event_body(ev, masjid, speaker, category, base="../../")
            summary = build_site.text_summary(ev, masjid, speaker)
            canonical = build_site.page_url("", f"event/{rid}/")
            share = (
                '<div class="share">'
                '<a class="btn btn-ghost" rel="noopener" target="_blank" href="{}">Kongsi WhatsApp</a>'
                '<a class="btn btn-ghost" rel="noopener" target="_blank" href="{}">Kongsi Telegram</a>'
                "</div>"
            ).format(build_site.whatsapp_url(summary + "\n" + canonical),
                     build_site.telegram_url(summary, canonical))
            body = body.replace("  </article>", "  </article>\n" + share)
            title = f"{ev.get('title') or ''} — {site_name}"
        elif kind == "masjid":
            masjid = next((m for m in data["masjids.json"] if m.get("id") == rid), None)
            if not masjid:
                return None, None
            today = date.today().isoformat()
            body = build_site.masjid_body(masjid, data["events.json"], masjids,
                                          categories, speakers, today, base="../../")
            title = f"{masjid.get('name') or ''} — {site_name}"
        else:
            return None, None
        html = (
            "<!DOCTYPE html><html lang=\"ms\"><head><meta charset=\"UTF-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
            + build_site.HEAD_META.format(
                base="../../", description=(body[:160] or title),
                canonical=build_site.page_url("", kind + "/" + rid + "/"),
                og_type="article" if kind == "event" else "website",
                og_title=title, og_description=(body[:160] or title), og_url="",
                title=title)
            + "</head><body>" + body + "</body></html>"
        )
        return html, title

    def _handle_preview(self, parsed):
        if parsed is None or not isinstance(parsed, dict):
            return self._send_json(400, {"errors": ["preview body must be JSON."]})
        kind = parsed.get("type")
        rid = parsed.get("id")
        if not kind or not rid:
            return self._send_json(400, {"errors": ["type and id are required."]})
        if kind not in ("event", "masjid"):
            return self._send_json(400, {"errors": ["type must be 'event' or 'masjid'."]})
        try:
            html, title = self._detail_html(kind, rid)
            if html is None:
                return self._send_json(404, {"error": f"{kind} not found"})
            return self._send_json(200, {"ok": True, "title": title, "html": html})
        except Exception as exc:  # preview should never 500 the admin UI
            return self._send_json(500, {"errors": [f"preview failed: {exc}"]})


class _ValidationError(Exception):
    def __init__(self, errors_list):
        super().__init__("validation failed")
        self.errors_list = errors_list


class _NotFound(Exception):
    pass


def main():
    global DATA_DIR, PUBLIC_DATA_DIR
    parser = argparse.ArgumentParser(description="Local Masjid Events Perlis admin editor.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--public-data", default=str(ROOT / "public" / "data"))
    args = parser.parse_args()

    DATA_DIR = Path(args.data_dir)
    PUBLIC_DATA_DIR = Path(args.public_data)

    store()._ensure_files()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    port = server.server_address[1]
    print(f"Masjid Events Perlis admin: http://localhost:{port}/admin/")
    print("Local tool only — do NOT deploy to GitHub Pages. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()