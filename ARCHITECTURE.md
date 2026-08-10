# ARCHITECTURE.md

# Masjid Events Perlis

## 1. Purpose

Masjid Events Perlis is a lightweight, open-source web platform for publishing events and religious programs conducted by masjids.

The primary goal is to provide a stable public information source independent of social-media platforms.

The system should make it possible for a visitor to answer:

> "What is happening at masjids around Perlis today or this week?"

without requiring:

* Facebook
* Instagram
* Telegram
* WhatsApp
* account registration
* mobile application
* proprietary software

---

# 2. Architectural Philosophy

The architecture follows these principles:

```text
Simple
   |
   +-- Static whenever possible
   |
   +-- Open formats
   |
   +-- Minimal dependencies
   |
   +-- Vendor neutral
   |
   +-- Mobile first
   |
   +-- Secure by default
   |
   +-- Easy to fork
   |
   +-- Easy to deploy
```

The public application is intentionally boring.

That is a feature.

# 3. High-Level Architecture

```text
                         DATA SOURCES
                              |
              +---------------+---------------+
              |               |               |
             JSON            CSV        Google Sheets
              |               |               |
              +---------------+---------------+
                              |
                              v
                    +-------------------+
                    | Data Adapters     |
                    | / Importers       |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Canonical Data    |
                    | Model             |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Validation        |
                    | + Normalization   |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Static Data       |
                    | JSON              |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Build / Generator |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | GitHub Repository |
                    +---------+---------+
                              |
                       GitHub Actions
                              |
                              v
                    +-------------------+
                    | GitHub Pages      |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Public Web App    |
                    +-------------------+
```

# 4. Two Application Model

The system consists of two logical applications:

```text
                    MASJID EVENTS
                         |
              +----------+----------+
              |                     |
              v                     v
       ADMIN / DATA             PUBLIC
       MANAGEMENT               WEBSITE
              |                     |
              |                     |
            WRITE                 READ ONLY
              |                     |
              v                     v
       Data source             Static JSON
       / importer                  |
                                  v
                            GitHub Pages
```

1. **Public application** — completely read-only, static, mobile-first, no login, no database, deployable to GitHub Pages.
2. **Administration/data-management application** — used by authorized editors to create/update/cancel events. Initially may use Google Sheets as a convenient data-entry source, but Google must NOT become a fundamental architectural dependency.

# 5. Public Application

## 5.1 Characteristics

The public application MUST be:

* read-only
* static
* mobile-first
* responsive
* lightweight
* accessible
* cacheable
* deployable to GitHub Pages

It should not require a backend.

## 5.2 Public Architecture

```text
Browser
  |
  +-- index.html
  |
  +-- CSS
  |
  +-- Vanilla JS
  |
  +-- JSON
       |
       +-- events.json
       +-- masjids.json
       +-- speakers.json
       +-- categories.json
       +-- districts.json
       +-- editors.json
```

The browser performs local filtering/search against the downloaded dataset.

# 6. Public Data Flow

```text
Source
  |
  v
Importer
  |
  v
Validation
  |
  v
Normalization
  |
  v
data/*.json
  |
  v
Build
  |
  v
GitHub Pages
  |
  v
Browser
```

The public browser must never need direct access to administrative credentials.

# 7. Admin Architecture

The admin system is deliberately separated from the public application.

```text
                 ADMIN
                   |
                   v
           +---------------+
           | Admin UI      |
           +-------+-------+
                   |
                   v
           Data management
                   |
                   v
           Data adapter
                   |
          +--------+--------+
          |                 |
       JSON/CSV        Google Sheets
          |                 |
          +--------+--------+
                   |
                   v
             Normalization
                   |
                   v
              Validation
                   |
                   v
               Build
```

The first admin implementation may be a local/data-management tool rather than a publicly exposed authenticated backend.

Do not invent insecure browser-side authentication.

# 8. Why Google Sheets Is an Adapter

Google Sheets is useful because many masjid committees are already comfortable with spreadsheets.

However:

```text
Google Sheets != Core Architecture
```

Instead:

```text
                  Canonical Data Model
                         ^
                         |
              +----------+----------+
              |          |          |
             JSON       CSV      Sheets
```

This allows the project to replace Google Sheets later.

Possible future adapters:

```text
JSON
CSV
Google Sheets
Git repository
REST API
SQLite
PostgreSQL
```

The frontend should not care which adapter produced the data.

# 9. Repository Structure

Recommended structure:

```text
masjid-events/
|
+-- README.md
+-- ARCHITECTURE.md
+-- TODO_AGENT.md
+-- LICENSE
+-- CONTRIBUTING.md
+-- SECURITY.md
|
+-- public/
|   |
|   +-- index.html
|   |
|   +-- css/
|   |   +-- style.css
|   |
|   +-- js/
|   |
|   +-- assets/
|
+-- data/
|
+-- admin/
|
+-- tools/
|
+-- tests/
|
+-- .github/
    |
    +-- workflows/
```

Detailed public/admin file listings are covered in the individual stages.

# 10. Canonical Data Model

The canonical model is the contract between all components.

## 10.1 Event

```json
{
  "id": "evt-20260812-001",
  "title": "Kuliyyah Maghrib",
  "masjid_id": "masjid-alwi",
  "date": "2026-08-12",
  "start_time": "20:00",
  "end_time": "21:00",
  "speaker_id": "speaker-ahmad",
  "category_id": "kuliyyah",
  "description": "",
  "status": "published"
}
```

Required: `id`, `title`, `masjid_id`, `date`, `start_time`, `status`

Optional: `end_time`, `speaker_id`, `category_id`, `description`, `location`, `recurrence`

# 11. Event IDs

Event IDs must be:

* unique, stable
* URL-safe
* independent of display names

Use machine-readable, index-style IDs:

```text
evt-20260812-001
```

Do not use the event title as the primary identifier.

# 12. Masjid Model

```json
{
  "id": "masjid-alwi",
  "name": "Masjid Alwi",
  "district": "Kangar",
  "state": "Perlis",
  "address": "",
  "latitude": 6.44,
  "longitude": 100.20,
  "contact": "",
  "website": ""
}
```

The ID must remain stable even if the display name changes.

# 13. Speaker Model

```json
{
  "id": "speaker-ahmad",
  "name": "Ustaz Ahmad",
  "description": ""
}
```

Speaker data should be optional. An event must not fail simply because speaker information is unavailable.

# 14. Category Model

```json
{
  "id": "kuliyyah",
  "name": "Kuliyyah"
}
```

The category list should remain configurable.

# 15. Event Status

Supported states: `draft`, `published`, `cancelled`, `postponed`, `completed`.

Public behavior:

```text
draft      -> invisible
published  -> visible normally
cancelled  -> visible with cancellation warning
postponed  -> visible with postponement warning
completed  -> historical/archive behavior
```

# 16. Recurring Events

Recurring events use a recurrence structure rather than generating hundreds of independent records.

```json
{
  "recurrence": {
    "type": "weekly",
    "days": ["thursday"],
    "start_date": "2026-08-13",
    "end_date": null
  }
}
```

The implementation must avoid creating duplicate occurrences.

# 17. Date and Time

* Date: `YYYY-MM-DD`
* Time: `HH:MM` (24-hour)

The project operates primarily in Malaysia. Default timezone: `Asia/Kuala_Lumpur`.

Do not rely on the user's browser timezone to determine the event's actual local date.

# 18. URL Architecture

Stable URLs are important.

```text
/events/                    event listing
/e/{event-id}               event detail
/m/{masjid-id}              masjid detail
```

These URLs are intended to be printed, shared, and embedded in QR codes.

# 19. Event Sharing Architecture

Each event has a stable URL.

Sharing channels: Copy URL, Web Share, WhatsApp, Telegram, Copy formatted text.

The website remains the canonical source. Social media becomes a distribution channel rather than the database.

# 20. Calendar Architecture

