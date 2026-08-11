/* Events — client-side filtering, grouping, and rendering. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;
  const ui = ME.ui;

  // Public-visible statuses. draft is never shown; completed is archived.
  const VISIBLE = { published: true, cancelled: true, postponed: true };

  function isVisible(event) {
    return !!VISIBLE[event.status] &&
      (event.status !== "postponed" || true); // postponed still shown w/ notice
  }

  function byDateAsc(a, b) {
    if (a.date !== b.date) return a.date < b.date ? -1 : 1;
    return (a.start_time || "").localeCompare(b.start_time || "");
  }

  function isRecurringOccurrenceOn(event, dateStr) {
    if (!event.recurrence) return false;
    const rec = event.recurrence;
    if (rec.type !== "weekly" || !rec.days) return false;
    // Individual occurrences may be cancelled via recurrence.exceptions.
    if (rec.exceptions && rec.exceptions.length) {
      const excl = rec.exceptions.map(function (d) { return String(d); });
      if (excl.indexOf(dateStr) !== -1) return false;
    }
    // compute weekday of dateStr
    const parts = dateStr.split("-");
    const d = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
    const weekday = WEEKDAY_INDEX[d.getUTCDay()];
    if (!rec.days.includes(weekday)) return false;
    const start = rec.start_date || event.date;
    if (dateStr < start) return false;
    if (rec.end_date && dateStr > rec.end_date) return false;
    return true;
  }

  // True when this date is an explicit exception (cancellation) for the event's
  // recurrence. Used to annotate detail pages.
  function isExceptionDate(event, dateStr) {
    if (!event || !event.recurrence || !event.recurrence.exceptions) return false;
    return event.recurrence.exceptions.map(String).indexOf(String(dateStr)) !== -1;
  }

  const WEEKDAY_INDEX = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

  // Returns occurrence copies for a specific date (handles base + recurring).
  function occurrencesOn(events, dateStr) {
    const out = [];
    events.forEach(function (ev) {
      if (!isVisible(ev)) return;
      if (ev.date === dateStr) {
        out.push(Object.assign({}, ev, { _occurrenceDate: dateStr }));
      } else if (isRecurringOccurrenceOn(ev, dateStr)) {
        out.push(Object.assign({}, ev, { _occurrenceDate: dateStr }));
      }
    });
    return out.sort(byDateAsc);
  }

  function upcoming(events, fromDate, limit, opts) {
    opts = opts || {};
    const out = [];
    const seen = {};
    let cursor = fromDate;
    let safety = 0;
    const maxDays = 366 * 2; // bounded horizon: 2 years, avoids infinite loops
    while (out.length < (limit || 20) && safety < maxDays) {
      const occ = occurrencesOn(events, cursor);
      occ.forEach(function (o) {
        if (out.length < (limit || 20) && !seen[o.id]) {
          if (opts.masjid && o.masjid_id !== opts.masjid) return;
          seen[o.id] = true;
          out.push(o);
        }
      });
      cursor = addDaysKL(cursor, 1);
      safety += 1;
      if (out.length === 0 && DATE_BOUND[1] && cursor > DATE_BOUND[1]) safety = maxDays;
    }
    return out;
  }

  // helpers (duplicated locally to keep module standalone)
  function addDaysKL(dateStr, n) {
    const p = dateStr.split("-");
    const d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }

  let DATE_BOUND = [null, null];

  // All distinct occurrences within [from, to]. If to is null, scan open-ended
  // up to a 2-year horizon (returns up to `limit` most recent-first distinct).
  function range(events, from, to, limit) {
    if (to) {
      const out = [];
      const seen = {};
      let cursor = from;
      let safety = 0;
      const cap = limit || 100;
      while (cursor <= to && safety < 800) {
        occurrencesOn(events, cursor).forEach(function (o) {
          if (seen[o.id]) return;
          seen[o.id] = true;
          out.push(o);
        });
        cursor = addDaysKL(cursor, 1);
        safety++;
      }
      return out.slice(0, cap);
    }
    return upcoming(events, from, limit || 50);
  }

  // Searchable text for an event: title + description + masjid name +
  // speaker name + category name (lowercased). Lookups resolve against the
  // modules wired by app.js (ME.masjids / ME.speakers / ME.categories).
  function searchText(ev) {
    const parts = [ev.title, ev.description];
    if (ev.masjid_id && ME.masjids && ME.masjids.get) {
      const m = ME.masjids.get(ev.masjid_id);
      if (m) parts.push(m.name);
    }
    if (ev.speaker_id && ME.speakers && ME.speakers.get) {
      const s = ME.speakers.get(ev.speaker_id);
      if (s) parts.push(s.name);
    }
    if (ev.category_id && ME.categories && ME.categories.get) {
      const c = ME.categories.get(ev.category_id);
      if (c) parts.push(c.name);
    }
    return parts.join(" ").toLowerCase();
  }

  function filterEvents(events, opts) {
    opts = opts || {};
    return events.filter(function (ev) {
      if (!isVisible(ev)) return false;
      if (opts.masjid && ev.masjid_id !== opts.masjid) return false;
      if (opts.mukim) {
        if (ME.masjids && ME.masjids.get(ev.masjid_id) &&
            ME.masjids.get(ev.masjid_id).mukim !== opts.mukim) return false;
      }
      if (opts.category && ev.category_id !== opts.category) return false;
      if (opts.status && ev.status !== opts.status) return false;
      if (opts.from && ev.date < opts.from) return false;
      if (opts.to && ev.date > opts.to) return false;
      if (opts.q) {
        if (searchText(ev).indexOf(opts.q.toLowerCase()) === -1) return false;
      }
      return true;
    }).sort(byDateAsc);
  }

  // ---- Rendering ----

  function eventCard(event) {
    const dateStr = event._occurrenceDate || event.date;
    const beInformed = statusNotice(event);
    const hasNotice = beInformed.trim().length > 0;
    const masjid = ME.masjids ? ME.masjids.get(event.masjid_id) : null;

    const metaParts = [];
    if (masjid) metaParts.push(masjid.name);
    else metaParts.push(event.masjid_id);
    metaParts.push(ui.eventWhen(event));
    if (event.speaker_id) {
      const spk = ME.speakers ? ME.speakers.get(event.speaker_id) : null;
      if (spk) metaParts.push(spk.name);
    }

    const anchor = ui.el("a", {
      class: "event-card",
      href: "event/" + encodeURIComponent(event.id) + "/",
      "aria-label": event.title + ", " + ui.formatDate(dateStr) + ", " + ui.eventWhen(event)
    }, [
      ui.el("span", { class: "when" }, [ui.formatDate(dateStr) + (event._occurrenceDate ? " (ulangan)" : "")]),
      ui.el("span", { class: "title", style: "display:block;font-weight:700;margin:.15rem 0" }, [event.title]),
      ui.el("span", { class: "where" }, [metaParts.join(" · ")])
    ]);
    if (event.status === "cancelled" || event.status === "postponed") {
      anchor.insertBefore(statusBadge(event.status), anchor.firstChild);
    }
    if (hasNotice) {
      anchor.insertBefore(ui.el("div", { class: "notice" }, [beInformed]), anchor.firstChild);
    }
    return anchor;
  }

  function statusBadge(status) {
    return ui.el("span", { class: "event-status " + status }, [ME.statusLabel(status)]);
  }

  function statusNotice(event) {
    if (event.status === "cancelled") {
      return "Acara ini dibatalkan (cancelled).";
    }
    if (event.status === "postponed") {
      return "Acara ini ditangguhkan (postponed).";
    }
    return "";
  }

  function renderList(container, events) {
    container.textContent = "";
    if (!events.length) {
      container.appendChild(ui.el("p", { class: "empty-state" }, [
        "Tiada acara ditemui pada masa ini. Cuba ubah penapis tarikh atau tab jangka masa yang dipilih."
      ]));
      return;
    }
    const list = ui.el("ul", { class: "event-list" });
    events.forEach(function (ev) {
      const li = ui.el("li", {}, [eventCard(ev)]);
      list.appendChild(li);
    });
    container.appendChild(list);
  }

  ME.events = {
    VISIBLE: VISIBLE,
    isVisible: isVisible,
    occurrencesOn: occurrencesOn,
    upcoming: upcoming,
    range: range,
    filterEvents: filterEvents,
    searchText: searchText,
    isExceptionDate: isExceptionDate,
    renderList: renderList,
    eventCard: eventCard,
    statusNotice: statusNotice,
    statusBadge: statusBadge,
    addDays: addDaysKL,
    setBound: function (from, to) { DATE_BOUND = [from, to]; }
  };
})();