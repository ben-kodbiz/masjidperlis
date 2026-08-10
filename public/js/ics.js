/* Ics — RFC 5545 iCal (.ics) generation for a single event.
   Pure/string-based so it is testable in Node. Malaysia timezone is
   Asia/Kuala_Lumpur (UTC+8, no daylight saving), so DTSTART/DTEND carry a
   TZID parameter and the calendar declares X-WR-TIMEZONE. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;

  // Escape text values per RFC 5545 (backslash, comma, semicolon, newlines).
  function escapeText(text) {
    return String(text == null ? "" : text)
      .replace(/\\/g, "\\\\")
      .replace(/,/g, "\\,")
      .replace(/;/g, "\\;")
      .replace(/\r?\n/g, "\\n");
  }

  // "2026-08-09" + "20:00" -> "20260809T200000"
  function localDateTime(dateStr, timeStr) {
    const d = String(dateStr || "").replace(/-/g, "");
    const t = String(timeStr || "00:00").replace(":", "");
    return d + "T" + t + "00";
  }

  // RFC 5545 weekday abbreviations for RRULE BYDAY.
  const DAY_ABBR = {
    sunday: "SU", monday: "MO", tuesday: "TU", wednesday: "WE",
    thursday: "TH", friday: "FR", saturday: "SA"
  };

  // rrule value for a weekly recurrence, or "" if none.
  function rruleFor(ev) {
    const rec = ev.recurrence;
    if (!rec || rec.type !== "weekly" || !rec.days || !rec.days.length) return "";
    const byday = rec.days.map(function (d) {
      return DAY_ABBR[String(d).toLowerCase()] || "MO";
    }).join(",");
    let value = "FREQ=WEEKLY;BYDAY=" + byday;
    if (rec.start_date && rec.start_date !== ev.date) {
      value += ";DTSTART=" + localDateTime(rec.start_date, ev.start_time);
    }
    if (rec.end_date) {
      value += ";UNTIL=" + String(rec.end_date).replace(/-/g, "") + "T000000Z";
    }
    return value;
  }

  // RFC 5545 STATUS keyword for the event status.
  function statusFor(status) {
    if (status === "cancelled") return "CANCELLED";
    if (status === "postponed") return "TENTATIVE";
    return "CONFIRMED";
  }

  // Trigger only defined in tests (stable clock). Layout helper for one line.
  function format(key, value) {
    return key + ":" + value + "\r\n";
  }

  // Build a single-event .ics document. opts: { now, tzid, prodid } for tests.
  function eventToIcs(ev, opts) {
    opts = opts || {};
    const tzid = opts.tzid || "Asia/Kuala_Lumpur";
    const prodid = opts.prodid || "-//Masjid Events Perlis//IDN masjidperlis.org//EN";
    const now = opts.now || new Date();
    const dtStamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

    const end = ev.end_time
      ? localDateTime(ev.date, ev.end_time)
      : localDateTime(ev.date, ev.start_time);

    const locationParts = [];
    if (ME.masjids && ME.masjids.get) {
      const m = ME.masjids.get(ev.masjid_id);
      if (m) locationParts.push(m.name);
    }
    if (ME.masjids && ME.masjids.get) {
      const m2 = ME.masjids.get(ev.masjid_id);
      if (m2 && m2.address) locationParts.push(m2.address);
    }
    const location = locationParts.join(", ") || ev.masjid_id || "";

    let descParts = [];
    if (ev.description) descParts.push(ev.description);
    if (ev.speaker_id && ME.speakers && ME.speakers.get) {
      const s = ME.speakers.get(ev.speaker_id);
      if (s) descParts.push("Penceramah: " + s.name);
    }

    let out = "";
    out += "BEGIN:VCALENDAR\r\n";
    out += "VERSION:2.0\r\n";
    out += "PRODID:" + prodid + "\r\n";
    out += "CALSCALE:GREGORIAN\r\n";
    out += "METHOD:PUBLISH\r\n";
    out += "X-WR-CALNAME:" + escapeText((opts.siteName || "Masjid Events Perlis")) + "\r\n";
    out += "X-WR-TIMEZONE:" + tzid + "\r\n";
    out += "BEGIN:VEVENT\r\n";
    out += "UID:" + escapeText(ev.id) + "@masjidperlis.org\r\n";
    out += "DTSTAMP:" + dtStamp + "\r\n";
    out += "DTSTART;TZID=" + tzid + ":" + localDateTime(ev.date, ev.start_time) + "\r\n";
    out += "DTEND;TZID=" + tzid + ":" + end + "\r\n";
    out += "STATUS:" + statusFor(ev.status) + "\r\n";
    out += "SUMMARY:" + escapeText(ev.title) + "\r\n";
    if (descParts.length) out += "DESCRIPTION:" + escapeText(descParts.join("\n")) + "\r\n";
    if (location) out += "LOCATION:" + escapeText(location) + "\r\n";
    const rrule = rruleFor(ev);
    if (rrule) out += "RRULE:" + rrule + "\r\n";
    out += "END:VEVENT\r\n";
    out += "END:VCALENDAR\r\n";
    return out;
  }

  // Download an .ics for the given event via a Blob + <a download>.
  function downloadIcs(ev, opts) {
    const ics = eventToIcs(ev, opts);
    const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (ev.id || "event") + ".ics";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  ME.ics = {
    eventToIcs: eventToIcs,
    rruleFor: rruleFor,
    downloadIcs: downloadIcs
  };
})();