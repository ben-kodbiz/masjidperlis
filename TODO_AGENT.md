# TODO_AGENT.md

# Masjid Events Perlis — Agent Build Plan

## 0. Project Mission

Build a lightweight, open-source web application for masjids in Perlis to publish:

* Kuliyyah, Ceramah, Tazkirah, Tafsir, Hadith lessons, Fiqh lessons
* Religious programs, Community programs, Youth / children programs
* Special events, Recurring weekly events

The system must reduce dependency on Facebook and other social-media platforms by providing a permanent, searchable, shareable public web presence for masjid events.

The project consists of two logical applications:

1. **Public application** — completely read-only, mobile-first, static hosting, no login, no database, deployable to GitHub Pages.
2. **Administration/data-management application** — used by authorized editors. Creates/updates/cancels events. Initially may use Google Sheets as a convenient data-entry source. Google must NOT become a fundamental architectural dependency.

---

# 1. Non-Negotiable Design Principles

1.1 Lightweight — prefer HTML5, Vanilla CSS, Vanilla JS, JSON, Python tooling, GitHub Actions, GitHub Pages. Avoid React/Vue/Angular/Next.js/Tailwind/Bootstrap/Node/Express/Firebase/Supabase/PostgreSQL/MongoDB/Docker unless there is a compelling reason.

1.2 Public site must be static — no backend, no database, no login, no API key, no secrets, no Google auth, no Google Maps API.

```text
events.json / masjids.json / speakers.json / categories.json
    -> Public HTML + CSS + JavaScript
    -> GitHub Pages
```

1.3 Data source must be replaceable — use an adapter concept (JSON, CSV, Google Sheets, Git repository, future API). All sources produce the same normalized data model.

1.4 Security — never put secrets into `public/`, frontend JS, generated JSON/HTML/CSS, GitHub Pages. Use GitHub Actions secrets for future write/sync operations.

1.5 Open-source first — open formats, open standards, no vendor lock-in. The project must remain useful if Google disappears.

---

# 2. Development Rules for Coding Agent

Work stage-by-stage. For every stage:

1. Read `ARCHITECTURE.md`.
2. Inspect the existing repository.
3. Implement only the current stage.
4. Run validation/tests.
5. Fix errors.
6. Update documentation.
7. Mark the stage complete in this file.
8. Do not silently implement future-stage functionality.
9. Keep commits logically separable when possible.

Before modifying existing functionality: `inspect -> understand -> modify -> test`. Do not rewrite working modules unnecessarily.

---

# 3. Definition of Done

A stage is complete only when all apply:

- [x] Code implemented
- [x] Existing functionality still works
- [x] Validation passes
- [ ] No obvious console errors
- [ ] Mobile layout checked
- [x] Documentation updated
- [x] No secrets introduced
- [x] Checklist updated
- [x] Git diff reviewed

---

# 4. Stage 0 — Repository Bootstrap

## Objective

Create the initial repository structure and project documentation.

### Tasks

- [x] Create project directory structure.
- [x] Create `README.md`.
- [x] Create `ARCHITECTURE.md`.
- [x] Create `TODO_AGENT.md`.
- [x] Create `LICENSE`.
- [x] Create `CONTRIBUTING.md`.
- [x] Create `SECURITY.md`.
- [x] Create `.gitignore`.
- [x] Create initial GitHub Pages deployment workflow.
- [x] Verify repository can deploy a basic page (verified locally with a static server; live GitHub Pages verification requires a remote).

### Expected structure

```text
masjid-events/
├── README.md
├── ARCHITECTURE.md
├── TODO_AGENT.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── .gitignore
│
├── public/
├── data/
├── admin/
├── tools/
├── tests/
│
└── .github/
    └── workflows/
```

### Acceptance test
- [ ] GitHub Pages successfully serves the initial site (pending live deployment).
- [x] No backend is required.

---

# 5. Stage 1 — Data Model

## Objective

Define the canonical data format before building UI.

Create `data/events.json`, `data/masjids.json`, `data/speakers.json`, `data/categories.json`, `data/settings.json`.

> **Early local tool (added by request):** `tools/serve.py` + the `admin/` control panel provide a local browser UI for managing masjids, events (create/edit/cancel/postpone/archive/publish), speakers and categories, with preview and validate-before-publish. It is a local/data-management tool, not part of the public site. Server-side validation (with rollback), stable-ID generation, and duplicate handling are enforced.

## 5.1 Event schema

Minimum fields: `id`, `title`, `masjid_id`, `date`, `start_time`, `end_time`, `speaker_id`, `category_id`, `description`, `status`.

Event statuses: `draft`, `published`, `cancelled`, `postponed`, `completed`.

### Tasks
- [x] Define canonical event schema.
- [x] Define masjid schema.
- [x] Define speaker schema.
- [x] Define category schema.
- [x] Define settings schema.
- [x] Create sample data.
- [x] Document all fields (see `DATA_SCHEMA.md`).
- [x] Define required vs optional fields.
- [x] Define date/time format.
- [x] Define IDs.
- [x] Define status values.

### Acceptance
- [x] Sample JSON validates.
- [x] No duplicated canonical fields.
- [ ] Frontend can consume sample data (verified in Stage 3 when the public app is built).

---

# 6. Stage 2 — Data Validation Tool

Create `tools/validate_data.py`.

Detect: malformed JSON, missing required fields, invalid IDs, duplicate IDs, invalid dates, invalid times, invalid status, unknown masjid/speaker/category IDs, invalid recurring config, obviously invalid event ranges.

Command: `python tools/validate_data.py`

Exit codes: `0 = valid`, `non-zero = validation failure`.

### Acceptance
- [x] Valid sample data passes.
- [x] Intentionally broken data fails.
- [x] Useful error messages are produced.

---

# 7. Stage 3 — Public Application Skeleton

Create:
```
GET `public/index.html`, `public/events.html`, `public/event.html`, `public/masjid.html`
GET public/css/style.css
GET public/js/app.js, data.js, events.js, masjids.js, ui.js
   + public/assets/
```

Requirements: Vanilla JS only, no framework, responsive mobile-first, accessible/semantic HTML, keyboard navigation, reasonable contrast, no unnecessary animation.

Homepage displays: Today's events, Upcoming events, Popular/featured masjids, Quick filters.

### Acceptance
- [x] Website works locally (verified with a static server + headless Chrome).
- [ ] GitHub Pages verification pending live deployment.
- [x] No server required.

Note: public site consumes JSON from `public/data/`; the deploy workflow copies canonical `data/` into it automatically.

