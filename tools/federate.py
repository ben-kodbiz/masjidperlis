#!/usr/bin/env python3
"""Masjid Events Perlis — feed federation tool (multiple data sources).

Aggregates several independent event feeds into the canonical data set in one
run. Supported feed types:

    local-json    reads a JSON file from the local filesystem (the recommended
                  way to ingest a Git-repo workspace: point the feed at the
                  JSON inside a local clone).
    json-url      fetches a JSON document over HTTP(S); the same loader backs
                  `rest` feeds (REST API endpoints returning JSON). Header
                  values may reference environment variables ("${NAME}") so
                  tokens never live in the config file.
    google-sheet  reuses tools/import_google_sheet.py in-process
                  (published-to-web CSV export; no API key/secret).

Every feed normalizes into the canonical schema (see DATA_SCHEMA.md) before it
is merged. All feeds are applied in config order, then the FULL merged set is
validated BEFORE anything is written to data/:

  - records are only added or updated by id, never deleted (no pruning);
  - a row that fails validation, or whose reference cells (masjid/speaker/
    category) cannot be resolved, is skipped and reported;
  - duplicate explicit ids inside one feed are rejected (first wins);
  - generated ids never collide with existing records or earlier feeds;
  - on any merged-data validation failure the run ABORTS and data/ is left
    byte-for-byte untouched.

Only the federated collections (masjids, events, speakers, categories) are
imported. settings.json, mukims.json and editors.json pass through
unchanged — maintain those via the admin tool or JSON.

Usage:
    python3 tools/federate.py                      # tools/feeds.json or .example
    python3 tools/federate.py --config tools/feeds.example.json
    python3 tools/federate.py --data-dir data --dry-run
    python3 tools/federate.py --strict             # abort if any row skipped

Exit codes:
    0   success (or --dry-run finished)
    1   runtime error (bad config, unreadable feed)
    2   abort: merged data invalid or (--strict) rows were skipped
"""

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "tools"))

from serve import (  # noqa: E402
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
from import_google_sheet import (  # noqa: E402
    Importer,
    ImportConfig,
    KINDS,
    _RowError,
    read_json,
    resolve_ref,
)

FEED_TYPES = ("local-json", "json-url", "rest", "google-sheet")
IMPORTABLE = ("masjids.json", "events.json", "speakers.json", "categories.json")
KIND_NAMES = ("masjids", "events", "speakers", "categories")
VALIDATORS = {
    "masjids": validate_masjid,
    "speakers": validate_speaker,
    "categories": validate_category,
    "events": validate_event,
}
NEXT_IDS = {
    "masjids": next_masjid_id,
    "speakers": next_speaker_id,
    "categories": next_category_id,
}


def _expand_env(value):
    """Expand ``${NAME}`` placeholders from the environment (feed headers)."""
    return os.path.expandvars(str(value)) if isinstance(value, str) else value


def fetch_json_document(feed, config_dir):
    """Return (document, source_label) for a local-json / json-url feed."""
    ftype = str(feed.get("type") or "").strip().lower()
    if ftype in ("json-url", "rest"):
        url = str(feed.get("url") or "").strip()
        if not url:
            raise RuntimeError(f"feed {feed.get('name', '?')}: 'url' is required for {ftype}.")
        headers = {}
        for key, value in (feed.get("headers") or {}).items():
            headers[key] = _expand_env(value)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=int(feed.get("timeout") or 30)) as resp:
                return json.loads(resp.read().decode("utf-8")), url
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"cannot fetch {url}: HTTP {exc.code}")
        except OSError as exc:
            raise RuntimeError(f"cannot fetch {url}: {exc}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"cannot parse JSON from {url}: {exc}")
    path_raw = str(feed.get("path") or "").strip()
    path = Path(path_raw)
    if not path.is_absolute():
        path = config_dir / path
    if not path.is_file():
        raise RuntimeError(f"feed {feed.get('name', '?')}: file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8")), str(path)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cannot parse JSON from {path}: {exc}")


