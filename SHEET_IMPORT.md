# SHEET_IMPORT.md

# Masjid Events Perlis — Google Sheets Adapter

**New here?** The practical, step-by-step guide (column templates, Excel→CSV,
deploying) is in `DATA_ENTRY_GUIDE.md`. This file is the technical reference
for the adapter.

**Stage 14.** An optional way to feed events (and reference data) into the
canonical JSON data set from Google Sheets. It is an *adapter*:

```text
Google Sheets (published CSV)  ->  import_google_sheet.py  ->  data/*.json  ->  tools/validate_data.py
```

No API key, no OAuth, no secret is used. The source spreadsheet only needs to
be *published to the web* (File > Share > Publish to web), which gives a
public CSV export that the importer downloads. If a sheet holds sensitive
information, do not use it with this tool.

## Guarantees

| Guarantee | Behaviour |
| --------- | --------- |
| Never destroys data | Records are only **added or updated by id**; local records absent from the sheet are kept. Nothing is ever pruned. |
| Invalid rows reported | Each bad row is listed with its sheet row number so it can be fixed; only the invalid rows are skipped. |
| Duplicate IDs detected | A second row using an id already used by an earlier row in the same sheet is rejected and reported. |
| Validated before writing | The *merged* result must pass `validate_data`; if it fails, nothing is written (your local data is untouched). |
| Stable IDs | Without an explicit `id` column, ids are derived (masjid/speaker from name, event from `date`), never renumbered. |

## Publishing the spreadsheet

1. File > Share > Publish to web.
2. Choose the whole sheet (or individual sheets/tabs) and the `Comma-separated values (.csv)` format; publish.
3. The importer builds export URLs from your spreadsheet id and each tab's `gid` — it needs no link, only the id.

## Configuration

Static config lives in `tools/sheets_import.example.json` (copy to
`tools/sheets_import.json` and fill in). Alternatively pass `--config PATH`.

```json
{
  "spreadsheet_id": "1AbCdEfGhIjKlMnOpQrStUv",
  "sources": {
    "masjids":    { "tab": "Masjids",    "gid": "0", "id_column": "id", "columns": { … } },
    "speakers":   { "tab": "Penceramah", "gid": "1", "id_column": "id", "columns": { … } },
    "categories": { "tab": "Kategori",   "gid": "2", "id_column": "id", "columns": { … } },
    "events":     { "tab": "Acara",      "gid": "3", "id_column": "id", "columns": { … } }
  }
}
```

Per-source options:

| Option     | Meaning |
| ---------- | ------- |
| `tab`      | Descriptive name, used in reports only. |
| `gid`      | Google tab id used to build `…/export?format=csv&gid=GID`. Omit to use the first tab. |
| `file`     | Use a local CSV instead of the network (offline / testing). When set, `gid` and `spreadsheet_id` are ignored. |
| `id_column`| Header that holds the canonical id. Given a row, the record is an **update** if the id already exists, otherwise a **create**. |
| `columns`  | Map of sheet header -> canonical field name. When absent, headers must equal the canonical field names. |

`spreadsheet_id` may also be overridden on the command line with
`--spreadsheet-id`.

## Column mappings

The reference data files must agree with `DATA_SCHEMA.md`.

`districts.json` and `editors.json` are not imported from sheets; they are
passed through untouched (maintain them via the admin tool or by editing the
JSON directly).

### Masjids tab

| Sheet header | Canonical field | Notes |
| ------------ | --------------- | ----- |
| `id` | `id` | optional; else slug from `name` |
| `Nama` | `name` | required |
| `Daerah` | `district` | optional; `district_id` is derived from a recognised Perlis district name |
| `Negeri` | `state` | default `Perlis` |
| `Alamat` | `address` | optional |
| `Latitud` | `latitude` | number, optional |
| `Longitud` | `longitude` | number, optional |
| `Kenalan` | `contact` | optional |
| `Laman web` | `website` | must start `http://`/`https://` |

### Speakers tab

| Sheet header | Canonical field | Notes |
| ------------ | --------------- | ----- |
| `id` | `id` | optional; else slug from `name` |
| `Nama` | `name` | required |
| `Penerangan` | `description` | optional |

### Categories tab

| Sheet header | Canonical field | Notes |
| ------------ | --------------- | ----- |
| `id` | `id` | optional; else slug from `name` |
| `Nama` | `name` | required |

### Events tab

| Sheet header | Canonical field | Notes |
| ------------ | --------------- | ----- |
| `id` | `id` | optional; else `evt-{date}-{NNN}` |
| `Tajuk` | `title` | required |
| `Masjid` | `masjid_id` | id **or** display name |
| `Tarikh` | `date` | `YYYY-MM-DD`, required |
| `Mula` | `start_time` | `HH:MM`, required |
| `Tamat` | `end_time` | `HH:MM`, optional |
| `Penceramah` | `speaker_id` | id or display name, optional |
| `Kategori` | `category_id` | id or display name, optional |
| `Lokasi` | `location` | optional |
| `Penerangan` | `description` | optional |
| `Status` | `status` | `draft`/`published`/`cancelled`/`postponed`/`completed` (default `published`) |
| `Jenis ulangan` | `recurrence_type` | `weekly`, optional |
| `Hari ulangan` | `recurrence_days` | comma-separated weekdays, e.g. `monday,friday` |
| `Mula ulangan` | `recurrence_start_date` | `YYYY-MM-DD`, optional |
| `Tamat ulangan` | `recurrence_end_date` | `YYYY-MM-DD`, optional |
| `Pengecualian` | `recurrence_exceptions` | comma-separated `YYYY-MM-DD` |

Reference cells (`Masjid`, `Penceramah`, `Kategori`) accept either the stable
id or the current display name; names are resolved against the *merged* data.
Reference tabs are processed before events, in the order categories, speakers,
masjids, events.

## Usage

```bash
# default config (tools/sheets_import.json or the .example.json)
python3 tools/import_google_sheet.py

# explicit config + id override, no network (validate only)
python3 tools/import_google_sheet.py --config tools/sheets_import.example.json \
    --spreadsheet-id 1AbC... --dry-run

# strict: abort (write nothing) if any row was skipped
python3 tools/import_google_sheet.py --config my.json --strict
```

Exit codes: `0` imported and validated (or dry-run ok), `1` configuration /
fetch error, `2` merged data failed validation or `--strict` aborted. On
success the canonical JSON in `data/` is rewritten (validated first); on any
failure it is left untouched.

Run `python3 tools/validate_data.py` after importing to double-check, then
publish the site merge via the admin tool's "Terbitkan" button or the deploy
workflow.