---

# 8. Stage 4 — Event Listing

Implement Today's/Tomorrow's/Upcoming events, event cards, event detail page, date/masjid/category filtering, empty-state messages, cancelled/postponed-event display.

### Acceptance
- [x] Correct events for current date.
- [x] Filters work.
- [x] Cancelled events clearly identified.
- [x] No console errors.

---

# 9. Stage 5 — Masjid Directory

Individual masjid pages use `masjid.html?id={masjid-id}`. Clean `/masjid/{masjid-id}` URL rewriting is deferred to static generation (Stage 11). Each masjid shows name, district, address, location (OpenStreetMap link), upcoming events, optional contact/website.

### Acceptance
- [x] Masjid list works.
- [x] Individual masjid page works.
- [x] Events correctly associated.

---

# 10. Stage 6 — Search and Filtering

Client-side search over title, description, masjid name, speaker name, category. Filters: masjid, district, category, date range, status. No server-side search engine.

### Acceptance
- [x] Search works on mobile.
- [x] Empty search result handled.
- [x] No API required.

---

# 11. Stage 7 — Event Sharing

Copy event URL, Web Share API (native), WhatsApp/Telegram share links, copy formatted event text, stable event URL. All client-side, no API keys.

### Acceptance
- [x] Event links shareable.
- [x] Shared URL identifies the event (stable `event.html?id=…`).
- [x] No private API required.

---

# 12. Stage 8 — Calendar Integration

Generate `.ics`. Include title, start, end, location, description, URL. Document Malaysia timezone handling.

### Acceptance
- [x] Generated `.ics` syntactically valid (RFC 5545 structure verified by tests).
- [x] Event date/time correct (TZID-anchored local times + UTC DTSTAMP).
- [x] Malaysia timezone handling documented (DATA_SCHEMA.md §9).

---

# 13. Stage 9 — Directions / Maps

Store latitude, longitude, address. No proprietary maps API. Provide configurable/open map links (OpenStreetMap / Waze / Google Maps link / Apple Maps). No embedded map (no Leaflet, no iframe) — minimal scope by design.

### Acceptance
- [x] User can navigate to masjid location (via external direction links).
- [x] No Google API key required.

---

# 14. Stage 10 — Recurring Events

Recurrence structure, e.g.:

```json
{
  "recurrence": {
    "type": "weekly",
    "days": ["thursday"]
  }
}
```

Weekly recurrence, optional end date, exception/cancellation support, correct occurrence generation, no duplicate occurrences.

### Acceptance
- [x] Recurring event appears correctly.
- [x] Individual occurrence can be cancelled if architecture supports exceptions.

---

# 15. Stage 11 — Static Site Generation / SEO

Python tooling generating static pages (event detail, masjid detail). Implement page titles, meta descriptions, canonical URLs, Open Graph, sitemap, robots.txt, structured data, meaningful HTML content.

### Acceptance
- [x] Generated pages contain useful HTML without JavaScript.
- [x] Sitemap generated.
- [x] Canonical URLs consistent.

---

# 16. Stage 12 — PWA

`manifest.webmanifest` + `sw.js`. Cache app shell, CSS, JS, recent data. Must NOT make stale event info misleading.

### Acceptance
- [x] Installable where supported.
- [x] Works with poor connectivity.
- [x] Cache invalidation documented.

---

# 17. Stage 13 — Admin UI

Only after the public app is stable. Create `admin/` (index, events, event-editor, masjids, speakers). Functionality: event list/create/edit/cancel/postpone/archive, manage masjids/speakers/categories, preview, validate before publishing.

First admin implementation may be a local/data-management tool. Do NOT invent insecure browser-side authentication.

### Acceptance
- [x] Admin UI is a local tool, never deployed to GitHub Pages.
- [x] Event list with filters (status, masjid, category, search).
- [x] Create / edit / cancel / postpone / archive / publish / delete events.
- [x] Manage masjids, speakers, categories (create / edit / delete, delete blocked when referenced).
- [x] Recurring events (weekly) with exceptions editable.
- [x] Preview public rendering before publishing.
- [x] Validate before publishing; every mutation validates with rollback on failure.
- [x] No insecure browser-side authentication invented.

---

# 18. Stage 14 — Google Sheets Adapter

Optional data source, implemented as an adapter (Importer -> Canonical JSON -> Validator -> Public site). Create `tools/import_google_sheet.py` or equivalent. Document sheet mappings, validate after import, report invalid rows, detect duplicate IDs, do not destroy existing data.

### Acceptance
- [x] Adapter shape: Google Sheets (published CSV) -> canonical JSON -> validator -> public site.
- [x] `tools/import_google_sheet.py` exists; no API key / secret required (published-to-web CSV export).
- [x] Sheet mappings documented (`SHEET_IMPORT.md` + `tools/sheets_import.example.json`).
- [x] Validates the merged data set before writing; failure leaves local data untouched.
- [x] Invalid rows reported with their sheet row number and skipped.
- [x] Duplicate IDs detected within a sheet (and across the merge), reported.
- [x] Existing data is never destroyed: only adds/updates by id, no pruning.

---

# 19. Stage 15 — GitHub Actions Automation

Workflows: `validate.yml` and `deploy.yml`. Validation on pull request, push to main, data changes. Broken data prevents deployment.

### Acceptance
- [x] `validate.yml` runs on pull request to main/master and on pushes touching data/tools/tests/public/admin/workflows.
- [x] Validation covers canonical data, all Python suites, all JS suites, JS syntax, and the public mirror being in sync.
- [x] `deploy.yml` validates canonical data before building; broken data blocks the deploy.

---

# 20. Stage 16 — QR Codes

Generate permanent QR codes for masjid URL and event URL. Point to stable URLs; never encode event details directly.

---

# 21. Stage 17 — Multi-Masjid Administration

Introduce organization/ownership concept (State -> District -> Masjid -> Editors -> Events). Establish data model first; do not implement complex multi-tenant auth until there is a real requirement.

---

# 22. Stage 18 — Federation / Multiple Data Sources

Allow multiple event feeds (JSON URL, Git repo, Google Sheets export, REST API) to be aggregated. All sources normalize into the canonical schema.

---

# 23. Stage 19 — Accessibility

Audit keyboard navigation, headings, labels, focus states, contrast, screen-reader labels, accessible button names, no color-only information.

---

# 24. Stage 20 — Performance

Target: small initial download, minimal JS, no unnecessary deps, compressed assets, lazy loading, no large frameworks. Measure HTML/CSS/JS/JSON/image sizes and request counts.

