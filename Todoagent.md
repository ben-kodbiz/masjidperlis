Yes. I would make the coding agent **build this incrementally**, with each stage producing a runnable system before moving forward. The important constraint is: **do not let the agent jump straight into admin/auth/Google integration**. Establish the data model and public read-only site first.

Below are the two files.

### `TODO_AGENT.md`

# TODO_AGENT.md

# Masjid Events Perlis — Agent Build Plan

## 0. Project Mission

Build a lightweight, open-source web application for masjids in Perlis to publish:

* Kuliyyah
* Ceramah
* Tazkirah
* Tafsir
* Hadith lessons
* Fiqh lessons
* Religious programs
* Community programs
* Youth / children programs
* Special events
* Recurring weekly events

The system must reduce dependency on Facebook and other social-media platforms by providing a permanent, searchable, shareable public web presence for masjid events.

The project consists of two logical applications:

1. **Public application**

   * Completely read-only.
   * Mobile-first.
   * Static hosting.
   * No login.
   * No database.
   * Deployable to GitHub Pages.

2. **Administration/data-management application**

   * Used by authorized editors.
   * Creates/updates/cancels events.
   * Initially may use Google Sheets as a convenient data-entry source.
   * Google must NOT become a fundamental architectural dependency.
   * Must eventually support other data sources.

---

# 1. Non-Negotiable Design Principles

The coding agent MUST follow these principles.

## 1.1 Lightweight

Prefer:

* HTML5
* Vanilla CSS
* Vanilla JavaScript
* JSON
* Python for build/validation tooling
* GitHub Actions
* GitHub Pages

Avoid unless there is a compelling reason:

* React
* Vue
* Angular
* Next.js
* Nuxt
* Tailwind
* Bootstrap
* Node backend
* Express
* Firebase
* Supabase
* PostgreSQL
* MongoDB
* Docker

Do not introduce a framework simply because it is popular.

---

## 1.2 Public site must be static

The public application must NOT require:

* backend server
* database server
* login
* API key
* secret
* Google authentication
* Google Maps API
* proprietary cloud service

Public users should consume generated/static data.

Preferred model:

```text
events.json
masjids.json
speakers.json
categories.json
        |
        v
Public HTML + CSS + JavaScript
        |
        v
GitHub Pages
```

---

## 1.3 Data source must be replaceable

The application must not hard-code Google Sheets into the core frontend.

Use an adapter concept:

```text
Data Source
    |
    +-- JSON
    |
    +-- CSV
    |
    +-- Google Sheets
    |
    +-- Git repository
    |
    +-- Future API
```

All sources should eventually produce the same normalized data model.

---

## 1.4 Security

NEVER put secrets into:

```text
public/
frontend JavaScript
events.json
GitHub Pages
HTML
CSS
```

Never commit:

* API tokens
* GitHub tokens
* Google service-account credentials
* passwords
* private keys
* OAuth secrets

Use GitHub Actions secrets or another secure mechanism for future write/sync operations.

---

## 1.5 Open-source first

Prefer:

* open formats
* open standards
* open-source libraries
* simple data structures
* portable architecture
* no vendor lock-in

The project should remain useful if Google disappears from the architecture.

---

# 2. Development Rules for Coding Agent

The agent MUST work stage-by-stage.

For every stage:

1. Read `ARCHITECTURE.md`.
2. Inspect the existing repository.
3. Implement only the current stage.
4. Run validation/tests.
5. Fix errors.
6. Update documentation.
7. Mark the stage complete in this file.
8. Do not silently implement future-stage functionality.
9. Keep commits logically separable when possible.

Before modifying existing functionality:

```text
inspect -> understand -> modify -> test
```

Do not rewrite working modules unnecessarily.

---

# 3. Definition of Done

A stage is NOT complete merely because code exists.

A stage is complete only when:

* [ ] Code implemented
* [ ] Existing functionality still works
* [ ] Validation passes
* [ ] No obvious console errors
* [ ] Mobile layout checked
* [ ] Documentation updated
* [ ] No secrets introduced
* [ ] Checklist updated
* [ ] Git diff reviewed

---

# 4. Stage 0 — Repository Bootstrap

## Objective

Create the initial repository structure and project documentation.

### Tasks

* [ ] Create project directory structure.
* [ ] Create `README.md`.
* [ ] Create `ARCHITECTURE.md`.
* [ ] Create `TODO_AGENT.md`.
* [ ] Create `LICENSE`.
* [ ] Create `CONTRIBUTING.md`.
* [ ] Create `SECURITY.md`.
* [ ] Create `.gitignore`.
* [ ] Create initial GitHub Pages deployment workflow.
* [ ] Verify repository can deploy a basic page.

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

