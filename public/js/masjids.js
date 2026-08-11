/* Masjids — directory lookups and rendering. */

(function () {
  "use strict";

  const ME = window.MasjidEvents;
  const ui = ME.ui;

  let list = [];

  function init(data) {
    list = data.masjids || [];
  }

  function get(id) {
    for (let i = 0; i < list.length; i++) {
      if (list[i].id === id) return list[i];
    }
    return null;
  }

  // Featured: masjids that have at least one upcoming event, else first few.
  function featured(events, limit) {
    const withEvents = {};
    events.forEach(function (ev) {
      withEvents[ev.masjid_id] = true;
    });
    const has = list.filter(function (m) { return withEvents[m.id]; });
    const pool = has.length ? has : list;
    return pool.slice(0, limit || 3);
  }

  function masjidCard(masjid, upcomingCount) {
    const lines = [];
    if (masjid.mukim) lines.push(masjid.mukim);
    if (masjid.state) lines.push(masjid.state);
    const kids = [
      ui.el("h3", {}, [masjid.name]),
      ui.el("p", { class: "muted" }, [lines.join(", ") || "—"])
    ];
    if (upcomingCount > 0) {
      kids.push(ui.el("p", { class: "masjid-events" }, [
        upcomingCount + " acara akan datang"
      ]));
    }
    return ui.el("a", {
      class: "masjid-card",
      href: "masjid/" + encodeURIComponent(masjid.id) + "/",
      "aria-label": masjid.name
    }, kids);
  }

  // Search + filter for the directory page. q matches name/mukim/address;
  // mukim and optional hasEvents restrict the set.
  function filterMasjids(q, opts) {
    opts = opts || {};
    q = (q || "").trim().toLowerCase();
    return list.filter(function (m) {
      if (opts.mukim && m.mukim !== opts.mukim) return false;
      if (opts.masjid_id && m.id !== opts.masjid_id) return false;
      if (q) {
        const hay = [m.id, m.name, m.mukim, m.state, m.address].join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  // Distinct mukim values, sorted alphabetically (for a filter dropdown).
  function mukims() {
    const out = [];
    list.forEach(function (m) {
      if (m.mukim && out.indexOf(m.mukim) === -1) out.push(m.mukim);
    });
    return out.sort();
  }

  function renderGrid(container, masjids, counts) {
    container.textContent = "";
    if (!masjids.length) {
      container.appendChild(ui.el("p", { class: "empty-state" }, [
        "Tiada masjid ditemui. Cuba ubah carian atau penapis mukim."
      ]));
      return;
    }
    const grid = ui.el("div", { class: "masjid-grid" });
    masjids.forEach(function (m) {
      grid.appendChild(masjidCard(m, (counts && counts[m.id]) || 0));
    });
    container.appendChild(grid);
  }

  ME.masjids = {
    init: init,
    get: get,
    list: function () { return list; },
    featured: featured,
    card: masjidCard,
    filterMasjids: filterMasjids,
    mukims: mukims,
    renderGrid: renderGrid
  };
})();