---

# 25. Stage 21 — Security Review

Audit: no secrets in repo/frontend, no unsafe HTML injection, escape user text, safe external links, no client-side admin credentials, minimized workflow permissions, review dependencies, no unnecessary third-party scripts. Update `SECURITY.md`.

---

# 26. Stage 22 — Documentation

README covers purpose, architecture, local development, data format, deployment, admin workflow, Google Sheets adapter, contributing, licensing. Document `DATA_SCHEMA.md`, `ADMIN_GUIDE.md`, `DEPLOYMENT.md` where useful.

---

# 27. Stage 23 — Production Readiness

Remove demo data, add real masjids, verify locations/times/timezone, test cancelled/recurring events, mobile/slow/no-JS, GitHub Pages, sharing links, QR codes, sitemap, no credentials exposed.

---

# 28. Final Acceptance Test

MVP-complete when all work: public homepage, today's events, upcoming events, search, masjid filtering, category filtering, event detail, masjid detail, share, calendar export, directions, cancelled events, recurring events, data validation, GitHub Pages deployment, mobile responsive, no backend/API key/framework.

### Mobile / tablet requirement

The public interface must be usable on phones and tablets (mobile-first). Minimum bar: viewport meta on every page; content readable without horizontal scrolling; interactive controls have adequate touch targets (≈44px); navigation/filters/cards reflow sensibly across phone, tablet, and desktop widths; prefers-reduced-motion respected.

---

# 29. Future Ideas — DO NOT IMPLEMENT YET

Android/iOS apps, Telegram bot, WhatsApp integration, email/browser notifications, RSS feeds, public API, statewide federation, event subscriptions, masjid dashboards, analytics, multilingual/Jawi support, offline-first enhancements. Do not implement unless explicitly requested.

---

# 30. Agent Operating Rule

At the end of every implementation session, update this file. For completed stages: `[x] Stage N — Name`. For incomplete stages: `[ ] Stage N — Name`. Do not mark a stage complete unless acceptance criteria pass.

Always report:

```text
Current stage:
Completed:
Tests:
Files changed:
Known issues:
Next stage:
```

---

# Session Report — 2026-08-09 (1)

```text
Current stage: Stage 0 (Repository Bootstrap)
Completed:
  - Stage 0: repo structure, docs (README, ARCHITECTURE, TODO_AGENT, LICENSE,
    CONTRIBUTING, SECURITY), .gitignore, GitHub Pages deploy workflow,
    placeholder public/index.html verified serving locally (HTTP 200).
  - Early local tool (user request): add-masjid form -> canonical JSON.
Tests:
  - Local static server served public/index.html (200).
  - tools/serve.py compile check (py_compile) passed.
  - API endpoints verified:
      GET  /admin/add-masjid.html           200
      GET  /index.html                     200
      GET  /api/data                       200
      POST /api/add-masjid valid           200 (masjid + schedule saved)
      POST /api/add-masjid bad date/time     400 + useful error
      POST /api/add-masjid unknown category 400 + useful error
      duplicate masjid names get unique ids (masjid-alwi, masjid-alwi-2)
      recurrence (weekly) accepted and stored
Files changed:
  - README.md, ARCHITECTURE.md, TODO_AGENT.md, LICENSE, CONTRIBUTING.md,
    SECURITY.md, .gitignore
  - .github/workflows/deploy.yml
  - public/index.html
  - data/{masjids,events,speakers,categories,settings}.json
  - tools/serve.py
  - admin/add-masjid.html
Known issues:
  - Live GitHub Pages deployment not yet verified (requires a remote repo).
  - data files currently empty (no real masjid entries yet).
Next stage: Stage 1 (Data Model) — finalize schemas + sample data; then
  Stage 2 (validation tool), Stage 3 (public app skeleton).
```

---

# Session Report — 2026-08-09 (2) — Stage 1

```text
Current stage: Stage 1 (Data Model)
Completed:
  - All schemas defined and documented in DATA_SCHEMA.md:
    event, masjid, speaker, category, settings, recurrence.
  - Sample data added to data/:
      events.json     8 events (published, cancelled, postponed,
                       recurring weekly, with/without speaker & category)
      masjids.json    3 masjids
      speakers.json   3 speakers
      categories.json 17 categories (unchanged from stage 0)
      settings.json   timezone, formats, statuses, recurrence meta
  - tools/serve.py updated to validate recurrence.start_date (schema parity).
Tests:
  - JSON parse + reference-integrity check on all data files: passes
    (no duplicate IDs, valid dates/times/statuses, masjid/speaker/category
    references all resolve).
Files changed:
  - data/masjids.json, data/events.json, data/speakers.json,
    data/settings.json, data/categories.json
  - DATA_SCHEMA.md (new)
  - tools/serve.py
  - TODO_AGENT.md
Known issues:
  - Standalone validator not built yet (that is Stage 2).
  - Frontend consumption not built yet (that is Stage 3).
Next stage: Stage 2 — Data Validation Tool (tools/validate_data.py).
```

---

# Session Report — 2026-08-09 (3) — Stage 2

```text
Current stage: Stage 2 (Data Validation Tool) — COMPLETE
Completed:
  - tools/validate_data.py validates all canonical data files
    (masjids, events, speakers, categories, settings).
  - Checks implemented: malformed JSON, missing required fields,
    invalid/duplicate/malformed IDs, invalid dates and times,
    invalid status, unknown masjid/speaker/category references,
    invalid recurrence config (type/days/start_date/end_date/range),
    end_time not later than start_time.
  - Exit-code contract: 0 = valid, 1 = validation failure, 2 = bad --data-dir.
  - tests/test_validate.py added (4 tests).
Tests:
  - python3 tools/validate_data.py            -> OK, exit 0
  - python3 tests/test_validate.py            -> 4/4 passed
  - Manual broken-data checks (bad dates/times/status/refs/dupes/recurrence)
    all reported useful messages + non-zero exit.
Files changed:
  - tools/validate_data.py (new)
  - tests/test_validate.py (new)
  - TODO_AGENT.md
Known issues:
  - None blocking. Validator matches DATA_SCHEMA.md; frontend consumption still
    pending (Stage 3).
Next stage: Stage 3 — Public Application Skeleton.
```

---

# Session Report — 2026-08-09 (4) — Stage 3

