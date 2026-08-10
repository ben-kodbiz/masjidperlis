/* UI helpers — safe DOM rendering, formatting, and empty/error states. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;

  const WEEKDAYS_MS = [
    "Ahad", "Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu"
  ];
  const MONTHS_MS = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun",
    "Julai", "Ogos", "September", "Oktober", "November", "Disember"
  ];

  // Escape text for safe insertion into HTML (XSS-safe by default).
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Build DOM nodes safely from an object tree; never inject raw HTML for
  // user data. Attributes and text are escaped automatically.
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "class") node.className = attrs[key];
        else if (key === "dataset") {
          Object.keys(attrs.dataset || {}).forEach(function (dk) {
            node.dataset[dk] = attrs.dataset[dk];
          });
        } else if (key.indexOf("on") === 0 && typeof attrs[key] === "function") {
          node.addEventListener(key.slice(2), attrs[key]);
        } else {
          node.setAttribute(key, attrs[key]);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child == null) return;
      if (child.nodeType) node.appendChild(child);
      else node.appendChild(document.createTextNode(String(child)));
    });
    return node;
  }

  // "12" -> "12" ; "20:00" -> "8:00 PM" (Malaysia local time convention).
  function formatTime(hhmm) {
    if (!hhmm) return "";
    const parts = String(hhmm).split(":");
    let h = parseInt(parts[0], 10);
    const m = parts[1] || "00";
    const suffix = h >= 12 ? "PM" : "AM";
    h = h % 12;
    if (h === 0) h = 12;
    return h + ":" + m + " " + suffix;
  }

  // "2026-08-12" -> "Rabu, 12 Ogos 2026" using Malay names.
  function formatDate(dateStr) {
    const parts = String(dateStr || "").split("-");
    if (parts.length !== 3) return dateStr || "";
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);
    const day = parseInt(parts[2], 10);
    if (!year || !month || !day) return dateStr;
    const jsDate = new Date(Date.UTC(year, month - 1, day));
    const weekday = WEEKDAYS_MS[jsDate.getUTCDay()];
    return weekday + ", " + day + " " + MONTHS_MS[month - 1] + " " + year;
  }

  // Today's "YYYY-MM-DD" in Asia/Kuala_Lumpur, independent of browser timezone.
  function todayKL() {
    const now = new Date();
    const fmt = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Kuala_Lumpur",
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    });
    return fmt.format(now); // en-CA gives YYYY-MM-DD
  }

  function addDays(dateStr, n) {
    const parts = String(dateStr).split("-");
    const d = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }

  // Friendlier piece: for events without end_time, show only start.
  function eventWhen(event) {
    const start = formatTime(event.start_time);
    const end = event.end_time ? " – " + formatTime(event.end_time) : "";
    return start + end;
  }

  ME.ui = {
    esc: esc,
    el: el,
    formatTime: formatTime,
    formatDate: formatDate,
    todayKL: todayKL,
    addDays: addDays,
    eventWhen: eventWhen
  };

  // Shared status display helper used by events.js and masjids.js.
  ME.statusLabel = function (status) {
    const map = {
      draft: "Draft",
      published: "Published",
      cancelled: "Cancelled",
      postponed: "Postponed",
      completed: "Completed"
    };
    return map[status] || status;
  };
})();