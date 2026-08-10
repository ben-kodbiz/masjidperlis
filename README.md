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
publish), speakers and categories; supports weekly recurring events with
exceptions; previews the public rendering; and validates every change,
rolling back if the data would become invalid. Use "Semak data" then
"Terbitkan (salin ke public/data)" to refresh the public mirror after edits —
deployment also refreshes it automatically. Legacy bulk entry (masjid +
schedule in one form) remains at `admin/add-masjid.html`.

## Documentation

- `ARCHITECTURE.md` — system architecture and design principles.
- `TODO_AGENT.md` — staged build roadmap and definitions of done.
- `CONTRIBUTING.md` — how to contribute.
- `SECURITY.md` — security reporting and practices.

## License

MIT — see [LICENSE](LICENSE).

## Roadmap

The project is built stage-by-stage. Current status and the full roadmap live in [`TODO_AGENT.md`](TODO_AGENT.md).