```text
Current stage: Stage 3 (Public Application Skeleton) — COMPLETE
Completed:
  - Public static site skeleton in public/:
      index.html, events.html, event.html, masjids.html, masjid.html
      css/style.css (mobile-first, accessible, reduced-motion aware)
      js/data.js (DataLoader abstraction), ui.js (safe DOM/escaping, KL-time
      formatting), events.js (filtering + recurrence + grouping), masjids.js
      (directory), app.js (per-page bootstrap + friendly error states)
  - Homepage: Today's events, Upcoming, Featured masjids.
  - events.html: tabs (Hari Ini / Esok / Minggu Ini / Akan Datang), filters
    (masjid/category/status), search box.
  - Cancelled/postponed events show status notices; drafts are hidden.
  - Deploy workflow syncs canonical data/ into public/data/ before upload.
Tests:
  - node --check for all JS files -> clean.
  - headless Chrome (desktop + 375px mobile) rendered every page without
    error-box except intentional "not found" states; no console errors.
  - tests/test_events.js (node) -> 12/12 passed (filtering, recurrence,
    upcoming bounds, visibilty).
  - python3 tests/test_validate.py -> 4/4 passed (unchanged).
Files changed:
  - public/{index,events,event,masjids,masjid}.html (new/replaced)
  - public/css/style.css (new)
  - public/js/{data,ui,events,masjids,app}.js (new)
  - public/data/*.json (copied from canonical data/)
  - .github/workflows/deploy.yml (sync data step)
  - tests/test_events.js (new)
  - README.md
Known issues:
  - Dispatcher uses client-side query params for detail pages; static/SEO
    generation comes later (Stage 11).
Next stage: Stage 4 — Event Listing polish (verify current-date correctness,
  cancelled/postponed display, filtering edge cases against live date).
```

---

# Session Report — 2026-08-09 (5) — Stage 4

```text
Current stage: Stage 4 (Event Listing) — COMPLETE
Completed:
  - Events page date-range filtering: "Dari"/"Hingga" date inputs (ids
    filter-from / filter-to). An explicit date range takes priority over the
    active tab; clearing both returns to tab behaviour.
  - Homepage now has an "Esok" (Tomorrow) section alongside "Hari Ini",
    "Akan Datang" and "Masjid Pilihan".
  - Event-card polish: adds speaker name (when present) to the meta line and
    always shows the status badge for cancelled AND postponed events; badge
    is placed at the top of the card.
  - Empty-state copy refined to guide users (suggests adjusting filters/tab).
  - Refactor: moved the previously local range-collection logic into the
    tested, shared ME.events.range(from, to, limit) in events.js (closed
    window -> distinct occurrences; open-ended -> bounded upcoming scan,
    capped at 2 years). app.js now calls ME.events.range.
  - Removed the leftover dead 'var setActiveTab' global in app.js.
Tests:
  - node --check on all public/js/*.js -> clean.
  - tests/test_events.js -> 25/25 passed (added: date-range filterEvents,
    status filters for cancelled/postponed, range() closed & open windows,
    status notice logic; added e6 recurring-Wed sample).
  - python3 tests/test_validate.py -> 4/4 passed.
  - python3 tools/validate_data.py -> OK (exit 0).
  - Headless Chrome: index/events/event/masjids/masjid pages have no
    error-box; homepage shows Hari Ini/Esok/Akan Datang/Masjid Pilihan;
    Hari Ini tab renders the correct 2 cards for sample data.
Files changed:
  - public/js/app.js (date filters, Esok section, ME.speakers lookup,
    ME.events.range usage, removed setActiveTab)
  - public/js/events.js (eventCard polish, statusBadge for cancelled+postponed,
    shared range(), refined empty-state)
  - public/js/data.js (unchanged)
  - tests/test_events.js (extended to 25 assertions, +e6)
  - TODO_AGENT.md
Known issues:
  - None blocking. Live GitHub Pages disabled by default for gh-pages branch;
    live deployment still pending (requires a remote repo + page config).
Next stage: Stage 5 — Masjid Directory (route by id, per-masjid listing +
  events) and then Stage 6 (Search & filtering refinements).
```

---

# Session Report — 2026-08-09 (6) — Stage 5

```text
Current stage: Stage 5 (Masjid Directory) — COMPLETE
Completed:
  - Masjid directory (masjids.html): grid of all masjids; cards now show the
    number of upcoming events per masjid ("N acara akan datang").
  - Masjid detail page (masjid.html?id={id}):
      * name, district/state, address
      * location link to OpenStreetMap (no-MAPS-API, static friendly)
      * optional "Hubungi" (tel:) and "Laman web" links when data present
      * "Hari Ini" section with that masjid's events for the current date
      * "Akan Datang" section filtered to that masjid, excluding today
      (avoids duplicating today's events)
      * friendly error state for unknown id
  - Masjid cards and detail page re-use tested ME.events helpers
    (occurrencesOn / upcoming with masjid filter / filterEvents).
  - Added tests/test_masjids.js (7 assertions: get/list/featured ordering,
    featured fallback & limit).
  - Clean /m/{id} static URLs intentionally deferred to Stage 11 (static
    generation). Current routing uses masjid.html?id= consistently
    (matching event.html?id=), which works with GitHub Pages without a
    server-side router/404 hack.
Tests:
  - node tests/test_masjids.js            -> 7/7 passed
  - node tests/test_events.js             -> 25/25 passed
  - python3 tests/test_validate.py        -> 4/4 passed
  - python3 tools/validate_data.py        -> OK (exit 0)
  - node --check on all public/js/*.js    -> clean
  - Headless Chrome: masjids.html shows 3 cards + upcoming counts;
    masjid.html?id=masjid-alwi renders Hari Ini + Akan Datang without
    duplicates and no error-box; OSM location link present; 375px mobile
    check clean; unknown id shows the error state.
Files changed:
  - public/js/masjids.js (masjidCard upcoming-count, renderGrid counts param)
  - public/js/app.js (renderMasjidsPage counts, renderMasjidPage enrichment)
  - public/css/style.css (.masjid-events, .masjid-links, .btn-ghost)
  - tests/test_masjids.js (new)
  - TODO_AGENT.md
Known issues:
  - None blocking. Clean /m/{id} URLs remain a static-generation item (Stage 11).
Next stage: Stage 6 — Search and filtering refinements (client-side search
  over title/masjid/speaker, district filter, refined empty/result states).
```

---

# Session Report — 2026-08-09 (7) — Stage 6