* [ ] GitHub Pages successfully serves the initial site.
* [ ] No backend is required.

---

# 5. Stage 1 — Data Model

## Objective

Define the canonical data format before building UI.

Create:

```text
data/
├── events.json
├── masjids.json
├── speakers.json
├── categories.json
└── settings.json
```

---

## 5.1 Event schema

Minimum event fields:

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

### Event statuses

```text
draft
published
cancelled
postponed
completed
```

### Tasks

* [ ] Define canonical event schema.
* [ ] Define masjid schema.
* [ ] Define speaker schema.
* [ ] Define category schema.
* [ ] Define settings schema.
* [ ] Create sample data.
* [ ] Document all fields.
* [ ] Define required vs optional fields.
* [ ] Define date/time format.
* [ ] Define IDs.
* [ ] Define status values.

### Acceptance

* [ ] Sample JSON validates.
* [ ] No duplicated canonical fields.
* [ ] Frontend can consume sample data.

---

# 6. Stage 2 — Data Validation Tool

## Objective

Prevent bad data from reaching the public website.

Use Python.

Create:

```text
tools/
└── validate_data.py
```

Validation should detect:

* [ ] malformed JSON
* [ ] missing required fields
* [ ] invalid IDs
* [ ] duplicate IDs
* [ ] invalid dates
* [ ] invalid times
* [ ] invalid status
* [ ] unknown masjid IDs
* [ ] unknown speaker IDs
* [ ] unknown category IDs
* [ ] invalid recurring-event configuration
* [ ] obviously invalid event ranges

Command:

```bash
python tools/validate_data.py
```

Exit codes:

```text
0 = valid
non-zero = validation failure
```

### Acceptance

* [ ] Valid sample data passes.
* [ ] Intentionally broken data fails.
* [ ] Useful error messages are produced.

---

# 7. Stage 3 — Public Application Skeleton

## Objective

Build the read-only public application.

Create:

```text
public/
├── index.html
├── events.html
├── event.html
├── masjid.html
├── css/
│   └── style.css
├── js/
│   ├── app.js
│   ├── data.js
│   ├── events.js
│   ├── masjids.js
│   └── ui.js
└── assets/
```

### Requirements

* [ ] Vanilla JavaScript only.
* [ ] No frontend framework.
* [ ] Responsive layout.
* [ ] Mobile-first.
* [ ] Accessible HTML.
* [ ] Semantic HTML.
* [ ] Keyboard navigation.
* [ ] Reasonable contrast.
* [ ] No unnecessary animation.

### Homepage

Display:

```text
Today's events
Upcoming events
Popular/featured masjids
Quick filters
```

### Acceptance

* [ ] Website works locally.
* [ ] Website works from GitHub Pages.
* [ ] No server required.

---

# 8. Stage 4 — Event Listing

## Objective

Make events useful to ordinary visitors.

Implement:

* [ ] Today's events.
* [ ] Tomorrow's events.
* [ ] Upcoming events.
* [ ] Event cards.
* [ ] Event detail page.
* [ ] Date filtering.
* [ ] Masjid filtering.
* [ ] Category filtering.
* [ ] Empty-state messages.
* [ ] Cancelled-event display.
* [ ] Postponed-event display.

Example:

```text
TODAY

🕌 Masjid Alwi
Kuliyyah Maghrib

8:00 PM
Ustaz Ahmad

[View Event]
```

### Acceptance

* [ ] Correct events appear for current date.
* [ ] Filters work.
* [ ] Cancelled events are clearly identified.
* [ ] No console errors.

---

# 9. Stage 5 — Masjid Directory

## Objective

Allow users to discover participating masjids.

Create:

```text
/masjids/
```

Each masjid should display:

* [ ] name
* [ ] mukim
* [ ] address
* [ ] location
* [ ] upcoming events
* [ ] optional contact
* [ ] optional website

URL model:

```text
/m/masjid-alwi
```

### Acceptance

* [ ] Masjid list works.
* [ ] Individual masjid page works.
* [ ] Events are correctly associated.

---

# 10. Stage 6 — Search and Filtering

Implement client-side search.

Search:

* [ ] event title
* [ ] masjid name
* [ ] speaker name
* [ ] category

Filters:

```text
Masjid
Mukim
Category
Date
Status
```

Do not introduce Elasticsearch or another server search engine.

The initial dataset should be small enough for client-side search.

### Acceptance

* [ ] Search works on mobile.
* [ ] Search is fast.
* [ ] Empty search result is handled.
* [ ] Search does not require an API.

