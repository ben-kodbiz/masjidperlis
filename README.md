# Masjid Events Perlis

Penerbitan program dan aktiviti masjid di Negeri Perlis — sebuah platform web sumber-terbuka yang ringan untuk mempublikasikan kuliyyah, ceramah, tazkirah, tafsir, hadis, fiqh, dan program komuniti.

The primary goal: a stable, searchable, shareable public web presence for masjid events — independent of Facebook and other social-media platforms.

## Why

Masjid committees currently share events through Facebook posts, WhatsApp groups, and Telegram channels. This project provides a permanent, static, open alternative:

- **No login** for visitors.
- **No backend** or database for the public site.
- **No API keys** required.
- Deployable entirely to **GitHub Pages**.
- Built with **HTML, CSS, vanilla JavaScript, JSON, and Python**.

## Applications

| Application | Purpose | Requires backend? |
| ----------- | ------- | ----------------- |
| Public site (`public/`) | Read-only, mobile-first event listing and masjid directory | No |
| Admin / editor tools (`admin/`, `tools/`) | Create, edit, cancel events | No (local/data adapter) |

## Repository layout

```text
masjid-events/
├── ARCHITECTURE.md          # architecture document
├── TODO_AGENT.md            # stage-by-stage build plan
├── public/                  # static public site (GitHub Pages)
├── data/                    # canonical JSON data
├── admin/                   # admin/data-management UI
├── tools/                   # Python tooling (validation, import, build)
├── tests/                   # tests
└── .github/workflows/       # GitHub Actions
```

## Local development

Serve the `public/` folder with any static server, for example:

```bash
python3 -m http.server 8000 --directory public
```

Run data validation:

```bash
python3 tools/validate_data.py
```

The public site reads its JSON from `public/data/`. The deploy workflow refreshes `public/data/` from the canonical `data/` automatically. For local testing, copy current data once:

```bash
mkdir -p public/data && cp data/*.json public/data/
```

## Admin / data-management tool

A **local** control panel turns simple browser forms into canonical JSON. It is
for editors/developers only: it runs on your machine, is not part of the public
site, and must not be deployed to GitHub Pages.

```bash
python3 tools/serve.py
# open http://localhost:8000/admin/
```

The panel manages masjids, events (create / edit / cancel / postpone / archive /
publish), speakers, categories, mukims and editors; supports weekly recurring
events with exceptions; previews the public rendering; and validates every
change, rolling back if the data would become invalid. Use "Semak data" then
"Terbitkan (salin ke public/data)" to refresh the public mirror after edits —
deployment also refreshes it automatically. Legacy bulk entry (masjid +
schedule in one form) remains at `admin/add-masjid.html`.

## Importing data

**Daily driver (recommended):** the `data-entry/` folder holds ready-made CSV
templates — open them in Excel, add rows, run:

```bash
./data-entry/update.sh
```

Google Sheets (published-to-web CSV export) — no API key:

```bash
python3 tools/import_google_sheet.py --config tools/sheets_import.example.json
```

Multiple independent feeds (JSON URL, REST API, Git-repo workspace JSON,
Google Sheets) aggregated in one run:

```bash
python3 tools/federate.py --config tools/feeds.example.json --dry-run
```

All of these merge add/update-by-id (never delete existing data), report
skipped rows, and validate the full result before writing anything. See
`DATA_ENTRY_GUIDE.md`, `SHEET_IMPORT.md` and `FEDERATION.md`.

## Performance

The site is deliberately static and small — no frameworks, no page images, and
each page loads only the scripts it needs. Measured on the current build every
page fetches ≈ **40 kB (unminified)** / ≈ **15 kB gzipped** (GitHub Pages
serves automatic gzip/brotli). Deploy-time running of
`tools/minify_assets.py` strips comments/blank lines from `public/js` and
`public/css` inside the artifact (the committed source stays readable).

Measure and enforce the budget:

```bash
python3 tools/perf_report.py        # deploy sizes: minified + approx gzip
python3 tools/perf_report.py --raw  # committed, unminified sizes
```

CI fails if a page exceeds the budgets (initial ≤ 80 kB raw / 30 kB gzipped,
≤ 15 requests, ≤ 60 kB JS, ≤ 20 kB CSS).

## Trying it yourself

```bash
python3 -m http.server 8000 --directory public   # public site → :8000
python3 tools/serve.py                            # admin panel → :8000/admin/
open http://localhost:8000
```

The admin panel's "Semak data" verifies a change and "Terbitkan" mirrors it
into `public/data/`; run `node --check public/js/*.js` and
`python3 tools/validate_data.py` after edits. A live, public deployment runs
automatically when this repository is pushed to GitHub (see `deploy.yml`).

## Documentation

- `ARCHITECTURE.md` — system architecture and design principles.
- `TODO_AGENT.md` — staged build roadmap, definitions of done, and session history.
- `DATA_SCHEMA.md` — canonical data format (all files, fields, ID rules, recurrence).
- `DATA_ENTRY_GUIDE.md` — practical how-to: Google Sheets or local CSV/Excel → live site.
- `ADMIN_GUIDE.md` — editor workflow: the panel, recurring events, statuses, validate/publish.
- `DEPLOYMENT.md` — GitHub Pages deployment, first-time setup, custom domains, troubleshooting.
- `SHEET_IMPORT.md` — Google Sheets adapter (no API key).
- `FEDERATION.md` — multi-feed federation tool.
- `CONTRIBUTING.md` — how to contribute.
- `SECURITY.md` — security reporting, boundary, and automated audit.

## License

MIT — see [LICENSE](LICENSE).

## Roadmap

The project is built stage-by-stage. Current status and the full roadmap live in [`TODO_AGENT.md`](TODO_AGENT.md).