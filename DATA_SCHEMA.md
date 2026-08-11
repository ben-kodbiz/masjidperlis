# DATA_SCHEMA.md

# Masjid Events Perlis — Canonical Data Schema

This document defines the canonical data model. Every data source (JSON, CSV, Google Sheets, future API) must normalize into this model before it reaches the public site.

All master data files live in `data/`:

```text
data/
├── events.json
├── masjids.json
├── speakers.json
├── categories.json
├── mukims.json
├── editors.json
└── settings.json
```

## 1. Conventions

### Date and time

Dates use `YYYY-MM-DD` only. Times use 24-hour `HH:MM`.

```text
2026-08-12
20:00
```

All event dates and times are local to **Asia/Kuala_Lumpur**. Never infer the event's actual local date from the visitor's browser timezone.

### IDs

IDs must be:

* unique within their collection
* stable across time
* URL-safe (lowercase, letters, digits, hyphens)
* independent of display names

Examples:

```text
evt-20260812-001
masjid-alwi
speaker-ahmad
kuliyyah
```

Event IDs use the pattern `evt-{YYYYMMDD}-{NNN}`. Masjid/speaker IDs are slug-style. Do not use titles or display names as primary identifiers.

---

## 2. Event (`data/events.json`)

An array of event objects.

### Fields

| Field         | Type                  | Required | Notes                                         |
| ------------- | --------------------- | -------- | --------------------------------------------- |
| `id`          | string                | yes      | unique, stable, URL-safe                      |
| `title`       | string                | yes      | e.g. "Kuliyyah Maghrib"                       |
| `masjid_id`   | string                | yes      | must reference `masjids.json`                 |
| `date`        | string (`YYYY-MM-DD`) | yes      | local date                                    |
| `start_time`  | string (`HH:MM`)      | yes      | 24-hour local time                            |
| `status`      | string                | yes      | one of the statuses below                     |
| `end_time`    | string (`HH:MM`)      | no       | optional                                      |
| `speaker_id`  | string                | no       | references `speakers.json`; `null` allowed    |
| `category_id` | string                | no       | references `categories.json`                  |
| `description` | string                | no       | plain text                                    |
| `location`    | string                | no       | free-text location override, if different     |
| `recurrence`  | object                | no       | see Recurrence below                          |