```text
Current stage: Stage 6 (Search and Filtering) — COMPLETE
Completed:
  - Events page search now matches title, description, masjid name, speaker
    name, and category name (new shared ME.events.searchText helper).
  - Events page gained a district filter ("filter-district") alongside the
    existing masjid / category / status / date-range filters.
  - Masjid directory (masjids.html) gained its own live search box
    ("masjid-search") and district filter, powered by new ME.masjids helpers:
      * filterMasjids(q, { district })  — matches id/name/district/state/address
      * districts()                    — sorted distinct values for the dropdown
  - Directory grid now shows an empty state ("Tiada masjid ditemui…") when no
    masjid matches, mirroring the events empty-state.
  - ME.categories wiring added in app.js (alongside ME.speakers) so searchText
    can resolve category names on all pages.
Tests:
  - node tests/test_events.js  -> 30/30 (added: searchText across masjid/
    speaker/category; q match by masjid name; district filter)
  - node tests/test_masjids.js -> 12/12 (added: filterMasjids by name/id,
    district filter, no-match empty, districts() sorting)
  - python3 tests/test_validate.py -> 4/4 passed
  - python3 tools/validate_data.py -> OK (exit 0)
  - node --check on all public/js/*.js -> clean
  - Headless Chrome: events.html + masjids.html render with no error-box at
    desktop and 375px mobile; district options (Arau, Kangar) present on both
    pages; masjid cards + event cards render.
Files changed:
  - public/js/events.js (searchText helper + q uses it; export)
  - public/js/masjids.js (filterMasjids, districts, empty-state in renderGrid)
  - public/js/app.js (districtSel on events page + wiring; ME.categories;
    directory search/filter UI)
  - tests/test_events.js, tests/test_masjids.js (extended)
  - TODO_AGENT.md
Known issues:
  - None blocking. Search is exact substring on lowercased text (no
    diacritic/fuzzy matching) — acceptable for the current scale.
Next stage: Stage 7 — Event Sharing (copy URL, Web Share API, WhatsApp,
  Telegram, formatted event text, stable event URLs).
```

---

# Session Report — 2026-08-09 (8) — Stage 7

```text
Current stage: Stage 7 (Event Sharing) — COMPLETE
Completed:
  - New module public/js/share.js with pure, testable helpers:
      * ME.share.textSummary(ev) — plain-text event summary (Masjid, date,
        time, speaker, description, cancelled/postponed note)
      * ME.share.eventUrl(id) — stable absolute URL to event.html?id=…
      * ME.share.whatsappUrl(text) / telegramUrl(text, url) — no-key share links
      * ME.share.copyText(text) — clipboard API with execCommand fallback
      * ME.share.nativeShare(payload) — Web Share API wrapper
  - Event detail page gains a Share bar:
      * "Salin pautan" (copy event URL)
      * "Salin teks acara" (copy summary + URL)
      * "Kongsi WhatsApp" / "Kongsi Telegram" (prefilled share links)
      * "Kongsi melalui apl lain" (native Web Share, graceful fallback msg)
  - Copy/status buttons give brief inline feedback then revert.
  - CSS (.share bar) added; share.js loaded on event.html before app.js.
Tests:
  - node tests/test_share.js -> 12/12 (summary content/notes, stable URL,
    wa.me/t.me URL shapes & encoding)
  - node tests/test_events.js / test_masjids.js unchanged -> 30/30, 12/12
  - python3 tests/test_validate.py -> 4/4; tools/validate_data.py -> OK
  - node --check all public/js/*.js -> clean
  - Headless Chrome: event detail renders all 5 share controls with correct
    wa.me + t.me links, no error-box; cancelled event shows its notice;
    desktop + mobile clean; all site pages no error-box.
Files changed:
  - public/js/share.js (new)
  - public/js/app.js (share bar in renderEventPage)
  - public/event.html (load share.js)
  - public/css/style.css (.share)
  - tests/test_share.js (new)
  - TODO_AGENT.md
Known issues:
  - None blocking. Clipboard + native share require a secure origin (https)
    or localhost; on plain http on another host the fallback paths apply.
Next stage: Stage 8 — Calendar Integration (generate .ics, Malaysia timezone).
```

---

# Session Report — 2026-08-09 (9) — Stage 8

```text
Current stage: Stage 8 (Calendar Integration) — COMPLETE
Completed:
  - New module public/js/ics.js — RFC 5545 single-event .ics generator:
      * ME.ics.eventToIcs(ev, opts) returns a full VCALENDAR document
      * Malaysia handling: DTSTART/DTEND use TZID=Asia/Kuala_Lumpur +
        X-WR-TIMEZONE; DTSTAMP and recurrence UNTIL are UTC (Z). Malaysia
        has no DST so the fixed-offset approach is unambiguous.
      * Includes title, location (masjid name + address), description,
        speaker, status mapping (published->CONFIRMED, cancelled->CANCELLED,
        postponed->TENTATIVE), stable UID (id@masjidperlis.org), DTSTAMP.
      * Recurring events emit RRULE:FREQ=WEEKLY;BYDAY=… (+ UNTIL when an
        end date is set). Missing end_time defaults DTEND to start_time.
      * Emphasis escape per RFC 5545 (backslash/comma/semicolon/newline).
      * ME.ics.downloadIcs(ev) triggers a Blob download named <id>.ics.
      * Rate-fix: DTSTAMP double-Z bug caught via sample output dump and
        fixed (toISOString already includes Z).
  - Event detail page: "Tambah ke kalendar (.ics)" button with inline
    feedback, reusing the button row styling (.share).
  - DATA_SCHEMA.md section 9 documents Malaysia timezone handling and the
    ICS conventions.
Tests:
  - node tests/test_ics.js -> 21/21 (calendar structure, timestamps,
    status mapping, escaping, end-time default, RRULE + UNTIL)
  - Full suite unchanged: events 30/30, masjids 12/12, share 12/12,
    validate 4/4; tools/validate_data.py -> OK
  - node --check all public/js/*.js -> clean
  - Headless Chrome: event pages (published/recurring/cancelled) render the
    .ics button with no error-box; all site pages clean.
Files changed:
  - public/js/ics.js (new)
  - public/js/app.js (.ics button in renderEventPage)
  - public/event.html (load ics.js)
  - tests/test_ics.js (new)
  - DATA_SCHEMA.md (§9 timezone handling)
  - TODO_AGENT.md
Known issues:
  - None blocking. .ics filenames use the stable event id.
Next stage: Stage 9 — Directions / Maps (OpenStreetMap links for masjids;
  already partially present via location links on the masjid page).
```

---

# Session Report — 2026-08-09 (10) — Stage 9