def _resolve_feed_records(feed, kind, records, working, skipped):
    """Return the normalized, merged records for one collection in a JSON feed.

    Appends skip entries to `skipped` and mutates `working[f"{kind}.json"]`.
    """
    name = str(feed.get("name") or "json-feed")
    fields_cfg = feed.get("fields") or {}
    coll_key = f"{kind}.json"
    target = working.setdefault(coll_key, [])
    used = [dict(r) for r in target]
    in_payload = set()

    for row_no, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            skipped.append((name, kind, row_no, "expected an object"))
            continue
        fields = {}
        for key, value in raw.items():
            field = fields_cfg.get(key, key) if isinstance(fields_cfg, dict) else key
            if value is None or value == "":
                continue
            fields[field] = value

        explicit = str(fields.get("id") or "").strip() or None
        if explicit:
            if explicit in in_payload:
                skipped.append((name, kind, row_no, f"duplicate id {explicit!r} in this feed"))
                continue
            in_payload.add(explicit)
            _id = explicit
        else:
            try:
                if kind == "events":
                    _id = next_event_id(fields.get("date", ""), used)
                else:
                    _id = NEXT_IDS[kind](fields.get("name", ""), used)
                in_payload.add(_id)
            except _RowError as exc:
                skipped.append((name, kind, row_no, str(exc)))
                continue

        if kind == "events":
            failed = False
            for ref_kind, field in (("masjids", "masjid_id"),
                                    ("speakers", "speaker_id"),
                                    ("categories", "category_id")):
                value = fields.get(field)
                if value:
                    try:
                        fields[field] = resolve_ref(value, working[f"{ref_kind}.json"])
                    except _RowError as exc:
                        skipped.append((name, kind, row_no, f"{field}: {exc}"))
                        failed = True
                        break
            if failed:
                continue
            rec, errors = validate_event(fields)
        else:
            rec, errors = VALIDATORS[kind](fields)
            if not errors and kind == "masjids":
                rec["mukim_id"] = mukim_id_for(rec.get("mukim"))
        if errors:
            skipped.append((name, kind, row_no, "; ".join(errors)))
            continue

        new_rec = {"id": _id, **rec}
        idx = next((i for i, r in enumerate(target) if r.get("id") == _id), None)
        if idx is None:
            target.append(new_rec)
            used.append(new_rec)
        else:
            target[idx] = new_rec


def normalize_json_feed(feed, doc, working, skipped):
    """Fetch document shape and fan out each collection to the normalizer."""
    name = str(feed.get("name") or "json-feed")
    collections = feed.get("collections") or []
    if isinstance(collections, str):
        collections = [collections]
    for c in collections:
        if c not in KIND_NAMES:
            raise RuntimeError(f"feed {name}: unknown collection {c!r}.")

    if isinstance(doc, list):
        if len(collections) != 1:
            raise RuntimeError(
                f"feed {name}: a JSON array feed needs exactly one 'collection' "
                "(e.g. \"collections\": [\"events\"]).")
        mapping = {collections[0]: doc}
    elif isinstance(doc, dict):
        mapping = {k: v for k, v in doc.items() if k in KIND_NAMES}
        if collections and collections != KIND_NAMES:
            mapping = {k: v for k, v in mapping.items() if k in collections}
    else:
        raise RuntimeError(f"feed {name}: JSON payload must be an array or an object.")

    for kind, records in mapping.items():
        before = len(working.get(f"{kind}.json", []))
        _resolve_feed_records(feed, kind, records, working, skipped)
        count = len(working.get(f"{kind}.json", [])) - before
        if count:
            print(f"  {kind}: {count} record(s) normalised")


