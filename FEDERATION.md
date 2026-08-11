# FEDERATION.md

# Masjid Events Perlis — Event Feed Federation

`tools/federate.py` aggregates **multiple independent event feeds** into the
canonical data set in one run. It is the multi-source counterpart to the
single-source Google Sheets adapter (`tools/import_google_sheet.py`).

All feeds normalize into the canonical schema defined in `DATA_SCHEMA.md`
before they are merged: federated collections are `masjids`, `events`,
`speakers`, `categories`. `settings.json`, `districts.json` and `editors.json`
always pass through unchanged — maintain those via the admin tool or JSON.

It is a local tool like the admin server and the sheet importer; it is not
part of the public site, and it requires no API keys (see header secrets
below).

## Feed types

| Type            | Loads from                                        | Use case                                   |
| --------------- | ------------------------------------------------- | ------------------------------------------ |
| `local-json`    | a JSON file on disk (`path`)                      | Git-repo workspace clones, exports, offline |
| `json-url`      | a JSON document over HTTP(S) (`url`)              | published JSON URL feeds                   |
| `rest`          | same loader as `json-url` (alias)                 | REST API endpoints returning JSON          |
| `google-sheet`  | published-to-web CSV export (`sources`, `spreadsheet_id`) | Google Sheets tabs               |

A Git repository is ingested by cloning it into a local workspace and pointing
a `local-json` feed at the JSON inside that clone — no git/GitHub credentials
are needed by this tool.

## Config

Default config: `tools/feeds.json` (fallback `tools/feeds.example.json`), or
`--config <path>`. The config is a JSON object with a `feeds` array:

```json
{
  "feeds": [
    {
      "name": "Cawangan Arau",
      "type": "local-json",
      "path": "./cawangan-arau.json",
      "collections": ["masjids", "events"]
      ,"fields": { "tarikh": "date" }
    },
    {
      "name": "Portal acara",
      "type": "json-url",
      "url": "https://example.org/acara.json",
      "collections": ["events"],
      "timeout": 30
    }
  ]
}
```

Per-feed fields:

| Field          | Used by            | Meaning                                                       |
| -------------- | ------------------ | ------------------------------------------------------------- |
| `name`         | all                | label used in reports                                         |
| `type`         | all                | one of `local-json`, `json-url`, `rest`, `google-sheet`       |
| `path`         | `local-json`       | JSON file; relative paths resolve against the config dir      |
| `url`          | `json-url`/`rest`  | endpoint/document URL                                         |
| `headers`      | `json-url`/`rest`  | HTTP headers; `${NAME}` expands from the environment          |
| `timeout`      | `json-url`/`rest`  | request timeout in seconds (default 30)                       |
| `collections`  | JSON feeds         | which collections the payload provides (see below)            |
| `fields`       | JSON feeds         | feed field name -> canonical field name map                   |
| `sources`      | `google-sheet`     | the full sheets_import source map (all four tabs)             |
| `spreadsheet_id`| `google-sheet`    | spreadsheet id for remote CSV export                          |

### JSON payload shapes

A `local-json` / `json-url` / `rest` payload may be either:

1. an **object** keyed by collection: `{"masjids": [...], "events": [...], ...}`,
   or
2. an **array** when the feed declares exactly one `collections` entry, e.g.
   `"collections": ["events"]`.

Each record uses canonical field names, optionally remapped via `fields`.
Missing ids are derived: masjid/speaker/category from `name`, events from
`date` (`evt-{YYYYMMDD}-{NNN}`, never renumbered or colliding). Events may
carry a nested `recurrence` object (see `DATA_SCHEMA.md`) or the rolled-up
`recurrence_*` columns.

Reference cells (`masjid_id`, `speaker_id`, `category_id`) accept either the
canonical id or the current display name, resolved against **everything already
merged** (existing data plus earlier feeds), so a masjid created by feed A can
be referenced by an event in feed B. Masjid `district_id` is derived from the
free-text `district` using the official Perlis district names.

### Header secrets

`headers` values may reference the environment, e.g.
`"Authorization": "Bearer ${FEED_API_TOKEN}"`. Tokens therefore live in the
environment or CI secrets, never in the config or the repository. Feeds that
do not need auth simply omit `headers`.

### Google Sheets feed

A `google-sheet` feed reuses the sheet adapter in-process. Its `sources` map
matches `tools/sheets_import.example.json` (four tabs required; use local CSV
`file` sources for offline operation). It is validated and reported exactly
like the other feeds.

## Merge semantics

* Records are **only added or updated by id — never deleted** (no pruning).
  Local records absent from a feed are preserved.
* Later feeds may update records created by earlier feeds or existing data.
* A row that fails validation, or whose references cannot be resolved, is
  **skipped and reported** (feed / collection / row number / reason).
* Duplicate explicit ids inside one feed are rejected (first wins).
* On any merged-data validation failure the run **aborts** and `data/` is left
  byte-for-byte untouched. `--dry-run` validates without writing; `--strict`
  aborts as soon as any row is skipped.

## Usage

```text
python3 tools/federate.py                              # tools/feeds.json or .example
python3 tools/federate.py --config tools/feeds.example.json
python3 tools/federate.py --data-dir data
python3 tools/federate.py --dry-run                    # validate only
python3 tools/federate.py --strict                     # abort if a row is skipped
```

Exit codes: `0` success (or dry-run), `1` runtime error (bad config,
unreadable feed), `2` abort (invalid merged data, or `--strict` skip).

After a successful run, publish the mirror to `public/data/` with the admin
tool's **Terbitkan** step (or `cp data/*.json public/data/`).