---

# 11. Stage 7 — Event Sharing

## Objective

Make the website useful as an alternative source of truth to social media.

Implement:

* [ ] Copy event URL.
* [ ] Web Share API where supported.
* [ ] WhatsApp share.
* [ ] Telegram share.
* [ ] Copy formatted event text.
* [ ] Stable event URL.

Example:

```text
Kuliyyah Maghrib

🕌 Masjid Alwi
📅 12 August 2026
⏰ 8:00 PM
🎙️ Ustaz Ahmad

https://example.org/e/evt-20260812-001
```

### Acceptance

* [ ] Event links are shareable.
* [ ] Shared URL identifies the event.
* [ ] No private API is required.

---

# 12. Stage 8 — Calendar Integration

Implement `.ics` generation.

Each event should provide:

```text
[ Add to Calendar ]
```

Support standard iCalendar format.

Include:

* [ ] title
* [ ] start
* [ ] end
* [ ] location
* [ ] description
* [ ] URL

### Acceptance

* [ ] Generated `.ics` is syntactically valid.
* [ ] Event date/time is correct.
* [ ] Malaysia timezone handling is documented.

---

# 13. Stage 9 — Directions / Maps

Do NOT introduce a proprietary maps API.

Store:

```text
latitude
longitude
address
```

Provide:

```text
[ Directions ]
```

Use configurable/open map links.

Potential implementation:

```text
OpenStreetMap
Leaflet
external navigation URL
```

Do not make Leaflet mandatory if a simple external map link is sufficient for MVP.

### Acceptance

* [ ] User can navigate to masjid location.
* [ ] No Google API key required.

---

# 14. Stage 10 — Recurring Events

Support recurring masjid programs.

Examples:

```text
Every Thursday
Every Friday
Every Sunday
Every weekday
```

Do not require administrators to manually create 52 copies of the same event.

Define a recurrence structure.

Example concept:

```json
{
  "recurrence": {
    "type": "weekly",
    "days": ["thursday"]
  }
}
```

### Requirements

* [ ] Weekly recurrence.
* [ ] Optional end date.
* [ ] Exception/cancellation support.
* [ ] Correct occurrence generation.
* [ ] Avoid duplicate occurrences.

### Acceptance

* [ ] Recurring event appears correctly.
* [ ] Individual occurrence can be cancelled if architecture supports exceptions.

---

# 15. Stage 11 — Static Site Generation / SEO

## Objective

Improve discoverability through search engines.

Create Python tooling capable of generating static pages where practical.

Potential output:

```text
events/
├── evt-001/
│   └── index.html
├── evt-002/
│   └── index.html
```

and:

```text
m/
├── masjid-alwi/
│   └── index.html
```

Implement:

* [ ] page titles
* [ ] meta descriptions
* [ ] canonical URLs
* [ ] Open Graph metadata
* [ ] sitemap
* [ ] robots.txt
* [ ] structured data where appropriate
* [ ] meaningful HTML content

Do not sacrifice simplicity for SEO.

### Acceptance

* [ ] Generated pages contain useful HTML without requiring JavaScript.
* [ ] Sitemap generated.
* [ ] Canonical URLs consistent.

---

# 16. Stage 12 — PWA

Implement optional PWA support.

Create:

```text
manifest.webmanifest
sw.js
```

Cache:

* [ ] application shell
* [ ] CSS
* [ ] JS
* [ ] recent data

The PWA must NOT make stale event information misleading.

Cancelled/updated events must eventually refresh.

### Acceptance

* [ ] Application can be installed where supported.
* [ ] Previously loaded content can work with poor connectivity.
* [ ] Cache invalidation is documented.

---

# 17. Stage 13 — Admin UI

Only begin this stage after the public application is stable.

Create:

```text
admin/
├── index.html
├── events.html
├── event-editor.html
├── masjids.html
├── speakers.html
├── css/
│   └── admin.css
└── js/
    ├── admin.js
    ├── events.js
    ├── editor.js
    └── validation.js
```

Admin functionality:

* [ ] Event list.
* [ ] Create event.
* [ ] Edit event.
* [ ] Cancel event.
* [ ] Postpone event.
* [ ] Delete/archive event.
* [ ] Manage masjids.
* [ ] Manage speakers.
* [ ] Manage categories.
* [ ] Preview event.
* [ ] Validate before publishing.

Important:

The first admin implementation may be a local/data-management tool rather than a publicly exposed authenticated backend.

Do NOT invent insecure browser-side authentication.

---

# 18. Stage 14 — Google Sheets Adapter

