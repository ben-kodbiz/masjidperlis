# DATA_ENTRY_GUIDE.md

# Masjid Events Perlis — Data Entry & Deployment Guide

This is the practical, step-by-step guide for adding **masjids, penceramah
(speakers), kategori, and acara (events)** to the site. You have **two ways**
to feed data in, and both end at the same place (the canonical `data/*.json`
files that the live site is built from):

```text
+-----------------------------+      +---------------------------------+
| Google Sheet(s) published    |      | Local CSV / Excel (.xlsx) file(s)|
| to the web (CSV)             |      | (no export step needed)         |
+--------------+--------------+      +---------------+-----------------+
               v                                    v
     tools/import_google_sheet.py  (same tool for both!)
               |
               v
   data/*.json  (add + update by id, never delete)
               |
               v
   tools/validate_data.py  (must pass before anything is written)
               |
               v
   git add + git commit + git push  ->  GitHub Actions rebuilds + deploys
```

**Important:** the importer reads **CSV and native `.xlsx` workbooks** (Excel
dates/times are understood — no CSV export needed if you keep your files as
`.xlsx`). No Google API key or OAuth is needed for the Google Sheets route
either.

---

## 1. The four data files and their order

The importer understands four kinds of data. You can provide **all four, or
just the ones you maintain** — anything without a source is left untouched.
When present, they are processed in this order:

1. **Kategori** (categories)
2. **Penceramah** (speakers)
3. **Masjid** (masjids)
4. **Acara** (events) — may reference the three above by **id or name**

Mukims and editors are **not** imported from sheets — manage those via the
admin panel or by editing the JSON directly.

---

## 2. Option A — Google Sheets (no API key)

### 2.1 Create the spreadsheet

Create one Google Sheet with **four tabs**, one per data file:

| Tab name (any) | Contents        |
| -------------- | --------------- |
| `Kategori`     | categories      |
| `Penceramah`   | speakers        |
| `Masjids`      | masjids         |
| `Acara`        | events          |

Put the **column headers from section 5** in row 1 of each tab.

### 2.2 Publish it to the web

1. **File → Share → Publish to web**
2. Choose the whole sheet (or per-tab), format **Comma-separated values (.csv)**
3. Publish. The sheet now has a public CSV export URL; the importer only needs
   your **spreadsheet id** and each tab's **gid**.

> Only publish sheets that are safe to be public — there is no auth.

### 2.3 Get the spreadsheet id and each tab's gid

- **spreadsheet id**: the long ID in the sheet's URL, e.g.
  `1AbCdEfGhIjKlMnOpQrStUvWxYz...`
- **gid** (per tab): open the tab, look at the URL fragment
  `#gid=123456789` — that number is the tab's gid. (The first tab is
  usually `0`.)

### 2.4 Configure

Copy the example config and fill it in:

```bash
cp tools/sheets_import.example.json tools/sheets_import.json
```

Edit `tools/sheets_import.json`: set `"spreadsheet_id"` to your id and the
`gid` values to each tab's number. The `columns` mapping and `id_column`
are already filled in — leave them unless your headers differ.

### 2.5 Run

```bash
# preview only — validates, writes nothing
python3 tools/import_google_sheet.py --dry-run

# real import (validated first; nothing written if invalid)
python3 tools/import_google_sheet.py

# abort if ANY row is skipped
python3 tools/import_google_sheet.py --strict
```

---

## 3. Option B — Local CSV / Excel files (offline, no Google needed)

You can point each source at a local CSV **or `.xlsx`** file instead of a
Google tab. This is the same tool, just configured with `"file"` instead of
`"gid"`.

> **Simplest path (recommended):** the repo ships a ready-made
> **`data-entry/`** folder exactly for this. Open the four CSVs in Excel, add
> your rows under the header, then run `./data-entry/update.sh`. No config to
> write. See `data-entry/README.md`.

### 3.1 Prepare the files

Create four files — one per data file — in a folder, e.g. `my-data/`:

```
my-data/
  kategori.csv   (or .xlsx)
  penceramah.csv (or .xlsx)
  masjids.csv    (or .xlsx)
  acara.csv      (or .xlsx)
```

Each file has the headers from **section 5** in row 1. You can mix: one source
may be a CSV and another an `.xlsx`.

- **`.csv`**: use **UTF-8** encoding (Excel: **Save As → CSV UTF-8 (Comma
  delimited)**). A UTF-8 BOM is fine — the importer strips it.