```text
Current stage: Stage 9 (Directions / Maps) — COMPLETE (minimal scope)
Completed:
  - New module public/js/maps.js — zero-key, plain URL builders only:
      * osmUrl(lat, lon)   -> openstreetmap.org map link
      * wazeUrl(lat, lon)  -> waze.com/ul navigate link
      * googleUrl(lat, lon)-> google.com/maps/dir keyless directions link
      * appleUrl(lat, lon) -> maps.apple.com point link
      * buttons(lat, lon)  -> ordered [{label, href}] list for the UI
  - Masjid detail page: the previous single OpenStreetMap link is now a
    compact "Arah / Peta" button group (OpenStreetMap, Waze, Google Maps,
    Apple Maps), first button styled primary, rest ghost.
  - No map SDK, no Leaflet, no iframe, no API keys — merges directly into
    the existing .masjid-links row.
Tests:
  - node tests/test_maps.js -> 9/9 (URL schemes, coordinates embedded,
    keyless google link, 4 providers, stable order, distinct https refs)
  - Full suite: events 30/30, masjids 12/12, share 12/12, ics 21/21,
    validate 4/4; tools/validate_data.py -> OK
  - node --check all public/js/*.js -> clean
  - Headless Chrome: masjid page shows all 4 direction buttons with
    correct links, no error-box; all site pages clean.
Files changed:
  - public/js/maps.js (new)
  - public/js/app.js (direction button group in renderMasjidPage)
  - public/masjid.html (load maps.js)
  - tests/test_maps.js (new)
  - TODO_AGENT.md
Known issues:
  - None blocking. External links open in new tab (rel=noopener).
    Offline fallback is the stored address text shown on the page.
Next stage: Stage 10 — Recurring Events (recurrence structure, exceptions,
  no duplicate occurrences). Much of the occurrence-generation logic and
  RRULE export already exists; Stage 10 will finalise exceptions + tests.
```

# Session Report — 2026-08-10 (11) — Stage 10

```text
Current stage: Stage 10 (Recurring Events) — COMPLETE
Completed:
  - Added recurrence.exceptions support: individual occurrences of a
    recurring event can be cancelled by listing their date in the
    recurrence's "exceptions" array (e.g. ["2026-08-19"]).
  - public/js/events.js:
      * isRecurringOccurrenceOn(event, dateStr) now skips exception dates
        (case-insensitive weekday match unaffected; built on exact date hit).
      * New exported helper isExceptionDate(event, dateStr) — true only when
        the event has recurrence.exceptions containing dateStr.
      * isExceptionDate safely returns false for events without a recurrence
        key (no undefined-recurrence crash).
  - DATA_SCHEMA.md: documented the recurrence.exceptions field (list of ISO
    dates, optional, must be valid and not duplicate the base date).
  - tools/validate_data.py: _check_recurrence now validates "exceptions"
    (must be a list if present, each entry a valid YYYY-MM-DD date, no
    duplicates, any date allowed — occurrence cancellation is legitimate).
  - tools/serve.py: equivalent "$validateRecurrence" parity guard.
  - data/events.json: recurring sample evt-20260812-001 (Wednesdays, base
    2026-08-12) now carries "exceptions": ["2026-08-19"].
  - public/data mirror re-synced (cp data/*.json public/data/).
Tests:
  - tests/test_events.js extended -> 37/37: exception date omits occurrence,
    normal Wednesday retained, base date retained, isExceptionDate true/false
    + non-recurring false, upcoming() never surfaces an exception occurrence.
  - tests/test_validate.py extended -> 6/6: bad exceptions (invalid date,
    duplicates) fail with messages; valid exceptions pass.
  - Full suite: masjids 12/12, share 12/12, ics 21/21, maps 9/9; validator on
    real data -> OK.
  - node --check all public/js/*.js -> clean.
  - Headless Chrome sweep: all 5 public pages render with zero error-box;
    recurring event page (evt-20260812-001) fine.
Files changed:
  - public/js/events.js
  - public/data/events.json (mirror re-synced)
  - tools/validate_data.py
  - tools/serve.py
  - DATA_SCHEMA.md
  - data/events.json
  - tests/test_events.js
  - tests/test_validate.py
  - TODO_AGENT.md
Known issues:
  - None blocking. The event detail page still shows the event's base date
    (no per-occurrence date parameter), so exception cancellations currently
    affect list/occurrence generation only. Per-date event URLs are deferred
    to Stage 11 (static site generation), which can later add an
    occurrence-cancelled notice.
Next stage: Stage 11 — Static Site Generation / SEO (clean /m/{id} URLs,
  meta/canonical/OG, sitemap, robots.txt, structured data).
```

---

# Session Report — 2026-08-10 (12) — Stage 11

```text
Current stage: Stage 11 (Static Site Generation / SEO)
Completed: Stage 11 acceptance criteria all pass.
Tests:
  - New tests/test_build_site.py -> 10/10: expected files generated (event
    pages + event.ics per event, masjid pages), draft events excluded,
    event page HTML has useful no-JS content (title/masjid/date/speaker),
    canonical/OG/JSON-LD present, ../../ asset base prefix, static WA/Telegram
    + .ics links, cancelled page carries "dibatalkan" + EventCancelled schema
    + STATUS:CANCELLED in .ics, masjid page has jsonld Place + OpenStreetMap +
    upcoming list with clean event URLs, recurring exception 2026-08-19 never
    surfaced on masjid page, sitemap loc count gives home+3 top pages+8
    events+3 masjids, canonical == sitemap locs, top-level head injection is
    idempotent (single <!-- build-site-seo --> block), invalid data fails the
    build with exit 1, empty --site-url falls back to root-relative canonicals
    and omits the Sitemap line from robots.txt.
  - Existing suite unchanged and green: validate 6/6, events 37/37, masjids
    12/12, share 12/12, ics 21/21, maps 9/9; validator on real data -> OK;
    node --check all public/js/*.js -> clean; deploy.yml parses as valid YAML.
  - Headless Chrome: 8 generated pages + masjid pages + patched index.html /
    events.html / masjids.html render with zero error-box; titles correct
    (e.g. "Kuliyyah Maghrib: Keutamaan Ilmu — Masjid Events Perlis", cancelled
    title retained); SPA fallback event.html?id=... still renders Penceramah
    with no errors; <link rel="canonical"> renders as injected.
Files changed:
  - tools/build_site.py (new): static generator — event/{id}/index.html (+
    event.ics, RFC 5545 TZID Asia/Kuala_Lumpur), masjid/{id}/index.html
    (jsonld Place + OpenStreetMap + "Akan Datang" list de-duplicated by event
    id, honoring recurrence exceptions), sitemap.xml, robots.txt, canonical/
    OG injection into existing top-level pages via idempotent
    <!-- build-site-seo --> markers; Python recurrence/ICS mirror the JS;
    --out/--today/--site-url/--data-dir args; validates data first (exit 1 on
    invalid).
  - .github/workflows/deploy.yml: added configure-pages id + "Build static
    SEO pages" step running tools/build_site.py prior to the artifact upload.
  - public/js/events.js, masjids.js, share.js, app.js: internal links switched
    from event.html?id= / masjid.html?id= to the clean /event/{id}/ and
    /masjid/{id}/ URLs; share.eventUrl now targets the canonical page.
  - tests/test_build_site.py (new): 10 tests as listed above.
  - tests/test_share.js: eventUrl assertion updated to clean-URL form.
  - TODO_AGENT.md: acceptance checked, this report appended.
Known issues:
  - --site-url currently empty in data/settings.json, so a local run of
    build_site.py (without the arg) emits root-relative canonicals and skips
    the Sitemap line; the deploy workflow passes the proper Pages base_url.
  - Generated pages already in repo are not committed; generation happens at
    deploy time and on demand via tools/build_site.py.
Next stage: Stage 12 — PWA (manifest.webmanifest + sw.js; cache the app shell,
  CSS, JS, recent data; document cache invalidation so stale event info is
  never misleading).
```
---