def normalize_sheet_feed(feed, working, skipped):
    """Normalize a google-sheet feed via tools/import_google_sheet (in-process)."""
    cfg = ImportConfig(feed)
    imp = Importer(cfg)
    imp.load_all()
    existing = {f"{k}.json": working[f"{k}.json"] for k in KINDS}
    merged, sheet_skipped = imp.normalize(existing)
    for kind, rows in sheet_skipped.items():
        for row_no, msg in rows:
            skipped.append((feed.get("name", "google-sheet"), kind, row_no, msg))
    for fname, records in merged.items():
        if records is not None:
            working[fname] = records


def apply_feed(feed, working, skipped, config_dir):
    name = str(feed.get("name") or "feed")
    ftype = str(feed.get("type") or "").strip().lower()
    if ftype not in FEED_TYPES:
        raise RuntimeError(f"feed {name}: unknown type {ftype!r} (allowed: {FEED_TYPES}).")
    if ftype == "google-sheet":
        normalize_sheet_feed(feed, working, skipped)
    else:
        doc, label = fetch_json_document(feed, config_dir)
        print(f"  source: {label}")
        normalize_json_feed(feed, doc, working, skipped)


def run(config_path, data_dir, strict=False, dry_run=False):
    with open(config_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    feeds = config.get("feeds")
    if not isinstance(feeds, list) or not feeds:
        raise RuntimeError("config must contain a non-empty 'feeds' list.")
    config_dir = Path(config_path).resolve().parent
    data_root = Path(data_dir)

    working = {}
    for fname in IMPORTABLE:
        working[fname] = read_json(data_root / fname, [])
    pass_through = {
        fname: read_json(data_root / fname, {} if fname == "settings.json" else [])
        for fname in ("settings.json", "mukims.json", "editors.json")
    }

    skipped = []
    print("Federation report")
    print("-" * 40)
    for feed in feeds:
        name = str(feed.get("name") or "feed")
        print(f"Applying feed {name!r}")
        apply_feed(feed, working, skipped, config_dir)

    # validate the FULL merged set against a throwaway copy before writing
    problems = []
    with tempfile.TemporaryDirectory(prefix="mvp-federate-") as tmp:
        tmpdir = Path(tmp)
        for fname, records in {**working, **pass_through}.items():
            with open(tmpdir / fname, "w", encoding="utf-8") as fh:
                json.dump(records, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        problems = validate_directory(tmpdir)

    if skipped:
        print(f"\nSkipped rows ({len(skipped)}):")
        for feed_name, kind, row_no, msg in skipped:
            print(f"  - {feed_name} {kind} row {row_no}: {msg}")
    print(f"\nValidation problems: {len(problems)}")

    if problems:
        print("\nABORTED — merged data is invalid. Your local data was NOT changed.",
              file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    if strict and skipped:
        print("\nABORTED (--strict) — rows were skipped; nothing written.",
              file=sys.stderr)
        return 2

    if dry_run:
        print("\nDry run — data validated; not writing (no change to data/).")
        return 0

    for fname, records in working.items():
        with open(data_root / fname, "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    print(f"\nFederated and validated. Wrote canonical JSON to {data_dir}.")
    print("Run the admin tool's Terbitkan step to sync public/data/.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Federate multiple event feeds into canonical JSON.")
    parser.add_argument("--config", default=None,
                        help="feed config (default: tools/feeds.json, else tools/feeds.example.json)")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--strict", action="store_true",
                        help="abort (write nothing) if any row was skipped")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate only; do not write data/")
    args = parser.parse_args(argv)

    if args.config:
        config_path = Path(args.config)
    else:
        default = ROOT / "tools" / "feeds.json"
        config_path = default if default.exists() else ROOT / "tools" / "feeds.example.json"
    if not config_path.is_file():
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 1
    if not Path(args.data_dir).is_dir():
        print(f"error: data dir not found: {args.data_dir}", file=sys.stderr)
        return 1

    try:
        return run(config_path, args.data_dir,
                   strict=args.strict, dry_run=args.dry_run)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())