Google Sheets is an optional data source.

Implement it as an adapter.

Architecture:

```text
Google Sheet
     |
     v
Importer
     |
     v
Canonical JSON
     |
     v
Validator
     |
     v
Public site
```

Do not let the frontend directly depend on spreadsheet layout.

Create:

```text
tools/
└── import_google_sheet.py
```

or equivalent modular adapter.

### Requirements

* [ ] Sheet-to-event mapping documented.
* [ ] Sheet-to-masjid mapping documented.
* [ ] Validation after import.
* [ ] Invalid rows reported.
* [ ] Duplicate IDs detected.
* [ ] Import does not silently destroy valid existing data.

### Acceptance

* [ ] Sample spreadsheet imports correctly.
* [ ] Invalid spreadsheet data produces actionable errors.

---

# 19. Stage 15 — GitHub Actions Automation

Create workflows for:

```text
Pull request
     |
     v
Validate
     |
     v
Build
     |
     v
Test
     |
     v
Deploy
```

At minimum:

```text
.github/workflows/
├── validate.yml
└── deploy.yml
```

Validation should run on:

* [ ] pull request
* [ ] push to main
* [ ] data changes

### Acceptance

* [ ] Broken data prevents deployment.
* [ ] Successful validation allows deployment.
* [ ] Deployment is reproducible.

---

# 20. Stage 16 — QR Codes

Generate permanent QR codes for:

```text
masjid URL
event URL
```

Example:

```text
/m/masjid-alwi
```

QR codes should point to stable URLs.

Do not encode event details directly into the QR code.

### Acceptance

* [ ] QR destination remains stable.
* [ ] Masjid QR can be printed and reused.

---

# 21. Stage 17 — Multi-Masjid Administration

Introduce the concept of organization ownership.

Potential model:

```text
State
  |
Mukim
  |
Masjid
  |
Editors
  |
Events
```

Do not implement complex multi-tenant authentication until there is an actual requirement.

First establish the data model.

---

# 22. Stage 18 — Federation / Multiple Data Sources

Future architecture:

```text
             Public Aggregator
                    |
       +------------+------------+
       |            |            |
    Perlis       Kedah        Penang
      JSON         JSON          JSON
       |            |            |
    Masjids      Masjids       Masjids
```

Allow multiple event feeds to be aggregated.

Possible sources:

```text
JSON URL
Git repository
Google Sheets export
REST API
```

All sources MUST normalize into the canonical event schema.

---

# 23. Stage 19 — Accessibility

Audit:

* [ ] keyboard navigation
* [ ] semantic headings
* [ ] form labels
* [ ] focus states
* [ ] color contrast
* [ ] screen-reader labels
* [ ] buttons have accessible names
* [ ] no information conveyed only through color

Do not assume users are technically sophisticated.

---

# 24. Stage 20 — Performance

Target:

* very small initial download
* minimal JavaScript
* no unnecessary dependencies
* compressed assets
* lazy loading where appropriate
* no large frameworks

Measure:

```text
HTML size
CSS size
JS size
JSON size
image size
number of requests
```

Do not optimize prematurely, but avoid obvious bloat.

---

# 25. Stage 21 — Security Review

Audit:

* [ ] no secrets in repository
* [ ] no secrets in frontend
* [ ] no unsafe HTML injection
* [ ] user-controlled text escaped
* [ ] external links handled safely
* [ ] admin credentials not stored client-side
* [ ] GitHub Actions permissions minimized
* [ ] dependency versions reviewed
* [ ] workflow permissions minimized
* [ ] no unnecessary third-party scripts

Create/update:

```text
SECURITY.md
```

---

# 26. Stage 22 — Documentation

README must explain:

* [ ] project purpose
* [ ] architecture
* [ ] local development
* [ ] data format
* [ ] deployment
* [ ] admin workflow
* [ ] Google Sheets adapter
* [ ] contributing
* [ ] licensing

Also document:

```text
DATA_SCHEMA.md
ADMIN_GUIDE.md
DEPLOYMENT.md
```

where useful.

---

# 27. Stage 23 — Production Readiness

Before first real deployment:

* [ ] Remove demo data.
* [ ] Add real participating masjids.
* [ ] Verify all locations.
* [ ] Verify event times.
* [ ] Verify timezone handling.
* [ ] Test cancelled events.
* [ ] Test recurring events.
* [ ] Test mobile devices.
* [ ] Test slow connection.
* [ ] Test no-JavaScript fallback where applicable.
* [ ] Verify GitHub Pages deployment.
* [ ] Verify sharing links.
* [ ] Verify QR codes.
* [ ] Verify sitemap.
* [ ] Verify no credentials exposed.