# Session Report — 2026-08-10 (13) — Stage 12 (PWA) + Mobile polish

```text
Current stage: Stage 12 (PWA) — complete; plus mobile/tablet polish.
Completed:
  - Mobile/tablet requirement made explicit in Final Acceptance Test (viewport
    meta everywhere, no horizontal scroll, ~44px touch targets, reflow across
    widths, prefers-reduced-motion). Touch targets raised in style.css:
    .site-nav a, .btn, .tabs button, .filters select/input to 44px min-height
    with larger padding; .share .btn keeps ~44px via padding top/bottom.
  - PWA manifest: public/manifest.webmanifest (name/short_name ms, standalone,
    theme #0f6b3a, bg #f4f6f8, icons 192/512 + maskable).
  - Icons: tools/gen_icons.py — pure-stdlib (zlib+struct) PNG encoder drawing
    accent-green rounded tile with white crescent + five-pointed star at
    192x192 and 512x512; supersampled edges. Committed under public/assets/.
  - Service worker: build_site.py emits sw.js with CACHE_VERSION stamp
    (--version, default KL timestamp; deploy passes github.sha). Strategy:
    shell assets stale-while-revalidate in versioned SHELL_CACHE; data/*.json
    and navigations NETWORK-FIRST (cache is only offline fallback) so
    cancellations/postponements are never stale online; old caches deleted on
    activate; skipWaiting + clients.claim; sub-path-safe path matching.
  - Registration: js/app.js registers sw.js on https only (progressive
    enhancement); generated no-JS pages carry a tiny guarded inline
    registration snippet (their only script). manifest.webmanifest +
    theme-color added to all 5 SPA templates and generated page <head>.
  - deploy.yml: added "Generate PWA icons" step and "Build static SEO pages +
    service worker" step (now passes --site-url AND --version github.sha).
  - ARCHITECTURE.md #34 updated: cache strategy + invalidation documented.
Tests:
  - tests/test_build_site.py -> 14/14 (added: sw.js generated + version
    stamped + network-first/navigate patterns + cache cleanup, generated pages
    carry manifest link + theme-color + inline SW registration, manifest
    fields valid, icons are valid 8-bit RGBA PNGs of correct size).
  - Existing suites all green: validate 6/6, events 37/37, masjids 12/12,
    share 12/12, ics 21/21, maps 9/9; node --check all public/js/*.js clean;
    node --check generated sw.js clean; deploy.yml valid YAML.
  - Headless Chrome: index/events/masjids + generated event/masjid pages
    render with zero errors; event.html?id=... renders detail with no error;
    event.html without id shows the intended "tidak ditemui" error-box.
Files changed:
  - public/manifest.webmanifest (new)
  - public/assets/icon-192.png, icon-512.png (new, generated)
  - tools/gen_icons.py (new)
  - tools/build_site.py (sw.js generation, manifest/theme-color in generated
    head, inline SW registration on generated pages, --version arg)
  - public/js/app.js (SW registration)
  - public/index.html, events.html, masjids.html, event.html, masjid.html
    (manifest + theme-color links)
  - public/css/style.css (touch targets)
  - .github/workflows/deploy.yml (gen_icons + versioned build steps)
  - ARCHITECTURE.md (#34 cache strategy + invalidation)
  - tests/test_build_site.py (3 new tests)
  - TODO_AGENT.md (Stage 12 acceptance checked, this report appended)
Known issues:
  - None blocking. SW only registers over https (localhost dev stays
    cache-free). Offline fallback for unvisited pages degrades to the cached
    home shell; data pages show a browser error if never cached before going
    offline. Rendered mobile layout is deterministic from the mobile-first
    CSS; a device lab check is worthwhile at final acceptance.
Next stage: Stage 13 — Admin UI (local/data-management tool first; do NOT
  invent insecure browser-side authentication).
```

---

# Session Report — 2026-08-10 (14) — Stage 13 (Admin UI)