Generate standard `.ics` (iCalendar). Required fields: `UID`, `DTSTART`, `DTEND`, `SUMMARY`, `DESCRIPTION`, `LOCATION`, `URL`. Use Malaysia timezone correctly.

# 21. Maps Architecture

Avoid mandatory proprietary mapping APIs. Store `latitude`, `longitude`, `address`. Provide configurable map/navigation links (OpenStreetMap/Leaflet or plain external links). Map functionality must remain optional.

# 22. Search Architecture

Initial search is client-side against the loaded JSON dataset. No search server is required for the initial deployment.

# 23. Static Site Generation

The application may generate static HTML pages from canonical data for SEO, stable URLs, fast load, and reduced JS dependency. The generator must remain optional until the basic frontend is stable.

# 24. GitHub Pages

Deployment: Developer/Admin -> Git repo -> GitHub Actions (validate/test/build) -> GitHub Pages. No runtime backend is required.

# 25. GitHub Actions

Push/PR -> validate JSON -> validate references -> run tests -> build -> deploy. A failed validation must prevent deployment.

# 26. Security Boundary

```text
                 PRIVATE / WRITE
                       |
                       v
                ADMIN / IMPORT
                       |
                       v
                 VALIDATION
                       |
                       v
                 PUBLIC / READ
                       |
                       v
                  GitHub Pages
```

Public users must never receive administrative credentials.

# 27. Secrets

Never store secrets in `public/`, `data/`, admin frontend, git repository, or generated HTML. Sensitive credentials belong in GitHub Actions Secrets or another secure server-side mechanism. If a feature requires a secret inside browser JavaScript, the architecture must be reconsidered.

# 28. XSS Protection

Event data can originate from external sources. Validation + escaping / safe DOM APIs must be used. Avoid `element.innerHTML = externalData`.

# 29. Dependency Strategy

Dependencies should be minimal. Before adding one, decide if vanilla JavaScript suffices, whether the library is maintained, whether the license is compatible, and whether it adds real value.

# 30. CSS Architecture

Use plain CSS with CSS variables. Avoid utility-class frameworks. Responsive/accessibility-friendly.

# 31. JavaScript Architecture

Use small modules with separated responsibilities:

```text
app.js, data.js, events.js, masjids.js, search.js, calendar.js, sharing.js, ui.js
```

Avoid a single 3,000-line `app.js`.

# 32. Data Loading

The public application loads data through a small `DataLoader` abstraction (events, masjids, speakers, categories). The UI must not know whether data came from JSON, CSV, Google Sheets, or an API.

# 33. Error Handling

The public site must gracefully handle missing/malformed JSON, empty lists, unknown references, cancellations, network failure, and stale caches. Never display raw JavaScript errors to users; use friendly messages.

# 34. Offline / PWA Architecture

The PWA (later stage) caches the app shell and recent data. The service worker must not permanently serve stale event data; use cache versioning and sensible refresh.

Service worker (`tools/build_site.py` emits `sw.js` into the site root):

- Shell assets (css/js/manifest/icons) are stale-while-revalidate in a
  versioned cache (`SHELL_CACHE`).
- `data/*.json` and page navigations are NETWORK-FIRST: online users always
  see the freshest schedule; the cached copy is only an offline fallback, so
  cancelled/postponed events are never shown as current.
- Cache invalidation: every deploy regenerates `sw.js` with a fresh
  `CACHE_VERSION` (git SHA). Old caches are deleted on activation.
  Icons are regenerated by `tools/gen_icons.py`; the PWA manifest is
  `public/manifest.webmanifest`.
- Registration happens in `js/app.js` (SPA pages) and via a tiny guarded
  inline snippet on generated no-JS pages, HTTPS only.

# 35. Accessibility

Follow practical WCAG: semantic HTML, labels, keyboard navigation, visible focus, accessible buttons, descriptive links, reasonable contrast, responsive text.

# 36. Mobile Architecture

Primary target is the mobile browser. Design order: Mobile -> Tablet -> Desktop.