---

# 28. Final Acceptance Test

The project is considered MVP-complete when all of the following work:

```text
[ ] Public homepage
[ ] Today's events
[ ] Upcoming events
[ ] Search
[ ] Masjid filtering
[ ] Category filtering
[ ] Event detail
[ ] Masjid detail
[ ] Share event
[ ] Calendar export
[ ] Directions
[ ] Cancelled event
[ ] Recurring event
[ ] Data validation
[ ] GitHub Pages deployment
[ ] Mobile responsive
[ ] No backend required for public site
[ ] No API key required for public site
[ ] No proprietary frontend framework
```

---

# 29. Future Ideas — DO NOT IMPLEMENT YET

Keep these as future possibilities only:

* [ ] Android application
* [ ] iOS application
* [ ] Telegram bot
* [ ] WhatsApp integration
* [ ] email notifications
* [ ] browser notifications
* [ ] RSS feeds
* [ ] public API
* [ ] statewide event federation
* [ ] event subscriptions
* [ ] masjid dashboards
* [ ] analytics
* [ ] multilingual support
* [ ] Jawi support
* [ ] offline-first enhancements

Do not implement these unless explicitly requested.

---

# 30. Agent Operating Rule

At the end of every implementation session, update this file.

For completed stages:

```text
[x] Stage N — Name
```

For incomplete stages:

```text
[ ] Stage N — Name
```

Do not mark a stage complete unless its acceptance criteria pass.

The agent must always report:

```text
Current stage:
Completed:
Tests:
Files changed:
Known issues:
Next stage:
```

Never skip directly from an early stage to a late-stage feature without explicit instruction.

---

### `ARCHITECTURE.md`

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

---

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

---

# 4. Two Application Model

The system consists of two logical applications.

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

---

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

---

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
```

The browser performs local filtering/search against the downloaded dataset.

---

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

---

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

The exact administrative authentication architecture may evolve.

Do not implement insecure browser-only authentication.

---

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

---

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
+-- DATA_SCHEMA.md
+-- ADMIN_GUIDE.md
+-- DEPLOYMENT.md
|
+-- public/
|   |
|   +-- index.html
|   +-- events.html
|   +-- event.html
|   +-- masjids.html
|   +-- masjid.html
|   |
|   +-- css/
|   |   +-- style.css
|   |
|   +-- js/
|   |   +-- app.js
|   |   +-- data.js
|   |   +-- events.js
|   |   +-- masjids.js
|   |   +-- search.js
|   |   +-- calendar.js
|   |   +-- sharing.js
|   |   +-- ui.js
|   |
|   +-- assets/
|   |
|   +-- manifest.webmanifest
|   +-- sw.js
|
+-- data/
|   |
|   +-- events.json
|   +-- masjids.json
|   +-- speakers.json
|   +-- categories.json
|   +-- settings.json
|
+-- admin/
|   |
|   +-- index.html
|   +-- events.html
|   +-- event-editor.html
|   +-- masjids.html
|   +-- speakers.html
|   |
|   +-- css/
|   |   +-- admin.css
|   |
|   +-- js/
|       +-- admin.js
|       +-- events.js
|       +-- editor.js
|       +-- validation.js
|
+-- tools/
|   |
|   +-- validate_data.py
|   +-- generate_site.py
|   +-- import_csv.py
|   +-- import_google_sheet.py
|   |
+-- tests/
|
+-- .github/
    |
    +-- workflows/
        +-- validate.yml
        +-- deploy.yml
```

---

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

Required:

```text
id
title
masjid_id
date
start_time
status
```

Optional:

```text
end_time
speaker_id
category_id
description
location
recurrence
```

---

# 11. Event IDs

Event IDs must be:

* unique
* stable
* URL-safe
* independent of display names

Example:

```text
evt-20260812-001
```

Do not use the event title as the primary identifier.

Bad:

```text
kuliyyah-maghrib
```

Better:

```text
evt-20260812-001
```

---

# 12. Masjid Model

Example:

```json
{
  "id": "masjid-alwi",
  "name": "Masjid Alwi",
  "mukim": "Kangar",
  "state": "Perlis",
  "address": "",
  "latitude": 6.44,
  "longitude": 100.20,
  "contact": "",
  "website": ""
}
```

The ID must remain stable even if the display name changes.

---

# 13. Speaker Model

Example:

```json
{
  "id": "speaker-ahmad",
  "name": "Ustaz Ahmad",
  "description": ""
}
```

Speaker data should be optional.