- **`.xlsx`**: just save the workbook normally (**File → Save As → Excel
  Workbook**). Dates and times you type in Excel (`2026-08-20`, `20:00`) are
  converted automatically, and comma-containing values such as
  `monday,friday` need **no quoting**. A `.xlsx` with several tabs uses the
  first one, or set `"sheet": "TabName"` on that source to pick a specific tab.

### 3.2 Configure

Make a config like this (or any name; pass it with `--config`):

```json
{
  "spreadsheet_id": "",
  "sources": {
    "categories": { "file": "my-data/kategori.csv",   "id_column": "id", "columns": { … } },
    "speakers":   { "file": "my-data/penceramah.csv", "id_column": "id", "columns": { … } },
    "masjids":    { "file": "my-data/masjids.csv",    "id_column": "id", "columns": { … } },
    "events":     { "file": "my-data/acara.csv",      "id_column": "id", "columns": { … } }
  }
}
```

The keys **must** be named `categories`, `speakers`, `masjids`, `events`. The
file *names* are up to you, `file` may end in `.csv` or `.xlsx`, and paths are
resolved **relative to the config file's folder**, so you can keep the folder
anywhere and run from any directory. Optional per-source `"sheet"` picks a
worksheet inside an `.xlsx` workbook. Use the same `columns` maps as in
`tools/sheets_import.example.json`.

Only configure the sources you actually maintain — a missing source is left
untouched (so you can, for example, import just `events` every week without
touching masjids/speakers/categories).

### 3.3 Run

```bash
# daily driver: ready-made folder (import + validate)
./data-entry/update.sh

# or with your own config
python3 tools/import_google_sheet.py --config my-config.json --dry-run
python3 tools/import_google_sheet.py --config my-config.json
```

> When no `--config` is given, the tool automatically prefers
> `data-entry/config.json` if it exists (falling back to the Google Sheets
> config). So with the shipped folder you can even run the bare
> `python3 tools/import_google_sheet.py`.

---

## 4. File formats — CSV vs Excel (.xlsx)

The importer reads **both**; pick whichever you find easier.

| If you use… | What to do |
| ----------- | ---------- |
| **Microsoft Excel** | Save the file as **Excel Workbook (\*.xlsx)** and point the config's `"file"` at it. Dates/times and commas just work — **no CSV export**. |
| Microsoft Excel (CSV) | File → Save As → **CSV UTF-8 (Comma delimited) (\*.csv)**. One tab at a time. |
| LibreOffice Calc | File → Save As → **Excel 2007–365 (\*.xlsx)** or **Text CSV (.csv)** → Encoding **UTF-8**. |
| Google Sheets | File → Download → **Comma-separated values (.csv, current sheet)**. |

Excel `.xlsx` reading is built into the tool (Python standard library only, no
extra installs): cells you type a date or time into are converted from Excel's
internal numbers to the `YYYY-MM-DD` / `HH:MM` the site expects. If a workbook
has several tabs, the first is read unless a `"sheet"` name is configured.

---

## 5. Column templates (headers for row 1)

### Kategori (categories)

| `id` | `Nama` |
| ---- | ------ |
| *(blank)* | Kuliah |

`id` optional → generated from the name (e.g. `kuliah`).

### Penceramah (speakers)

| `id` | `Nama` | `Penerangan` |
| ---- | ------ | ------------ |
| *(blank)* | Ustaz Ahmad Firdaus | Pensyarah UIAM |

### Masjids (masjids)

| `id` | `Nama` | `Mukim` | `Negeri` | `Alamat` | `Latitud` | `Longitud` | `Kenalan` | `Laman web` |
| ---- | ------ | -------- | -------- | -------- | --------- | ---------- | --------- | ----------- |
| *(blank)* | Masjid Alwi | Kangar | Perlis | Jalan Tuanku Syed Putra, 01000 Kangar | 6.4405 | 100.1952 | | |

- `Mukim` accepts any of the 15 Perlis mukim names (Kangar, Arau, Padang
  Besar, Pauh, Beseri, Chuping, Bintong, Kurong Anai, Kayang, Mata Ayer,
  Oran, Sanglang, Simpang Empat, Tambun Tulang, Wang Bintong) — the
  `mukim_id` is linked automatically.
- `Latitud` / `Longitud` are decimal degrees (needed for maps/directions).

