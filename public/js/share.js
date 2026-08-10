/* Share — event sharing helpers: plain-text summary, share URLs, copy,
   and the native Web Share API. Dependency-free and testable. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;
  const ui = ME.ui;

  // Build a plain-text summary of an event suitable for WhatsApp/Telegram/etc.
  // Looks up masjid/speaker names via the modules wired by app.js.
  function textSummary(ev) {
    const lines = [];
    lines.push(ev.title || "");
    const loc = [];
    if (ev.masjid_id && ME.masjids && ME.masjids.get) {
      const m = ME.masjids.get(ev.masjid_id);
      if (m) loc.push(m.name);
    }
    lines.push(loc.join(", ") || ev.masjid_id || "");
    const when = [];
    when.push(ui.formatDate(ev.date || ""));
    const time = ui.eventWhen(ev);
    if (time) when.push(time);
    lines.push(when.join(" — "));
    if (ev.speaker_id && ME.speakers && ME.speakers.get) {
      const s = ME.speakers.get(ev.speaker_id);
      if (s) lines.push("Penceramah: " + s.name);
    }
    if (ev.description) lines.push(ev.description);
    if (ev.status === "cancelled") lines.push("NOTA: Acara ini dibatalkan.");
    if (ev.status === "postponed") lines.push("NOTA: Acara ini ditangguhkan.");
    return lines.filter(function (line) { return line; }).join("\n");
  }

  // Absolute URL for this event's stable page, same-origin aware.
  function eventUrl(id) {
    const base = window.location.protocol + "//" + window.location.host;
    return base + "/event/" + encodeURIComponent(id) + "/";
  }

  // WhatsApp share link (https-based; no wa.me API key needed).
  function whatsappUrl(text) {
    return "https://wa.me/?text=" + encodeURIComponent(text);
  }

  // Telegram share link.
  function telegramUrl(text, url) {
    return "https://t.me/share/url?url=" + encodeURIComponent(url) +
      "&text=" + encodeURIComponent(text);
  }

  // Copy text to the clipboard. Returns a Promise<boolean>.
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () {
        return true;
      }, function () {
        return fallbackCopy(text);
      });
    }
    return Promise.resolve(fallbackCopy(text));
  }

  // Legacy execCommand fallback (returns boolean synchronously).
  function fallbackCopy(text) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "absolute";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  }

  // Native share (Web Share API) when available, else reject.
  function nativeShare(payload) {
    if (navigator.share) {
      return navigator.share(payload);
    }
    return Promise.reject(new Error("Web Share API tidak disokong"));
  }

  ME.share = {
    textSummary: textSummary,
    eventUrl: eventUrl,
    whatsappUrl: whatsappUrl,
    telegramUrl: telegramUrl,
    copyText: copyText,
    nativeShare: nativeShare
  };
})();