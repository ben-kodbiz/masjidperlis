#!/usr/bin/env python3
"""Masjid Events Perlis — static site generator / SEO pages.

Reads the canonical data set and writes server-rendered, no-JavaScript
versions of every event and masjid detail page into the public site, plus
a sitemap, robots.txt, canonical/OpenGraph metadata and structured data
(JSON-LD). The interactive single-page app remains the primary experience;
these generated pages give crawlers and no-JS readers useful HTML.

Outputs (written under --out, default public/):
    event/{event_id}/index.html     server-rendered event page
    masjid/{masjid_id}/index.html   server-rendered masjid page
    sitemap.xml                     all pages, absolute or root-relative locs
    robots.txt                      allow-all + sitemap reference
    <head> patches                  canonical + OpenGraph on top-level pages

Canonical base URL: --site-url (default: settings.json "site_url"). When no
absolute base is known, canonicals and sitemap <loc> use root-relative paths,
which stay consistent with the deployed page locations.

Data is validated before generation; invalid data fails the build (exit 1).

Usage:
    python3 tools/build_site.py                     # default data/ -> public/
    python3 tools/build_site.py --site-url https://example.com
    python3 tools/build_site.py --data-dir data --out /tmp/build --today 2026-08-18
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

from validate_data import validate_directory

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUT = ROOT / "public"

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json", "settings.json")

WEEKDAYS_MS = ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu", "Ahad"]
MONTHS_MS = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun",
    "Julai", "Ogos", "September", "Oktober", "November", "Disember",
]

VISIBLE_STATUSES = ("published", "cancelled", "postponed")

SEOMARK_START = "<!-- build-site-seo -->"
SEOMARK_END = "<!-- /build-site-seo -->"
SEO_PATTERN = re.compile(
    re.escape(SEOMARK_START) + r".*?" + re.escape(SEOMARK_END), re.DOTALL
)

PAGE_SHELLS = (
    "index.html", "events.html", "masjids.html",
)


# ---------------------------------------------------------------------------
# Formatting helpers (mirror public/js/ui.js so generated pages match the app)
# ---------------------------------------------------------------------------

def esc(value):
    return escape("" if value is None else str(value))


def format_time(hhmm):
    if not hhmm:
        return ""
    h, m = str(hhmm).split(":", 1)
    hour = int(h)
    suffix = "PM" if hour >= 12 else "AM"
    hour = hour % 12
    if hour == 0:
        hour = 12
    return "{}:{} {}".format(hour, m or "00", suffix)


def format_date(date_str):
    if not date_str:
        return ""
    try:
        d = date.fromisoformat(str(date_str))
    except ValueError:
        return str(date_str)
    return "{} {:d} {} {:d}".format(WEEKDAYS_MS[d.weekday()], d.day, MONTHS_MS[d.month - 1], d.year)


def event_when(ev):
    start = format_time(ev.get("start_time"))
    end = (" \u2013 " + format_time(ev["end_time"])) if ev.get("end_time") else ""
    return start + end


def status_label(status):
    return {
        "draft": "Draft",
        "published": "Published",
        "cancelled": "Cancelled",
        "postponed": "Postponed",
        "completed": "Completed",
    }.get(status, status or "")


def status_notice(status):
    if status == "cancelled":
        return "Acara ini dibatalkan (cancelled)."
    if status == "postponed":
        return "Acara ini ditangguhkan (postponed)."
    return ""


def status_class(status):
    return "event-status {}".format(status)


# ---------------------------------------------------------------------------
# Recurrence (mirror public/js/events.js occurrence logic)
# ---------------------------------------------------------------------------

def recurring_occurrence_on(ev, date_str):
    rec = ev.get("recurrence")
    if not rec or rec.get("type") != "weekly" or not rec.get("days"):
        return False
    if date_str in (rec.get("exceptions") or []):
        return False
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return False
    weekday = d.strftime("%A").lower()
    if weekday not in rec["days"]:
        return False
    start = rec.get("start_date") or ev.get("date")
    if date_str < start:
        return False
    end = rec.get("end_date")
    if end and date_str > end:
        return False
    return True


def occurrences_on(events, date_str):
    out = []
    for ev in events:
        if ev.get("status") not in VISIBLE_STATUSES:
            continue
        if ev.get("date") == date_str or recurring_occurrence_on(ev, date_str):
            copy = dict(ev)
            copy["_occurrenceDate"] = date_str
            out.append(copy)
    return out


def upcoming(events, from_date, limit=10, masjid_id=None):
    out = []
    seen = set()
    cursor = from_date
    safety = 0
    max_days = 366 * 2
    while len(out) < limit and safety < max_days:
        for ev in occurrences_on(events, cursor):
            if ev.get("id") in seen:
                continue
            if masjid_id and ev.get("masjid_id") != masjid_id:
                continue
            seen.add(ev.get("id"))
            out.append(ev)
        cursor = (date.fromisoformat(cursor).toordinal() + 1)
        cursor = date.fromordinal(cursor).isoformat()
        safety += 1
    return out


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def base_url(settings, site_url):
    if site_url:
        return site_url.rstrip("/")
    return settings.get("site_url", "").rstrip("/") if settings.get("site_url") else ""


def page_url(base, path):
    """Absolute URL when a base is known, else root-relative path."""
    if base:
        return "{}/{}".format(base, path)
    return "/" + path


# ---------------------------------------------------------------------------
# Share links (mirror public/js/share.js)
# ---------------------------------------------------------------------------

def text_summary(ev, masjid, speaker):
    lines = [ev.get("title") or ""]
    loc = [masjid["name"]] if masjid and masjid.get("name") else ([ev.get("masjid_id")] if ev.get("masjid_id") else [])
    lines.append(", ".join(loc))
    when = [format_date(ev.get("date") or "")]
    time_str = event_when(ev)
    if time_str:
        when.append(time_str)
    lines.append(" \u2014 ".join(when))
    if speaker and speaker.get("name"):
        lines.append("Penceramah: " + speaker["name"])
    if ev.get("description"):
        lines.append(ev["description"])
    if ev.get("status") == "cancelled":
        lines.append("NOTA: Acara ini dibatalkan.")
    if ev.get("status") == "postponed":
        lines.append("NOTA: Acara ini ditangguhkan.")
    return "\n".join(line for line in lines if line)


def whatsapp_url(text):
    return "https://wa.me/?text=" + quote(text)


def telegram_url(text, url):
    return "https://t.me/share/url?url=" + quote(url) + "&text=" + quote(text)


# ---------------------------------------------------------------------------
# JSON-LD structured data
# ---------------------------------------------------------------------------

def event_jsonld(ev, masjid, speaker, url):
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": ev.get("title") or "",
        "url": url,
        "eventStatus": {
            "cancelled": "https://schema.org/EventCancelled",
            "postponed": "https://schema.org/EventPostponed",
        }.get(ev.get("status"), "https://schema.org/EventScheduled"),
    }
    if ev.get("description"):
        data["description"] = ev["description"]
    if ev.get("start_time"):
        data["startDate"] = "{}T{}+08:00".format(ev["date"], ev["start_time"])
        data["endDate"] = "{}T{}+08:00".format(
            ev["date"], ev.get("end_time") or ev.get("start_time"))
    if masjid:
        loc = {"@type": "Place", "name": masjid.get("name") or ""}
        if masjid.get("address"):
            loc["address"] = masjid["address"]
        if masjid.get("latitude") is not None and masjid.get("longitude") is not None:
            loc["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": masjid["latitude"],
                "longitude": masjid["longitude"],
            }
        data["location"] = loc
        data["organizer"] = {"@type": "Organization", "name": masjid.get("name") or ""}
    if speaker and speaker.get("name"):
        data["performer"] = {"@type": "Person", "name": speaker["name"]}
    return json.dumps(data, ensure_ascii=False)


def masjid_jsonld(masjid, url):
    data = {
        "@context": "https://schema.org",
        "@type": "Place",
        "name": masjid.get("name") or "",
        "url": url,
    }
    addr = {"@type": "PostalAddress"}
    if masjid.get("address"):
        addr["streetAddress"] = masjid["address"]
    if masjid.get("mukim"):
        addr["addressLocality"] = masjid["mukim"]
    if masjid.get("state"):
        addr["addressRegion"] = masjid["state"]
    if len(addr) > 1:
        data["address"] = addr
    if masjid.get("latitude") is not None and masjid.get("longitude") is not None:
        data["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": masjid["latitude"],
            "longitude": masjid["longitude"],
        }
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------

HEAD_META = """<meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#0f6b3a">
  <link rel="manifest" href="{base}manifest.webmanifest">
  <meta name="description" content="{description}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{og_title}">
  <meta property="og:description" content="{og_description}">
  <meta property="og:url" content="{og_url}">
  <title>{title}</title>
  <link rel="stylesheet" href="{base}css/style.css">"""


def header_nav(active, base=""):
    items = [
        ("index.html", "Utama", "home"),
        ("events.html", "Acara", "events"),
        ("masjids.html", "Masjid", "masjids"),
    ]
    nav = ["<ul>"]
    for href, label, key in items:
        cur = ' aria-current="page"' if key == active else ""
        nav.append('          <li><a href="{}{}"{}>{}</a></li>'.format(base, href, cur, label))
    nav.append("</ul>")
    return """
    <header class="site-header">
    <div class="inner">
      <div class="brand"><a href="{0}index.html">Masjid Events Perlis</a></div>
      <nav class="site-nav" aria-label="Navigasi utama">
{1}
      </nav>
    </div>
  </header>""".format(base, "\n".join(nav))


FOOTER = """
    <footer class="site-footer">
    <div class="inner">
      <p>Masjid Events Perlis — sumber maklumat terbuka.</p>
    </div>
  </footer>"""


def wrap_page(page, body_html, scripts, seo_meta, base_prefix="../../"):
    """Assemble a generated page. base_prefix points from the page's directory
    back to the site root so every relative URL (css, js, nav, data) resolves
    from the root regardless of the deployment sub-path."""
    nav = header_nav(page, base=base_prefix)
    scripts_html = "\n".join(
        '  <script src="{}js/{}"></script>'.format(base_prefix, s) for s in scripts
    )
    # Generated (script-free) pages still register the service worker so a
    # deep link straight to a generated page still installs the PWA.
    pwa = (
        "\n  <script>\n"
        "  // PWA: register the service worker (generated page has no app.js).\n"
        '  if ("serviceWorker" in navigator && location.protocol === "https:") {\n'
        "    addEventListener(\"load\", function () {\n"
        '      navigator.serviceWorker.register("' + base_prefix + 'sw.js").catch(function () {});\n'
        "    });\n"
        "  }\n"
        "  </script>"
        if not scripts else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ms">\n'
        "<head>\n"
        + HEAD_META.format(base=base_prefix, **seo_meta)
        + "\n"
        + jsonld_block(seo_meta.get("jsonld"))
        + "</head>\n"
        + '<body data-page="{}"{}>\n'.format(page, seo_meta.get("body_data", ""))
        + '  <a class="skip-link" href="#main">Langkau ke kandungan</a>\n'
        + nav
        + "\n\n  <main id=\"main\" tabindex=\"-1\">\n"
        + body_html
        + "\n  </main>\n"
        + FOOTER
        + "\n\n"
        + scripts_html
        + pwa
        + "\n</body>\n</html>\n"
    )


def jsonld_block(jsonld_text):
    if not jsonld_text:
        return ""
    return '  <script type="application/ld+json">{}</script>\n'.format(jsonld_text)


def seo(title, description, canonical, og_type, og_title, og_url, body_data="", jsonld=""):
    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_type": og_type,
        "og_title": og_title,
        "og_description": description,
        "og_url": og_url,
        "body_data": body_data,
        "jsonld": jsonld,
    }


# ---------------------------------------------------------------------------
# ICS generation (mirror public/js/ics.js so static pages keep calendar export)
# ---------------------------------------------------------------------------

DAY_ABBR = {
    "monday": "MO", "tuesday": "TU", "wednesday": "WE", "thursday": "TH",
    "friday": "FR", "saturday": "SA", "sunday": "SU",
}


def ics_escape(text):
    return ("" if text is None else str(text)) \
        .replace("\\", "\\\\") \
        .replace(",", "\\,") \
        .replace(";", "\\;") \
        .replace("\r\n", "\\n").replace("\n", "\\n")


def ics_local_datetime(date_str, time_str):
    d = str(date_str or "").replace("-", "")
    t = str(time_str or "00:00").replace(":", "")
    return d + "T" + t + "00"


def ics_rrule(ev):
    rec = ev.get("recurrence")
    if not rec or rec.get("type") != "weekly" or not rec.get("days"):
        return ""
    byday = ",".join(DAY_ABBR.get(str(day).lower(), "MO") for day in rec["days"])
    value = "FREQ=WEEKLY;BYDAY=" + byday
    if rec.get("start_date") and rec["start_date"] != ev.get("date"):
        value += ";DTSTART=" + ics_local_datetime(rec["start_date"], ev.get("start_time"))
    if rec.get("end_date"):
        value += ";UNTIL=" + str(rec["end_date"]).replace("-", "") + "T000000Z"
    return value


def event_to_ics(ev, masjid, site_name="Masjid Events Perlis"):
    end = ev.get("end_time") or ev.get("start_time")
    location_parts = []
    if masjid and masjid.get("name"):
        location_parts.append(masjid["name"])
    if masjid and masjid.get("address"):
        location_parts.append(masjid["address"])
    location = ", ".join(x for x in location_parts if x) or ev.get("masjid_id") or ""

    desc_parts = [ev.get("description")] if ev.get("description") else []
    status = {"cancelled": "CANCELLED", "postponed": "TENTATIVE"}.get(ev.get("status"), "CONFIRMED")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Masjid Events Perlis//IDN masjidperlis.org//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + ics_escape(site_name),
        "X-WR-TIMEZONE:Asia/Kuala_Lumpur",
        "BEGIN:VEVENT",
        "UID:" + ics_escape(ev.get("id", "")) + "@masjidperlis.org",
        "DTSTAMP:20260801T000000Z",
        "DTSTART;TZID=Asia/Kuala_Lumpur:" + ics_local_datetime(ev.get("date"), ev.get("start_time")),
        "DTEND;TZID=Asia/Kuala_Lumpur:" + ics_local_datetime(ev.get("date"), end),
        "STATUS:" + status,
        "SUMMARY:" + ics_escape(ev.get("title", "")),
    ]
    if desc_parts:
        lines.append("DESCRIPTION:" + ics_escape("\n".join(x for x in desc_parts if x)))
    if location:
        lines.append("LOCATION:" + ics_escape(location))
    rrule = ics_rrule(ev)
    if rrule:
        lines.append("RRULE:" + rrule)
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------------------
# Event page
# ---------------------------------------------------------------------------

def event_body(ev, masjid, speaker, category, base):
    rows = [
        ("Tarikh", esc(format_date(ev.get("date") or ""))),
        ("Masa", esc(event_when(ev))),
        ("Lokasi", '<a href="{}masjid/{}/">{}</a>'.format(
            base, esc(masjid["id"]), esc(masjid.get("name") or ev.get("masjid_id")))
            if masjid else esc(ev.get("masjid_id") or "")),
    ]
    if speaker:
        rows.append(("Penceramah", esc(speaker.get("name") or "")))
    if category:
        rows.append(("Kategori", esc(category.get("name") or "")))
    if ev.get("description"):
        rows.append(("Keterangan", esc(ev["description"])))
    if ev.get("recurrence"):
        rows.append(("Berulang", "Mingguan ({})".format(esc(", ".join(ev["recurrence"].get("days") or [])))))
    rows.append(("Status", '<span class="{}">{}</span>'.format(
        status_class(ev.get("status")), esc(status_label(ev.get("status"))))))

    dl = ["    <dl>"]
    for dt, dd in rows:
        dl.append("      <dt>{}</dt>".format(dt))
        dl.append("      <dd>{}</dd>".format(dd))
    dl.append("    </dl>")

    notice = status_notice(ev.get("status"))
    notice_html = '    <div class="notice">{}</div>'.format(esc(notice)) if notice else ""

    parts = [
        '  <article class="detail" aria-labelledby="ev-title">',
        '    <h1 id="ev-title">{}</h1>'.format(esc(ev.get("title") or "")),
    ]
    if notice_html:
        parts.append(notice_html)
    parts.extend(dl)
    parts.append("  </article>")

    ics_link = (
        '  <div class="share"><a class="btn" href="event.ics">'
        "Tambah ke kalendar (.ics)</a></div>"
    )
    parts.append(ics_link)

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Masjid page
# ---------------------------------------------------------------------------

def masjid_body(masjid, events, masjids_by_id, categories_by_id, speakers_by_id, today, base):
    lines = []
    if masjid.get("mukim") or masjid.get("state"):
        lines.append(", ".join(x for x in (masjid.get("mukim"), masjid.get("state")) if x))
    meta_html = '    <p class="muted">{}</p>'.format(esc(", ".join(lines))) if lines else ""
    address_html = '    <p>{}</p>'.format(esc(masjid.get("address"))) if masjid.get("address") else ""

    links = []
    if masjid.get("contact"):
        tel = re.sub(r"[^\d+]", "", str(masjid["contact"]))
        links.append('<a class="btn btn-ghost" href="tel:{}">Hubungi</a>'.format(quote(tel)))
    if masjid.get("website"):
        links.append(
            '<a class="btn btn-ghost" rel="noopener" target="_blank" href="{}">Laman web<span class="vh"> (buka dalam tab baharu)</span></a>'
            .format(esc(masjid["website"])))
    if masjid.get("latitude") is not None and masjid.get("longitude") is not None:
        lat, lon = masjid["latitude"], masjid["longitude"]
        links.append(
            '<a class="btn" rel="noopener" target="_blank" href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=16/{lat}/{lon}">Peta<span class="vh"> (buka dalam tab baharu)</span></a>'
            .format(lat=lat, lon=lon))
    links_html = '    <div class="masjid-links">{}</div>'.format("".join(links)) if links else ""

    upcoming_list = []
    for ev in upcoming(events, today, 10, masjid_id=masjid["id"]):
        occ_date = ev.get("_occurrenceDate") or ev.get("date")
        m = masjids_by_id.get(ev.get("masjid_id"))
        upcoming_list.append(
            '      <li><a class="event-card" href="{}event/{}/">'
            '<span class="when">{}</span>'
            '<span class="title">{}</span>'
            '<span class="where">{}</span></a></li>'.format(
                base,
                esc(ev["id"]),
                esc(format_date(occ_date or "")),
                esc(ev.get("title") or ""),
                esc(", ".join(x for x in (m["name"] if m else ev.get("masjid_id"), event_when(ev)) if x)),
            )
        )
    if not upcoming_list:
        upcoming_list = ['      <li><p class="empty-state">Tiada acara akan datang buat masa ini.</p></li>']

    body = [
        "    <h1>{}</h1>".format(esc(masjid.get("name") or "")),
    ]
    if meta_html:
        body.append(meta_html)
    if address_html:
        body.append(address_html)
    if links_html:
        body.append(links_html)
    body.append('    <h2 class="section-title">Akan Datang</h2>')
    body.append("    <ul class=\"event-list\">")
    body.extend(upcoming_list)
    body.append("    </ul>")
    return "\n".join(body) + "\n"


# ---------------------------------------------------------------------------
# Sitemap + robots
# ---------------------------------------------------------------------------

def build_sitemap(base, event_ids, masjid_ids):
    paths = ["", "events.html", "masjids.html"]
    paths += ["event/{}/".format(i) for i in event_ids]
    paths += ["masjid/{}/".format(i) for i in masjid_ids]
    locs = ["    <url><loc>{}</loc></url>".format(esc(page_url(base, p) if p else (base + "/" if base else "/")))
            for p in paths]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(locs)
        + "\n</urlset>\n"
    )


def build_robots(base):
    lines = ["User-agent: *", "Allow: /"]
    if base:
        lines.append("")
        lines.append("Sitemap: {}/sitemap.xml".format(base))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Service worker (PWA)
# ---------------------------------------------------------------------------

def build_swjs(version):
    """Return the service worker source stamped with CACHE_VERSION.

    Strategy (safe for frequently-changing event data):
      - Shell assets (css/js/manifest/icons): stale-while-revalidate in a
        versioned cache, so a fresh deploy busts them automatically.
      - data/*.json and page navigations: NETWORK-FIRST. Online users always
        get the freshest schedule; the cached copy is only an offline
        fallback, so cancelled/postponed events are never shown as current.
      - Caches from older versions are removed on activation.
    """
    _SWJS_TEMPLATE = """/* Masjid Events Perlis — service worker.
 * Generated by tools/build_site.py. Do not edit by hand.
 *
 * Caching strategy:
 *   - Shell assets (css/js/manifest/icons) are stale-while-revalidate in a
 *     versioned cache; a new deploy stamps a fresh CACHE_VERSION and cleans
 *     the old caches on activate.
 *   - data/*.json and page navigations are NETWORK-FIRST so online users
 *     never see stale event info; the cached copy is only an offline
 *     fallback.
 */