# 37. Public UX

The homepage must answer quickly: What is happening today? Where? When? Who is speaking? Avoid clutter.

# 38. Masjid UX

A masjid page shows name, location, directions, today, this week, and all upcoming events. Permanent masjid URLs allow QR codes and printed materials.

# 39. QR Code Architecture

QR codes point to stable URLs (`https://example.org/m/masjid-alwi`), never encode event details directly.

# 40. Federation Architecture

Future: a public aggregator consuming feeds (Perlis, Kedah, Penang) in canonical schema.

# 41. Future API

If required later, expose the canonical model via static JSON, REST API, RSS, mobile app, or Telegram bot — not a new data format.

# 42. Deployment Environments

Minimum: Local, GitHub, GitHub Pages. Optional later: Preview, Production. Do not create staging infrastructure for the MVP.

# 43. Testing Strategy

* **Data**: JSON schema, reference integrity, dates, times, statuses, IDs
* **JavaScript**: date/event filtering, recurrence, calendar, search
* **UI**: manual verification mobile/desktop/keyboard/empty states
* **Deployment**: GitHub Pages URLs, assets, JSON loading, HTTPS

# 44. Performance Goals

Small HTML/CSS/JS/JSON, few requests, no large frameworks, no large icon packs. Performance is an architectural property.

# 45. Privacy

The public application should collect as little personal information as possible. No user accounts, profiles, personal data, or tracking cookies in the MVP.

# 46. No Social-Network Dependency

Social media is allowed only as a sharing channel; the website remains the authoritative source.

# 47. Recommended Technology Stack

| Layer                | Technology                            |
| -------------------- | ------------------------------------- |
| Public HTML          | HTML5                                 |
| CSS                  | Vanilla CSS                           |
| JavaScript           | Vanilla JS                            |
| Data                 | JSON                                  |
| Data validation      | Python                                |
| Build                | Python                                |
| Hosting              | GitHub Pages                          |
| CI/CD                | GitHub Actions                        |
| Optional spreadsheet | Google Sheets                         |
| Maps         | OpenStreetMap / configurable provider |
| Calendar             | iCalendar `.ics`                     |
| PWA                  | Web Manifest + Service Worker         |

# 48. What NOT to Build

Do not introduce these without explicit approval: React, Vue, Angular, Next.js, Nuxt, Tailwind, Firebase, Supabase, PostgreSQL, MongoDB, Redis, Kubernetes, Docker, microservices, GraphQL, Elasticsearch, server-side authentication, complex RBAC, paid cloud services, Google Maps API, third-party analytics.

If in doubt, ask:

> Do we actually need it?

# 49. Architectural Evolution

```text
Static JSON Website -> GitHub Pages -> Google Sheets Adapter
-> Static Site Generator -> PWA -> Multiple Data Sources -> Federation -> Public API
```

# 50. Target End-State

The ideal end-state is an **open publishing system for masjid events**, not merely another website: multiple masjids managing their own events through a canonical schema consumed by website, mobile, and API.

# 51. Architectural Success Criteria

* A visitor can discover today's events quickly.
* No Facebook required.
* No account required.
* No backend.
* Runs entirely from GitHub Pages.
* Event data is portable.
* Google Sheets is optional.
* Masjids can eventually manage their own events.
* Event URLs are permanent and shareable.
* QR codes point to permanent masjid pages.
* The system can support multiple states.
* Another developer / community can fork and replace Google Sheets.
* Understandable without a large framework.
* Secrets never reach the public application.

# 52. Final Architectural Principle

```text
              DATA FIRST
                  |
                  v
          SIMPLE DATA MODEL
                  |
                  v
         VALIDATE EVERYTHING
                  |
                  v
           STATIC PUBLIC SITE
                  |
                  v
          ADD ADMIN FEATURES
                  |
                  v
          ADD AUTOMATION
                  |
                  v
          ADD FEDERATION
```

Never start with infrastructure. Start with the data model and the user experience. The public site should remain the simplest component of the entire system.