### Acara (events)

| `id` | `Tajuk` | `Masjid` | `Tarikh` | `Mula` | `Tamat` | `Penceramah` | `Kategori` | `Lokasi` | `Penerangan` | `Status` |
| ---- | ------- | -------- | -------- | ------ | ------- | ------------ | ---------- | -------- | ------------ | -------- |
| *(blank)* | Kuliyyah Maghrib | Masjid Alwi | 2026-08-20 | 20:00 | 21:00 | Ustaz Ahmad Firdaus | Kuliah | | Siri mingguan | published |

Recurring (weekly) — extra optional columns:

| `Jenis ulangan` | `Hari ulangan` | `Mula ulangan` | `Tamat ulangan` | `Pengecualian` |
| --------------- | -------------- | -------------- | --------------- | -------------- |
| weekly | monday,friday | 2026-08-20 | 2026-12-31 | 2026-08-28,2026-09-04 |

Rules:
- `Tarikh` = `YYYY-MM-DD`, `Mula`/`Tamat` = `HH:MM`, both required (except
  `Tamat`).
- `Masjid`, `Penceramah`, `Kategori` accept the **id or the display name**.
- `Status` = `draft` / `published` / `cancelled` / `postponed` /
  `completed` (default `published`).
- `Pengecualian` = comma-separated dates to drop from a weekly series.
- Leave `id` blank on new rows; it is generated and **never renumbered**, so
  re-importing the same row updates it instead of duplicating.

> **CSV quoting rule:** any value containing a comma — `Hari ulangan`
> (`monday,friday`) and `Pengecualian` (`2026-08-28,2026-09-04`) — must be
> wrapped in double quotes in the CSV: `"monday,friday"`. Google Sheets does
> this automatically on export, but if you hand-write or post-edit a CSV,
> unquoted commas produce extra columns and the import stops with a clear
> message telling you to quote the value. **This rule only applies to `.csv`
> files — `.xlsx` cells never need quoting.**

---

## 6. How the import behaves (guarantees)

- **Never deletes.** Rows are added or updated by id; anything already in your
  local data that is missing from the sheet is kept.
- **Idempotent.** Run it 10 times → same result. Leave the `id` column blank
  and the generated ids stay stable across runs (based on name/date).
- **Reports bad rows** with the sheet row number; invalid rows are skipped,
  good ones are imported.
- **Validates the whole merged result first.** If anything fails validation,
  **nothing** is written — your `data/` is untouched.
- **`--strict`** turns any skipped row into a full abort.

---

## 7. Deploying to the live site

After a successful import:

```bash
# 1. confirm the data is valid
python3 tools/validate_data.py

# 2. see it locally (public site)
python3 -m http.server 8000 --directory public

# 3. commit + push — GitHub Actions rebuilds and deploys automatically
git add data/
git commit -m "data: import from Google Sheet"
git push
```

The deploy workflow validates again, regenerates all pages, minifies, checks
performance budgets, and publishes. Within a minute or two your live site at
`https://ben-kodbiz.github.io/masjidperlis/` shows the new events. Check the
**Actions** tab for the green "Deploy to GitHub Pages" run.

> Working from a Google Sheet on a schedule? You can also clone this repo,
> run the importer on a cron/`schedule` trigger, and push — the deploy
> workflow handles the rest.

---

## 8. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `cannot fetch ... HTTP 400` | The sheet isn't published to the web, or the gid is wrong. Re-publish and double-check the gid. |
| `no spreadsheet_id configured` | Set `spreadsheet_id` or use `"file"` + `--config`. |
| `config has no source for: categories, speakers` | Outdated error — sources are now optional; a missing source is kept unchanged. Re-pull the latest code. |
| `ABORTED — merged data is invalid` | Read the listed problems (bad date, missing masjid, unknown mukim…), fix the rows, re-run. |
| Row skipped: `unknown masjid` | The masjid name/id isn't in the Masjids tab (or is misspelled). |
| `Invalid UTF-8` / mojibake in names | Re-save the CSV as **UTF-8** (see section 4). |
| `.xlsx` reads the wrong tab | Set `"sheet": "TabName"` on that source to pick a worksheet (default: first tab). |
| Site not updating after push | Check the Actions tab — the deploy workflow (not just validate) must finish green. |
| Wrong mukim link | `Mukim` must be one of the 15 official Perlis names; use the Malay name exactly. |
