# ADMIN_GUIDE.md

# Masjid Events Perlis — Admin & Editor Guide

The admin application is a **local, developer/editor-only tool**. It runs on
your machine, edits the canonical JSON in `data/`, and writes the published
copy that the public site reads. It is never deployed to the public site.

> The public site and any live deployment are completely separate from this
> tool — see `DEPLOYMENT.md`. Nothing you do here touches a live website
> until you either run **Terbitkan** (which updates the local `public/data`
> mirror) or push the repository to GitHub.

## 1. Starting the panel

```bash
python3 tools/serve.py
# open http://localhost:8000/admin/
```

- Binds to `127.0.0.1` only — safe on your own machine, not a server.
- Options: `--port 8080`, `--data-dir data`, `--public-data public/data`.
- All edits are validated before they are saved; broken data rolls back.

## 2. What you can manage

| Page        | Purpose                                                              |
| ----------- | -------------------------------------------------------------------- |
| Ringkasan   | Dashboard with counts + **Semak data** / **Terbitkan** (section 5)   |
| Acara       | List, filter, edit, and change event status                          |
| Masjid      | Create/edit masjids, assign mukim + editor, delete (blocked if referenced) |
| Penceramah  | Speaker profiles used by events                                      |
| Kategori    | Event categories                                                     |
| Mukim      | Mukims (the demo data ships 15); masjids reference a mukim |
| Editor      | Editor accounts associated with masjids (organizational model)       |

Legacy bulk entry (a masjid plus a repeating schedule in one form) remains at
`admin/add-masjid.html`.

## 3. Events

Create an event from **Acara → "+ Cipta acara"** (or the **event-editor** page):

- **Tajuk** (title), **Masjid** (required), **Tarikh** + **Mula** (required),
  **Penceramah**, **Kategori**, **Keterangan**, **Status**.
- **Berulang mingguan**: pick the weekdays and optional start/end dates.
  Individual occurrences can be removed with **pengecualian** (exceptions).

Status transitions (buttons on the Acara list):

| Status   | Meaning                                  |
| -------- | ---------------------------------------- |
| draft    | Not shown publicly                       |
| published| Visible on the public site               |
| cancelled| Visible with a **dibatalkan** notice     |
| postponed| Visible with a **ditangguhkan** notice   |
| completed| Archived; hidden.                        |

Delete is blocked while masjids/speakers/categories are still referenced by
events — remove or re-point the references first.

## 4. Recurring events

A weekly recurring event appears once per matched weekday in the public
calendar. Use **pengecualian** (`recurrence.exceptions`, ISO dates) to drop a
single occurrence (e.g. a public-holiday cancellation). Exceptions are
respected by the public site, the static generator, and `.ics` export.

## 5. Validate and publish

The public site reads JSON from `public/data/`. The browsers never see the
canonical `data/`. Two buttons on the **Ringkasan** page keep them in sync:

1. **Semak data** — runs the same validator as CI (`tools/validate_data.py`)
   against `data/` and reports problems without changing anything.
2. **Terbitkan (salin ke public/data)** — validates `data/` once more, then
   copies the mirrored JSON files into `public/data/`. It aborts without
   writing if the data is invalid.

Deployment also refreshes the mirror automatically (GitHub Actions copies
`data/*.json` into the artifact), so Terbitkan is mainly for local previews
of the public site:

```bash
python3 tools/build_site.py                       # generate masjid/event detail pages
python3 -m http.server 8000 --directory public   # after Terbitkan
open http://localhost:8000
```

## 6. Importing external data

- One Google Sheet: `python3 tools/import_google_sheet.py --config tools/sheets_import.example.json` — see `SHEET_IMPORT.md`.
- Multiple independent feeds: `python3 tools/federate.py --config tools/feeds.example.json` — see `FEDERATION.md`.

Both merge add/update-by-id (never delete), report skipped rows, and validate
the whole result before writing. Then use **Semak data** → **Terbitkan** from
the panel (or run the exporters) so the public mirror is updated too.

## 7. Data format

The canonical schema lives in `DATA_SCHEMA.md` (all files, required/optional
fields, ID rules, date/time conventions, recurrence format). IDs are strict:
`^[a-z0-9]+(-[a-z0-9]+)*$`. Every change is validated against it before it is
accepted.