const CACHE_VERSION = "__VERSION__";
const SHELL_CACHE = "masjid-perlis-shell-" + CACHE_VERSION;
const DATA_CACHE = "masjid-perlis-data-" + CACHE_VERSION;

const PRECACHE = [
  "./",
  "css/style.css",
  "js/data.js",
  "js/ui.js",
  "js/events.js",
  "js/masjids.js",
  "js/share.js",
  "js/ics.js",
  "js/maps.js",
  "js/app.js",
  "manifest.webmanifest",
  "assets/icon-192.png",
  "assets/icon-512.png"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(function (cache) { return cache.addAll(PRECACHE); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(
          keys.filter(function (key) {
            return key !== SHELL_CACHE && key !== DATA_CACHE;
          }).map(function (key) { return caches.delete(key); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") { return; }

  var url = new URL(request.url);
  if (url.origin !== location.origin) { return; }

  var pathname = url.pathname;
  var isData = pathname.indexOf("/data/") !== -1;
  var isShell = PRECACHE.some(function (asset) {
    return pathname === "/" + asset || pathname.slice(-(asset.length + 1)) === "/" + asset;
  });

  // Data and page navigations: network-first, cache is only an offline fallback.
  if (isData || request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(function (response) {
          if (response && response.ok) {
            var copy = response.clone();
            caches.open(DATA_CACHE).then(function (cache) { cache.put(request, copy); });
          }
          return response;
        })
        .catch(function () {
          return caches.match(request).then(function (hit) {
            if (hit) { return hit; }
            if (request.mode === "navigate") {
              return caches.match("./").then(function (shell) {
                return shell || Response.error();
              });
            }
            return Response.error();
          });
        })
    );
    return;
  }

  // Shell assets: stale-while-revalidate (cache-first with background refresh).
  if (isShell) {
    event.respondWith(
      caches.match(request).then(function (hit) {
        var refresh = fetch(request)
          .then(function (response) {
            if (response && response.ok) {
              var copy = response.clone();
              caches.open(SHELL_CACHE).then(function (cache) { cache.put(request, copy); });
            }
            return response;
          })
          .catch(function () { return hit || Response.error(); });
        return hit || refresh;
      })
    );
    return;
  }

  // Everything else: network only.
});
"""

    return _SWJS_TEMPLATE.replace("__VERSION__", version or "dev")


# ---------------------------------------------------------------------------
# Top-level page <head> injection
# ---------------------------------------------------------------------------

def inject_seo_head(html_path, base):
    if not html_path.exists():
        return False
    text = html_path.read_text(encoding="utf-8")
    if "</head>" not in text:
        return False

    path = html_path.name
    canonical = (base + "/") if path == "index.html" and base else page_url(base, path)
    desc = {
        "index.html": "Program dan aktiviti masjid-masjid di Perlis: kuliyyah, ceramah, tazkirah dan banyak lagi.",
        "events.html": "Senarai program dan aktiviti masjid di Perlis.",
        "masjids.html": "Direktori masjid di Perlis.",
    }.get(path, "")

    block = (
        "\n" + SEOMARK_START + "\n"
        + '  <link rel="canonical" href="{}">\n'.format(esc(canonical))
        + '  <meta property="og:type" content="website">\n'
        + '  <meta property="og:title" content="Masjid Events Perlis">\n'
        + '  <meta property="og:description" content="{}">\n'.format(esc(desc))
        + '  <meta property="og:url" content="{}">\n'.format(esc(canonical))
        + SEOMARK_END + "\n"
    )
    if SEO_PATTERN.search(text):
        text = SEO_PATTERN.sub(lambda m: block, text, count=1)
    else:
        text = text.replace("</head>", block + "  </head>", 1)
    html_path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(data_dir):
    parsed = {}
    for fname in DATA_FILES:
        with open(data_dir / fname, "r", encoding="utf-8") as fh:
            parsed[fname] = json.load(fh)
    return parsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build static SEO pages from canonical data.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--site-url", default="", help="absolute base URL, e.g. https://example.com")
    parser.add_argument("--today", default="", help="reference date YYYY-MM-DD for 'akan datang' (default: KL today)")
    parser.add_argument("--version", default="", help="cache stamp for the service worker (default: KL build timestamp)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv) if argv is not None else parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)

    errors = validate_directory(data_dir)
    if errors:
        print("build_site: data validation FAILED ({} problem(s)):".format(len(errors)), file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1

    parsed = load_data(data_dir)
    masjids = parsed["masjids.json"]
    events = parsed["events.json"]
    speakers = parsed["speakers.json"]
    categories = parsed["categories.json"]
    settings = parsed["settings.json"]

    site_name = settings.get("site_name") or "Masjid Events Perlis"
    base = base_url(settings, args.site_url)

    if args.today:
        today = args.today
    else:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).strftime("%Y-%m-%d")

    if args.version:
        version = args.version
    else:
        from zoneinfo import ZoneInfo
        version = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).strftime("%Y%m%dT%H%M%S")

    masjids_by_id = {m["id"]: m for m in masjids if m.get("id")}
    speakers_by_id = {s["id"]: s for s in speakers if s.get("id")}
    categories_by_id = {c["id"]: c for c in categories if c.get("id")}

    written = []
    for ev in events:
        if ev.get("status") not in VISIBLE_STATUSES:
            continue
        eid = ev.get("id")
        if not eid:
            continue
        canonical = page_url(base, "event/{}/".format(eid))
        masjid = masjids_by_id.get(ev.get("masjid_id"))
        speaker = speakers_by_id.get(ev.get("speaker_id"))
        category = categories_by_id.get(ev.get("category_id"))
        meta = seo(
            title="{} \u2014 {}".format(ev.get("title") or "", site_name),
            description=((ev.get("description") or "")[:160]) or "{} di {}".format(
                ev.get("title") or "", masjid.get("name") if masjid else ev.get("masjid_id")),
            canonical=canonical,
            og_type="article",
            og_title=ev.get("title") or site_name,
            og_url=canonical,
            body_data=' data-event-id="{}"'.format(esc(eid)),
            jsonld=event_jsonld(ev, masjid, speaker, canonical),
        )
        body = event_body(ev, masjid, speaker, category, base="../../")
        # rebuild body with share links that need the canonical URL
        summary = text_summary(ev, masjid, speaker)
        share = (
            '  <div class="share">'
            '<a class="btn btn-ghost" rel="noopener" target="_blank" href="{}">Kongsi WhatsApp<span class="vh"> (buka dalam tab baharu)</span></a>'
            '<a class="btn btn-ghost" rel="noopener" target="_blank" href="{}">Kongsi Telegram<span class="vh"> (buka dalam tab baharu)</span></a>'
            "</div>"
        ).format(whatsapp_url(summary + "\n" + canonical), telegram_url(summary, canonical))
        body = body.replace("  </article>", "  </article>\n" + share)

        page = wrap_page("event", body, [], meta)
        dest = out_dir / "event" / eid / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")

        ics_dest = out_dir / "event" / eid / "event.ics"
        ics_dest.write_text(event_to_ics(ev, masjid, site_name), encoding="utf-8")
        written.append("event/{}".format(eid))

    for masjid in masjids:
        mid = masjid.get("id")
        if not mid:
            continue
        canonical = page_url(base, "masjid/{}/".format(mid))
        meta = seo(
            title="{} \u2014 {}".format(masjid.get("name") or "", site_name),
            description="{} \u2014 {}".format(
                masjid.get("name") or "",
                ", ".join(x for x in (masjid.get("mukim"), masjid.get("state")) if x) or "Perlis"),
            canonical=canonical,
            og_type="website",
            og_title=masjid.get("name") or site_name,
            og_url=canonical,
            body_data=' data-masjid-id="{}"'.format(esc(mid)),
            jsonld=masjid_jsonld(masjid, canonical),
        )
        body = masjid_body(masjid, events, masjids_by_id, categories_by_id, speakers_by_id, today, base="../../")
        page = wrap_page("masjid", body, [], meta)
        dest = out_dir / "masjid" / mid / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        written.append("masjid/{}".format(mid))

    event_ids = [m.split("/", 1)[1] for m in written if m.startswith("event/")]
    masjid_ids = [m.split("/", 1)[1] for m in written if m.startswith("masjid/")]

    (out_dir / "sitemap.xml").write_text(build_sitemap(base, event_ids, masjid_ids), encoding="utf-8")
    (out_dir / "robots.txt").write_text(build_robots(base), encoding="utf-8")
    (out_dir / "sw.js").write_text(build_swjs(version), encoding="utf-8")

    patched = []
    for name in PAGE_SHELLS:
        if inject_seo_head(out_dir / name, base):
            patched.append(name)

    print("build_site: {} event page(s), {} masjid page(s), sitemap.xml, robots.txt, sw.js".format(
        len(event_ids), len(masjid_ids)))
    if patched:
        print("build_site: injected canonical/OG into: " + ", ".join(patched))
    if not base:
        print("build_site: warning — no site_url; canonicals/sitemap use root-relative paths.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