An event must not fail simply because speaker information is unavailable.

---

# 14. Category Model

Example:

```json
{
  "id": "kuliyyah",
  "name": "Kuliyyah"
}
```

Suggested initial categories:

```text
kuliyyah
ceramah
tafsir
hadith
fiqh
akidah
sirah
tazkirah
khutbah
program
seminar
youth
children
women
ramadan
community
other
```

The category list should remain configurable.

---

# 15. Event Status

Supported states:

```text
draft
published
cancelled
postponed
completed
```

Public behavior:

```text
draft
   -> invisible

published
   -> visible normally

cancelled
   -> visible with cancellation warning

postponed
   -> visible with postponement warning

completed
   -> historical/archive behavior
```

---

# 16. Recurring Events

Recurring events should eventually use a recurrence structure rather than generating hundreds of independent records.

Example:

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

Recurring event support should remain independent from the main event UI.

---

# 17. Date and Time

All event data should use machine-readable values.

Date:

```text
YYYY-MM-DD
```

Time:

```text
HH:MM
```

Example:

```text
2026-08-12
20:00
```

The project operates primarily in Malaysia.

Default timezone:

```text
Asia/Kuala_Lumpur
```

Do not rely on the user's browser timezone to determine the event's actual local date.

---

# 18. URL Architecture

Stable URLs are important.

Recommended:

```text
/events/
```

```text
/e/{event-id}
```

Example:

```text
/e/evt-20260812-001
```

Masjid:

```text
/m/{masjid-id}
```

Example:

```text
/m/masjid-alwi
```

These URLs are intended to be printed, shared and embedded in QR codes.

---

# 19. Event Sharing Architecture

Each event has a stable URL.

Sharing flow:

```text
Event page
    |
    +-- Copy URL
    |
    +-- Web Share
    |
    +-- WhatsApp
    |
    +-- Telegram
    |
    +-- Copy formatted text
```

The website remains the canonical source.

Social media becomes a distribution channel rather than the database.

---

# 20. Calendar Architecture

Generate standard `.ics`.

Example conceptual flow:

```text
Event
 |
 v
Calendar generator
 |
 v
VEVENT
 |
 v
.ics
```

Required fields:

```text
UID
DTSTART
DTEND
SUMMARY
DESCRIPTION
LOCATION
URL
```

Use Malaysia timezone correctly.

---

# 21. Maps Architecture

Avoid mandatory proprietary mapping APIs.

Store:

```text
latitude
longitude
address
```

The application can provide configurable map/navigation links.

Possible implementation:

```text
OpenStreetMap
Leaflet
external navigation URL
```

Map functionality must remain optional.

The event system must work without maps.

---

# 22. Search Architecture

Initial search is client-side.

```text
events.json
     |
     v
Browser memory
     |
     +-- title
     +-- masjid
     +-- speaker
     +-- category
```

No search server is required for the initial deployment.

If the dataset becomes very large, search can later be optimized.

Do not prematurely introduce Elasticsearch or similar infrastructure.

---

# 23. Static Site Generation

The application may generate static HTML pages from canonical data.

Example:

```text
data/events.json
       |
       v
generate_site.py
       |
       +-- events/
       |    +-- evt-001/
       |    |    +-- index.html
       |    |
       |    +-- evt-002/
       |
       +-- m/
            +-- masjid-alwi/
                 +-- index.html
```

Benefits:

* SEO
* stable URLs
* fast initial load
* less JavaScript dependency
* good sharing behavior

The generator must remain optional until the basic SPA/static frontend is stable.

---

# 24. GitHub Pages

GitHub Pages hosts the public application.

Deployment:

```text
Developer/Admin
      |
      v
Git repository
      |
      v
GitHub Actions
      |
      +-- validate
      +-- test
      +-- build
      |
      v
GitHub Pages
```

No runtime backend is required.

---

# 25. GitHub Actions

Validation pipeline:

```text
Push / Pull Request
        |
        v
Validate JSON
        |
        v
Validate references
        |
        v
Run tests
        |
        v
Build
        |
        v
Deploy
```

A failed validation must prevent deployment.

---

# 26. Security Boundary

The most important security boundary is:

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

---

# 27. Secrets

Never store secrets in:

```text
public/
data/
admin frontend
Git repository
generated HTML
```

Sensitive credentials belong in:

```text
GitHub Actions Secrets
```

or another secure server-side mechanism.

If a feature requires a secret inside browser JavaScript, the architecture must be reconsidered.

---

# 28. XSS Protection

Event data can eventually originate from external sources.

Therefore:

```text
External Data
     |
     v
Validation
     |
     v
Escaping / safe DOM APIs
     |
     v
HTML
```

Avoid blindly using:

```javascript
element.innerHTML = externalData;
```

Prefer safe DOM operations or explicitly sanitized content.

---

# 29. Dependency Strategy

Dependencies should be minimal.

Before adding a dependency, ask:

1. Can vanilla JavaScript solve it?
2. Can a small standalone library solve it?
3. Is the dependency actively maintained?
4. Is the license compatible?
5. Does it materially improve the application?
6. Does it introduce a build system?
7. Does it increase security risk?

Avoid dependency accumulation.

---

# 30. CSS Architecture

Use plain CSS.

Suggested:

```text
style.css
 |
 +-- reset/base
 +-- typography
 +-- layout
 +-- navigation
 +-- cards
 +-- events
 +-- filters
 +-- forms
 +-- responsive
 +-- accessibility
```

Avoid utility-class frameworks.

Use CSS variables for project-wide values.

---

# 31. JavaScript Architecture

Use small modules.

Example:

```text
app.js
 |
 +-- data.js
 |
 +-- events.js
 |
 +-- masjids.js
 |
 +-- search.js
 |
 +-- calendar.js
 |
 +-- sharing.js
 |
 +-- ui.js
```

Responsibilities must remain separated.

Avoid a single 3,000-line `app.js`.

---

# 32. Data Loading

The public application should load data through a small abstraction.

Concept:

```text
DataLoader
    |
    +-- events
    +-- masjids
    +-- speakers
    +-- categories
```

The UI should not know whether data came from:

```text
JSON
CSV
Google Sheets
API
```

The build process should normally produce stable JSON.

---

# 33. Error Handling

Public site must gracefully handle:

* missing JSON
* malformed JSON
* empty event list
* unknown masjid
* unknown speaker
* cancelled event
* unavailable optional field
* network failure
* stale cached data

Never display raw JavaScript errors to users.

Use friendly messages.

Example:

```text
We're having trouble loading the latest events.

Please try again later.
```

---

# 34. Offline / PWA Architecture

Future PWA:

```text
Browser
   |
Service Worker
   |
   +-- app shell cache
   +-- static assets
   +-- recent event data
```

The service worker must not permanently serve stale event data.

Use cache versioning and sensible refresh behavior.

---

# 35. Accessibility

The public site should follow practical WCAG principles.

Use:

* semantic HTML
* labels
* keyboard navigation
* visible focus
* accessible buttons
* descriptive links
* reasonable contrast
* responsive text

Do not make accessibility an afterthought.

---

# 36. Mobile Architecture

Primary target:

```text
Mobile browser
```

Design order:

```text
Mobile
   |
   v
Tablet
   |
   v
Desktop
```

Not:

```text
Desktop
   |
   v
Shrink everything
   |
   v
Mobile
```

The main event card must be readable quickly on a phone.

---

# 37. Public UX

The homepage should answer quickly:

```text
What is happening today?
Where?
When?
Who is speaking?
```

Suggested homepage:

```text
MASJID EVENTS PERLIS

[ Today ] [ Tomorrow ] [ This Week ]

--------------------------------

TONIGHT

🕌 Masjid Alwi

Kuliyyah Maghrib
8:00 PM
Ustaz Ahmad

[Details] [Share]

--------------------------------

UPCOMING

...
```

Avoid clutter.

---

# 38. Masjid UX

A masjid page:

```text
Masjid Alwi
Kangar, Perlis

[Directions]

TODAY
...

THIS WEEK
...

ALL UPCOMING EVENTS
...
```

A permanent masjid URL allows QR codes and printed materials.

---

# 39. QR Code Architecture

QR codes should point to URLs.

Good:

```text
https://example.org/m/masjid-alwi
```

Bad:

```text
QR contains complete event data
```

This allows event information to change without reprinting the QR code.

---

# 40. Federation Architecture

Future system:

```text
                    PUBLIC AGGREGATOR
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
          Perlis        Kedah         Penang
          feed           feed           feed
             |             |             |
             v             v             v
          Masjids       Masjids       Masjids
```

Each feed should conform to the canonical schema.

This creates an open publishing protocol rather than a closed centralized database.

---

# 41. Future API

If an API is eventually required:

```text
Canonical Data
      |
      +-- Static JSON
      |
      +-- REST API
      |
      +-- RSS
      |
      +-- Mobile app
      |
      +-- Telegram bot
```

The API should expose the canonical model rather than inventing another data format.

---

# 42. Deployment Environments

Minimum:

```text
Local
  |
GitHub
  |
GitHub Pages
```

Optional later:

```text
Preview
Production
```

Do not create staging infrastructure unnecessarily for the MVP.

---

# 43. Testing Strategy

Testing should occur at several levels.

## Data

```text
JSON schema
Reference integrity
Dates
Times
Statuses
IDs
```

## JavaScript

Test important functions:

```text
date filtering
event filtering
recurrence
calendar generation
search
```

## UI

Manually verify:

```text
mobile
desktop
keyboard
empty states
cancelled events
```

## Deployment

Verify:

```text
GitHub Pages
URLs
assets
JSON loading
HTTPS
```

---

# 44. Performance Goals

The application should prioritize:

```text
small HTML
small CSS
small JS
small JSON
few requests
no large frameworks
```

Avoid:

```text
large UI libraries
large icon packs
large background images
unnecessary fonts
analytics scripts
third-party trackers
```

Performance should be treated as an architectural property.

---

# 45. Privacy

The public application should collect as little personal information as possible.

MVP should not require:

* user accounts
* visitor profiles
* personal data
* tracking cookies

Analytics, if ever added, should be optional and privacy-conscious.

---

# 46. No Social Network Dependency

Social media is allowed as a sharing channel.

It must NOT be the authoritative data source.

Correct:

```text
Masjid Event Database
       |
       +---- Website
       |
       +---- WhatsApp share
       |
       +---- Telegram share
       |
       +---- Facebook share
```

Incorrect:

```text
Facebook
   |
   v
Application database
```

The website should remain useful even if every social platform disappears.

---

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
| Maps                 | OpenStreetMap / configurable provider |
| Map UI               | Leaflet, optional                     |
| Calendar             | iCalendar `.ics`                      |
| PWA                  | Web Manifest + Service Worker         |
| Database             | None for MVP                          |
| Backend              | None for public MVP                   |

---

# 48. What NOT to Build

The coding agent must not introduce these without explicit approval:

```text
React
Vue
Angular
Next.js
Nuxt
Tailwind
Firebase
Supabase
PostgreSQL
MongoDB
Redis
Kubernetes
Docker
microservices
GraphQL
Elasticsearch
server-side authentication
complex RBAC
paid cloud services
Google Maps API
third-party analytics
```

A future requirement may justify one of these.

The default answer is:

> Do we actually need it?

---

# 49. Architectural Evolution

The system should evolve like this:

```text
                    MVP
                     |
                     v
             Static JSON Website
                     |
                     v
               GitHub Pages
                     |
                     v
             Google Sheets Adapter
                     |
                     v
             Static Site Generator
                     |
                     v
                    PWA
                     |
                     v
             Multiple Data Sources
                     |
                     v
                 Federation
                     |
                     v
               Public API
```

Do not reverse this by starting with a complex backend.

---

# 50. Target End-State

The ideal long-term architecture is:

```text
                       OPEN MASJID
                       EVENT DATA
                           |
            +--------------+--------------+
            |              |              |
            v              v              v
         Website         Mobile          API
            |              |              |
            +--------------+--------------+
                           |
                           v
                    Public event data
                           ^
                           |
                +----------+----------+
                |                     |
             Masjid A              Masjid B
                |                     |
             Admin                  Admin
                |                     |
                +----------+----------+
                           |
                           v
                    Canonical schema
```

The important idea is that the project becomes an **open publishing system for masjid events**, not merely another website.

---

# 51. Architectural Success Criteria

The architecture is successful when:

```text
[ ] A visitor can discover today's events quickly.

[ ] A visitor does not need Facebook.

[ ] A visitor does not need an account.

[ ] The public website requires no backend.

[ ] The public website can run entirely from GitHub Pages.

[ ] Event data is portable.

[ ] Google Sheets is optional rather than fundamental.

[ ] Masjids can eventually manage their own events.

[ ] Event URLs are permanent and shareable.

[ ] QR codes can point to permanent masjid pages.

[ ] The system can support multiple states.

[ ] Another developer can fork the project.

[ ] Another community can replace Google Sheets.

[ ] The project remains understandable without a large framework.

[ ] Secrets never reach the public application.
```

---

# 52. Final Architectural Principle

The system should follow this rule:

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

Never start with infrastructure.

Start with the data model and the user experience.

The public site should remain the simplest component in the entire system.

These two files deliberately keep the **MVP much smaller than the eventual vision**. Your coding agent should first get `data → validation → static public site → GitHub Pages` working. Only after that should it touch Google Sheets, admin workflows, recurring events, PWA, and federation. That will prevent this from turning into another over-engineered project.
