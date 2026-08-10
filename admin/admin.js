/* Masjid Events Perlis — admin shared helpers (local/dev tool only). */
(function (window) {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function api(method, path, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined && body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (resp) {
      return resp.json().then(function (json) {
        return { status: resp.status, ok: resp.ok, json: json };
      });
    });
  }

  var STATUS_LABEL = {
    draft: "Draft",
    published: "Published",
    cancelled: "Cancelled",
    postponed: "Postponed",
    completed: "Completed (arkib)"
  };

  function badge(status) {
    var label = STATUS_LABEL[status] || status;
    return '<span class="badge ' + esc(status) + '">' + esc(label) + "</span>";
  }

  function fmtDate(iso) {
    if (!iso) return "";
    var p = String(iso).split("-");
    if (p.length !== 3) return esc(iso);
    return p[2] + "/" + p[1] + "/" + p[0];
  }

  function today() {
    var d = new Date();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + m + "-" + day;
  }

  function showAlert(container, kind, msgOrList) {
    if (!container) return;
    var items = Array.isArray(msgOrList) ? msgOrList : [msgOrList];
    var html = items.map(function (m) { return "<li>" + esc(m) + "</li>"; }).join("");
    container.innerHTML = kind === "ok"
      ? "<div class=\"alert ok\">" + esc(items[0]) + "</div>"
      : "<div class=\"alert " + esc(kind) + "\"><strong>" + (kind === "err" ? "Ralat" : "Amaran") + ":</strong><ul>" + html + "</ul></div>";
    container.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function clearAlert(container) {
    if (container) container.innerHTML = "";
  }

  function confirmAction(msg) {
    return window.confirm(msg);
  }

  // Highlight the current page in the nav.
  function initNav() {
    var page = document.body.dataset.page;
    document.querySelectorAll(".admin-nav a").forEach(function (a) {
      if (a.dataset.page === page) a.setAttribute("aria-current", "page");
    });
  }

  // Load canonical data once into window.ADMIN_DATA.
  function loadData() {
    return api("GET", "/api/data").then(function (res) {
      if (!res.ok) throw new Error("failed to load /api/data");
      window.ADMIN_DATA = res.json;
      return res.json;
    });
  }

  window.Admin = {
    esc: esc,
    api: api,
    badge: badge,
    fmtDate: fmtDate,
    today: today,
    showAlert: showAlert,
    clearAlert: clearAlert,
    confirm: confirmAction,
    initNav: initNav,
    loadData: loadData,
    STATUS_LABEL: STATUS_LABEL
  };

  document.addEventListener("DOMContentLoaded", initNav);
})(window);