```text
Current stage: Stage 13 (Admin UI) — complete (local/data-management tool).
Completed:
  - tools/serve.py rewritten into a local admin server (NOT the public site):
      * --data-dir / --public-data / --port args; seeds an empty data dir
        with a valid settings.json (event_statuses, recurrence_types,
        weekdays allow-lists, site metadata).
      * Canonical CRUD API: POST/PUT/DELETE /api/{events,masjids,speakers,
        categories}; POST /api/events/{id}/status (draft/published/cancelled/
        postponed/completed); GET /api/data; POST /api/validate; POST
        /api/publish (mirrors data -> public/data after validation); POST
        /api/preview (renders public event/masjid pages via build_site);
        legacy POST /api/add-masjid (masjid + schedule batch) kept working.
      * Every mutation writes, then runs validate_directory and rolls back to
        a byte snapshot on any failure; referential integrity enforced
        (delete blocked while referenced; unknown ids rejected).
  - New admin/ pages (shared admin.css + admin.js): index (stats, validate,
    publish, quick links), events (list + status/masjid/category/search
    filters + publish/postpone/cancel/archive/delete actions), event-editor
    (create/edit incl. weekly recurrence + exceptions + live preview iframe),
    masjids, speakers, categories (list + create/edit forms). Legacy
    add-masjid.html retained.
  - No authentication layer added (tool binds 127.0.0.1, dev-only, per the
    "do NOT invent insecure browser-side authentication" rule).
Tests:
  - tests/test_admin.py (new) -> 6/6: CRUD for masjid/speaker/category with
    referenced-delete blocking; event lifecycle + status transitions +
    invalid-update rollback; weekly recurrence save + exceptions + event
    preview (200) and unknown-id preview (404); validation rollback incl.
    add-masjid batch rollback; publish mirrors all data files; all admin
    pages served. Runs serve.py on an ephemeral port against a throwaway
    data dir so real data/ is untouched.
  - Existing suites still green: validate 6/6, events 37/37, masjids 12/12,
    share 12/12, ics 21/21, maps 9/9.
  - node --check admin/admin.js + all inline admin scripts -> clean.
  - Real data dir boots serve.py cleanly: /api/validate -> ok: True.
Files changed:
  - tools/serve.py (rewritten: args, DataStore, CRUD/status/preview/publish,
    rollback, settings seeding)
  - admin/admin.css, admin/admin.js (new shared shell)
  - admin/index.html, events.html, event-editor.html, masjids.html,
    speakers.html, categories.html (new)
  - admin/add-masjid.html (unchanged; still wired to /api/add-masjid)
  - tests/test_admin.py (new)
  - TODO_AGENT.md (Stage 13 acceptance checked, this report appended)
Known issues:
  - None blocking. No browser-side auth by design; tool binds loopback only.
Next stage: Stage 14 — Google Sheets Adapter (Importer -> Canonical JSON ->
  Validator -> Public site; document mappings, validate after import, detect
  duplicate IDs, never destroy existing data).
```

---

# Session Report — 2026-08-10 (15) — Stage 14 (Google Sheets Adapter)

```text
Current stage: Stage 14 (Google Sheets Adapter) — complete.
Completed:
  - tools/import_google_sheet.py: optional data-source adapter. Reads
    published-to-web Google Sheets CSV exports (tab via gid) OR local CSV
    files, normalizes rows into canonical JSON, merges into data/, then runs
    the full validator on the merged set BEFORE writing.
      * No API key / secret: uses the public CSV export URL
        (.../export?format=csv&gid=GID); sheets only need File > Share >
        Publish to web.
      * Column mappings per source ("columns": header -> canonical field);
        without them headers must equal canonical names. id_column optional;
        ids are derived stably when absent (masjid/speaker/category from
        name, event from date -> evt-{date}-{NNN}), never renumbered.
      * Reference cells (masjid/speaker/category) accept an id OR the current
        display name, resolved against the merged data.
      * Add/update by id only; local records not in the sheet are kept (no
        pruning). Duplicate ids within a sheet detected, later rows skipped.
      * Invalid rows are reported with their sheet row number and skipped.
      * On any merged-data validation failure the importer ABORTS and leaves
        data/ byte-for-byte untouched. --dry-run validates only; --strict
        aborts if any row was skipped; --spreadsheet-id/--config/--data-dir
        overrides. Events support recurrence via rolled-up columns
        (recurrence_type/days/start/end/exceptions).
  - tools/sheets_import.example.json: full documented mapping (4 tabs, Malay
    headers as in the example archive the repo ships).
  - SHEET_IMPORT.md: guarantees, publish-to-web steps, config/source options,
    per-tab column tables, CLI usage and exit codes.
Tests:
  - tests/test_import_sheet.py -> 4/4: happy add+update+keep+skip (new
    masjid/speaker/category/event with generated ids, existing event updated,
    existing records preserved, invalid date + unknown reference rows
    skipped); duplicate explicit id + strict abort leaves files unchanged;
    validation failure (patched validator) aborts without writing; --dry-run
    modifies nothing. Runs against a throwaway copy of data/, never touches
    the real data/.
  - Existing suites still green: admin 6/6, validate 6/6,
    build_site 14/14, JS events 37/37, masjids 12/12, share 12/12,
    ics 21/21, maps 9/9; tools/validate_data.py -> OK on data/.
Files changed:
  - tools/import_google_sheet.py (new)
  - tools/sheets_import.example.json (new)
  - SHEET_IMPORT.md (new)
  - tests/test_import_sheet.py (new)
  - TODO_AGENT.md (Stage 14 acceptance checked, this report appended)
Known issues:
  - None blocking. Requires the source spreadsheet to be publicly shared /
    published; that is by design (no secrets). Names in reference cells
    resolve to the id of the first match; keep display names unique.
Next stage: Stage 15 — GitHub Actions Automation (`validate.yml` + deploy
  hardening; validation on PR/push/data changes, broken data blocks deploy).
```

---

# Session Report — 2026-08-10 (16) — Stage 15 (GitHub Actions Automation)

```text
Current stage: Stage 15 (GitHub Actions Automation) — complete.
Completed:
  - .github/workflows/validate.yml (new): runs on pull_request to main/master
    and on push (paths: data/, public/js + SPA templates + css/, tools/,
    tests/, admin/, .github/workflows/). Steps: validate canonical data;
    run the four Python suites (validate, build_site, admin, import_sheet);
    run all five Node suites (events, masjids, share, ics, maps); node --check
    every public/js/*.js plus admin/admin.js; verify public/data/ mirror is
    byte-equal to data/ (reports a helpful message when out of sync).
  - .github/workflows/deploy.yml: added a "Validate canonical data (broken
    data blocks deployment)" step that runs tools/validate_data.py before the
    data sync and build steps, so invalid data fails the build job and cannot
    be published.
Tests:
  - Both YAML workflow files parsed with PyYAML (schema/keys/jobs sanity).
  - Every command the workflows run was executed locally (all green): full
    Python + JS suites, validate_data OK on data/, node --check clean,
    mirror-in-sync check passes.
  - Remaining suites unchanged and green: admin 6/6, import_sheet 4/4,
    validate 6/6, build_site 14/14, events 37/37, masjids 12/12,
    share 12/12, ics 21/21, maps 9/9.
Files changed:
  - .github/workflows/validate.yml (new)
  - .github/workflows/deploy.yml (validation gate step)
  - TODO_AGENT.md (Stage 15 acceptance checked, this report appended)
Known issues:
  - None blocking. The validate job is read-only (contents: read); live
    GitHub-run verification requires a push/PR on GitHub.
Next stage: Stage 16 — QR Codes (permanent QR codes for masjid and event
  URLs; point at stable URLs, never encode event details directly).
```