### Example

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
  "description": "Kuliyyah mingguan selepas solat Maghrib.",
  "status": "published"
}
```

### Status values

```text
draft       -> invisible to the public
published   -> visible normally
cancelled   -> visible with cancellation warning
postponed   -> visible with postponement warning
completed   -> historical / archive behavior
```

### Recurrence

Recurring events use a recurrence object instead of many duplicate records.

```json
{
  "recurrence": {
    "type": "weekly",
    "days": ["wednesday"],
    "start_date": "2026-08-12",
    "end_date": null,
    "exceptions": ["2026-08-26"]
  }
}
```

| Field        | Type        | Required | Notes                                   |
| ------------ | ----------- | -------- | --------------------------------------- |
| `type`       | string      | yes      | currently only `weekly`                 |
| `days`       | string[]    | yes      | weekday names, see weekdays list        |
| `start_date` | string      | no       | default: `date` of the event            |
| `end_date`   | string/null | no       | `null` = recurring indefinitely        |
| `exceptions` | string[]    | no       | individual occurrence dates to cancel   |

Valid weekday names: `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`.

---

## 3. Masjids (`data/masjids.json`)

An array of masjid objects.

| Field        | Type   | Required | Notes                                |
| ------------ | ------ | -------- | ------------------------------------ |
| `id`         | string | yes      | unique, stable, URL-safe             |
| `name`       | string | yes      | display name                         |
| `mukim`   | string | no       | free-text display value, e.g. `Kangar`; when `mukim_id` is set it must match that mukim's name |
| `mukim_id`| string | yes      | must reference `mukims.json`      |
| `editor_id`  | string | no       | must reference `editors.json`        |
| `state`      | string | no       | e.g. `Perlis`                        |
| `address`    | string | no       | free-text address                    |
| `latitude`   | number | no       | decimal degrees                      |
| `longitude`  | number | no       | decimal degrees                      |
| `contact`    | string | no       | phone / email                        |
| `website`    | string | no       | URL                                  |

### Example

```json
{
  "id": "masjid-alwi",
  "name": "Masjid Alwi",
  "mukim": "Kangar",
  "mukim_id": "kangar",
  "editor_id": "editor-pengurusan",
  "state": "Perlis",
  "address": "Jalan Tuanku Syed Putra, 01000 Kangar, Perlis",
  "latitude": 6.4405,
  "longitude": 100.1952,
  "contact": "",
  "website": ""
}
```

The ID must remain stable even if the display name changes. `mukim` is a
display convenience: `mukim_id` is the canonical link, and the two must not
disagree.

---

## 4. Mukims (`data/mukims.json`)

An array of mukim objects (the mukims of Perlis).

| Field         | Type   | Required | Notes             |
| ------------- | ------ | -------- | ----------------- |
| `id`          | string | yes      | unique, kebab-case |
| `name`        | string | yes      | display name, e.g. `Kangar` |
| `description` | string | no       | short description |

### Example

```json
{
  "id": "kangar",
  "name": "Kangar",
  "description": "Ibu negeri Perlis dan mukim sekitarnya."
}
```

Fresh data dirs (new `serve.py` setups) are seeded with the official Perlis
mukims; the list is then maintained via the admin tool.

---

## 5. Editors (`data/editors.json`)

An array of editor objects. Editors are the local administrators who manage
masjid records (linked via `masjid.editor_id`). Access control itself remains
an admin-tool concern — editors are metadata, not credentials.

| Field         | Type   | Required | Notes                    |
| ------------- | ------ | -------- | ------------------------ |
| `id`          | string | yes      | unique, kebab-case       |
| `name`        | string | yes      | display name             |
| `email`       | string | no       | contact e-mail           |
| `role`        | string | no       | e.g. `editor`, `superuser` |
| `description` | string | no       | short description        |

### Example

```json
{
  "id": "editor-pengurusan",
  "name": "Pengurusan Masjid Events Perlis",
  "email": "hello@example.com",
  "role": "superuser",
  "description": "Editor utama penyelaras data acara."
}
```

An array of speaker objects.

| Field         | Type   | Required | Notes                    |
|---------------|--------|----------|--------------------------|
| `id`          | string | yes      | unique, stable, URL-safe |
| `name`        | string | yes      | e.g. `Ustaz Ahmad`       |
| `description` | string | no       | short bio / role         |

Speaker data is optional for events. An event with no `speaker_id` is valid.

### Example

```json
{
  "id": "speaker-ahmad",
  "name": "Ustaz Ahmad",
  "description": "Imam Masjid Alwi"
}
```

---

## 7. Categories (`data/categories.json`)

An array of category objects.

| Field | Type   | Required | Notes          |
|-------|--------|----------|----------------|
| `id`  | string | yes      | stable, kebab-case |
| `name`| string | yes      | display name   |

### Example

```json
{
  "id": "kuliyyah",
  "name": "Kuliyyah"
}
```

Initial categories:

```text
kuliyyah, ceramah, tafsir, hadith, fiqh, akidah, sirah, tazkirah,
khutbah, program, seminar, youth, children, women, ramadan, community, other
```

The category list is configurable.

---

## 8. Settings (`data/settings.json`)

A single settings object (not an array).

| Field              | Type     | Notes                                   |
| ------------------ | -------- | --------------------------------------- |
| `site_name`        | string   | public site name                        |
| `site_url`         | string   | canonical public URL (empty until set)  |
| `language`         | string   | default language code, e.g. `ms`        |
| `timezone`         | string   | IANA timezone, e.g. `Asia/Kuala_Lumpur` |
| `date_format`      | string   | `YYYY-MM-DD`                            |
| `time_format`      | string   | `HH:MM`                                 |
| `event_statuses`   | string[] | allowed status values                   |
| `recurrence_types` | string[] | allowed recurrence types                |
| `weekdays`         | string[] | allowed weekday names                   |

---

## 6. Required vs optional summary

Required in every record:

```text
event:    id, title, masjid_id, date, start_time, status
masjid:   id, name, mukim_id
speaker:  id, name
category: id, name
```

Everything else is optional.

---

## 9. Reference integrity

* Every `event.masjid_id` must exist in `masjids.json`.
* Every `event.speaker_id` must exist in `speakers.json` (unless null/absent).
* Every `event.category_id` must exist in `categories.json`.
* Every `masjid.mukim_id` must exist in `mukims.json`.
* Every `masjid.editor_id` must exist in `editors.json` (unless null/absent).
* If both `masjid.mukim` and `masjid.mukim_id` are present they must agree.
* IDs must not be duplicated within their own file.

---

## 10. Versioning / evolution

The canonical model is a contract. Changes should be additive where possible:

* A new optional field is generally safe to add.
* Renaming or removing a field is a breaking change and must be documented and co-ordinated with validators, importers, and the public site.

Current model version tracked visually in this document. (Future model metadata may live in `settings.json`.)

---

# 11. Timezone handling

All dates and times in the data model are **wall-clock local Malaysia time** (IANA zone `Asia/Kuala_Lumpur`, UTC+8, no daylight-saving changes):

* `date` is the local calendar date (`YYYY-MM-DD`).
* `start_time` / `end_time` are local `HH:MM`.

Public site display (`ui.todayKL()`) always computes "today" against `Asia/Kuala_Lumpur`, never the visitor's device timezone.

Calendar export (`public/js/ics.js`) preserves local semantics by emitting `DTSTART`/`DTEND` with a `TZID=Asia/Kuala_Lumpur` parameter plus `X-WR-TIMEZONE:Asia/Kuala_Lumpur`, and `DTSTAMP`/recurrence `UNTIL` in UTC (`Z` suffix). Because Malaysia has no DST, the fixed offset approach is unambiguous. Recurring events use `RRULE:FREQ=WEEKLY;BYDAY=…`, with `UNTIL` when an end date is set.