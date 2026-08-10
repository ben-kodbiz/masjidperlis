/* App — bootstrap: load data, wire page-level rendering, friendly errors. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;
  const ui = ME.ui;

  function showError(container) {
    if (!container) return;
    container.textContent = "";
    container.appendChild(ui.el("div", { class: "error-box" }, [
      ui.el("p", { style: "font-weight:700;margin-bottom:.25rem" }, [
        "Kami menghadapi masalah memuatkan data terbaru."
      ]),
      ui.el("p", { class: "muted" }, ["Sila cuba lagi kemudian."])
    ]));
  }

  function param(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function heading(title) {
    return ui.el("h2", { class: "section-title" }, [title]);
  }

  // ---- Homepage ----
  function renderHome(container, data) {
    const now = ui.todayKL();

    const todayEvs = ME.events.occurrencesOn(data.events, now);
    container.appendChild(heading("Hari Ini"));
    const todayBox = ui.el("div");
    container.appendChild(todayBox);
    ME.events.renderList(todayBox, todayEvs.slice(0, 5));

    const tomorrowEvs = ME.events.occurrencesOn(data.events, ui.addDays(now, 1));
    if (tomorrowEvs.length) {
      container.appendChild(heading("Esok"));
      const tomoBox = ui.el("div");
      container.appendChild(tomoBox);
      ME.events.renderList(tomoBox, tomorrowEvs.slice(0, 5));
    }

    const upcoming = ME.events.upcoming(data.events, now, 6).filter(function (ev) {
      return (ev._occurrenceDate || ev.date) !== now;
    });
    container.appendChild(heading("Akan Datang"));
    const upBox = ui.el("div");
    container.appendChild(upBox);
    ME.events.renderList(upBox, upcoming);

    const featured = ME.masjids.featured(data.events, 3);
    container.appendChild(heading("Masjid Pilihan"));
    const fBox = ui.el("div");
    container.appendChild(fBox);
    ME.masjids.renderGrid(fBox, featured);

    container.appendChild(ui.el("p", {}, [
      ui.el("a", { class: "btn", href: "events.html" }, ["Lihat semua acara"])
    ]));
  }

  // ---- Events listing page ----
  function renderEventsPage(container, data) {
    const today = ui.todayKL();

    // Filters
    const filters = ui.el("div", { class: "filters" });
    const row = ui.el("div", { class: "row" });

    const masjidSel = ui.el("select", { id: "filter-masjid", "aria-label": "Tapis mengikut masjid" },
      [ui.el("option", { value: "" }, ["Semua masjid"])]);
    data.masjids.forEach(function (m) {
      masjidSel.appendChild(ui.el("option", { value: m.id }, [m.name]));
    });

    const catSel = ui.el("select", { id: "filter-category", "aria-label": "Tapis mengikut kategori" },
      [ui.el("option", { value: "" }, ["Semua kategori"])]);
    data.categories.forEach(function (c) {
      catSel.appendChild(ui.el("option", { value: c.id }, [c.name]));
    });

    const statusSel = ui.el("select", { id: "filter-status", "aria-label": "Tapis mengikut status" },
      [
        ui.el("option", { value: "" }, ["Semua status"]),
        ui.el("option", { value: "published" }, ["published"]),
        ui.el("option", { value: "cancelled" }, ["cancelled"]),
        ui.el("option", { value: "postponed" }, ["postponed"])
      ]);

    const districtSel = ui.el("select", { id: "filter-district", "aria-label": "Tapis mengikut daerah" },
      [ui.el("option", { value: "" }, ["Semua daerah"])]);
    const districts = [];
    data.masjids.forEach(function (m) {
      if (m.district && districts.indexOf(m.district) === -1) districts.push(m.district);
    });
    districts.sort().forEach(function (d) {
      districtSel.appendChild(ui.el("option", { value: d }, [d]));
    });

    const fromDate = ui.el("input", {
      id: "filter-from",
      type: "date",
      "aria-label": "Dari tarikh"
    });
    const toDate = ui.el("input", {
      id: "filter-to",
      type: "date",
      "aria-label": "Hingga tarikh"
    });

    row.appendChild(masjidSel);
    row.appendChild(districtSel);
    row.appendChild(catSel);
    row.appendChild(statusSel);

    const dateRow = ui.el("div", { class: "row" });
    dateRow.appendChild(ui.el("div", {}, [
      ui.el("label", { for: "filter-from" }, ["Dari"]),
      fromDate
    ]));
    dateRow.appendChild(ui.el("div", {}, [
      ui.el("label", { for: "filter-to" }, ["Hingga"]),
      toDate
    ]));

    const searchBox = ui.el("input", {
      id: "search",
      type: "search",
      placeholder: "Cari acara, masjid, penceramah…",
      "aria-label": "Cari acara"
    });

    filters.appendChild(ui.el("label", { for: "search" }, ["Carian"]));
    filters.appendChild(searchBox);
    filters.appendChild(row);
    filters.appendChild(dateRow);
    container.appendChild(filters);

    const tabs = ui.el("div", { class: "tabs", role: "group", "aria-label": "Jangka masa" });
    const tabDefs = ["Hari Ini", "Esok", "Minggu Ini", "Akan Datang"];
    const tabButtons = {};
    tabDefs.forEach(function (label) {
      const btn = ui.el("button", { type: "button" }, [label]);
      btn.addEventListener("click", function () { setTab(label); });
      tabButtons[label] = btn;
      tabs.appendChild(btn);
    });
    container.appendChild(tabs);

    const listBox = ui.el("div");
    container.appendChild(listBox);

    function setTab(label) {
      activeTab = label;
      Object.keys(tabButtons).forEach(function (k) {
        tabButtons[k].setAttribute("aria-pressed", String(k === label));
      });

      const explicitFrom = fromDate.value || null;
      const explicitTo = toDate.value || null;

      let events;
      if (explicitFrom || explicitTo) {
        // Explicit date range takes priority over the tab.
        events = ME.events.range(data.events, explicitFrom || today, explicitTo || null, 50);
      } else {
        events = collectForTab(label);
      }
      events = ME.events.filterEvents(events, {
        masjid: masjidSel.value || null,
        district: districtSel.value || null,
        category: catSel.value || null,
        status: statusSel.value || null,
        q: searchBox.value
      });
      ME.events.renderList(listBox, events);
    }

    // Occurrences within [from, to] (to == null means open-ended, capped by 2
    // years). Reuses the shared, tested ME.events.range implementation.

    function collectForTab(label) {
      const today = ui.todayKL();
      if (label === "Hari Ini") {
        return ME.events.occurrencesOn(data.events, today);
      }
      if (label === "Esok") {
        return ME.events.occurrencesOn(data.events, ui.addDays(today, 1));
      }
      if (label === "Minggu Ini") {
        let out = [];
        for (let i = 0; i < 7; i++) {
          out = out.concat(ME.events.occurrencesOn(data.events, ui.addDays(today, i)));
        }
        return out;
      }
      return ME.events.upcoming(data.events, today, 50);
    }

    function refresh() {
      setTab(activeTab);
    }

    let activeTab = "Hari Ini";
    masjidSel.addEventListener("change", refresh);
    districtSel.addEventListener("change", refresh);
    catSel.addEventListener("change", refresh);
    statusSel.addEventListener("change", refresh);
    searchBox.addEventListener("input", refresh);
    fromDate.addEventListener("change", refresh);
    toDate.addEventListener("change", refresh);

    setTab("Hari Ini");
  }

  // ---- Event detail ----
  function renderEventPage(container, data) {
    const id = param("id");
    const ev = data.events.find(function (e) { return e.id === id; });
    if (!ev) {
      showError(container);
      return;
    }
    const masjid = ME.masjids.get(ev.masjid_id);
    const speaker = ev.speaker_id
      ? data.speakers.find(function (s) { return s.id === ev.speaker_id; })
      : null;
    const category = ev.category_id
      ? data.categories.find(function (c) { return c.id === ev.category_id; })
      : null;

    const dl = ui.el("dl", {}, [
      ui.el("dt", {}, ["Tarikh"]),
      ui.el("dd", {}, [ui.formatDate(ev.date)]),
      ui.el("dt", {}, ["Masa"]),
      ui.el("dd", {}, [ui.eventWhen(ev)]),
      ui.el("dt", {}, ["Lokasi"]),
      ui.el("dd", {}, [masjid ? masjid.name : ev.masjid_id])
    ]);
    if (speaker) dl.appendChild(ui.el("dt", {}, ["Penceramah"])), dl.appendChild(ui.el("dd", {}, [speaker.name]));
    if (category) dl.appendChild(ui.el("dt", {}, ["Kategori"])), dl.appendChild(ui.el("dd", {}, [category.name]));
    if (ev.description) dl.appendChild(ui.el("dt", {}, ["Keterangan"])), dl.appendChild(ui.el("dd", {}, [ev.description]));
    if (ev.recurrence) {
      dl.appendChild(ui.el("dt", {}, ["Berulang"]));
      dl.appendChild(ui.el("dd", {}, ["Mingguan (" + ev.recurrence.days.join(", ") + ")"]));
    }
    dl.appendChild(ui.el("dt", {}, ["Status"]));
    dl.appendChild(ui.el("dd", {}, [ME.events.statusBadge(ev.status)]));

    const card = ui.el("article", { class: "detail", "aria-labelledby": "ev-title" }, [
      ui.el("h1", { id: "ev-title" }, [ev.title]),
      (ev.status === "cancelled" || ev.status === "postponed")
        ? ui.el("div", { class: "notice" }, [ME.events.statusNotice(ev)])
        : null,
      dl
    ]);
    container.appendChild(card);

    // ---- Sharing (Stage 7) ----
    const summary = ME.share.textSummary(ev);
    const url = ME.share.eventUrl(ev.id);
    const shareWrap = ui.el("div", { class: "share" });

    const copyLinkBtn = ui.el("button", {
      type: "button",
      class: "btn btn-ghost",
      onclick: function () {
        ME.share.copyText(url).then(function (ok) {
          copyLinkBtn.textContent = ok ? "Pautan disalin" : "Sila salin tapal sendiri";
          setTimeout(function () { copyLinkBtn.textContent = "Salin pautan"; }, 2000);
        });
      }
    }, ["Salin pautan"]);

    const copyTextBtn = ui.el("button", {
      type: "button",
      class: "btn btn-ghost",
      onclick: function () {
        ME.share.copyText(summary + "\n" + url).then(function (ok) {
          copyTextBtn.textContent = ok ? "Teks disalin" : "Sila salin teks sendiri";
          setTimeout(function () { copyTextBtn.textContent = "Salin teks acara"; }, 2000);
        });
      }
    }, ["Salin teks acara"]);

    shareWrap.appendChild(copyLinkBtn);
    shareWrap.appendChild(copyTextBtn);

    const wa = ui.el("a", {
      class: "btn",
      rel: "noopener",
      target: "_blank",
      href: ME.share.whatsappUrl(summary + "\n" + url)
    }, ["Kongsi WhatsApp"]);

    const tg = ui.el("a", {
      class: "btn btn-ghost",
      rel: "noopener",
      target: "_blank",
      href: ME.share.telegramUrl(summary, url)
    }, ["Kongsi Telegram"]);

    shareWrap.appendChild(wa);
    shareWrap.appendChild(tg);

    const nativeBtn = ui.el("button", {
      type: "button",
      class: "btn btn-ghost",
      onclick: function () {
        ME.share.nativeShare({
          title: ev.title,
          text: summary,
          url: url
        }).then(function () {
          nativeBtn.textContent = "Dikongsi";
          setTimeout(function () { nativeBtn.textContent = "Kongsi melalui apl lain"; }, 2000);
        }, function () {
          nativeBtn.textContent = "Kongsi tidak disokong";
          setTimeout(function () { nativeBtn.textContent = "Kongsi melalui apl lain"; }, 2000);
        });
      }
    }, ["Kongsi melalui apl lain"]);

    shareWrap.appendChild(nativeBtn);
    container.appendChild(shareWrap);

    // ---- Calendar (.ics, Stage 8) ----
    const icsWrap = ui.el("div", { class: "share" });
    const calBtn = ui.el("button", {
      type: "button",
      class: "btn",
      onclick: function () {
        ME.ics.downloadIcs(ev, { siteName: (data.settings && data.settings.site_name) || "Masjid Events Perlis" });
        calBtn.textContent = "Kalendar dimuat turun?";
        setTimeout(function () { calBtn.textContent = "Tambah ke kalendar (.ics)"; }, 2000);
      }
    }, ["Tambah ke kalendar (.ics)"]);
    icsWrap.appendChild(calBtn);
    container.appendChild(icsWrap);

    if (masjid) {
      container.appendChild(ui.el("p", {}, [
        ui.el("a", { href: "masjid/" + encodeURIComponent(masjid.id) + "/" }, [
          "Lihat profil " + masjid.name
        ])
      ]));
    }
  }

  // ---- Masjid directory ----
  function renderMasjidsPage(container, data) {
    const today = ui.todayKL();
    const counts = {};
    ME.events.upcoming(data.events, today, 60, {}).forEach(function (ev) {
      counts[ev.masjid_id] = (counts[ev.masjid_id] || 0) + 1;
    });

    const filters = ui.el("div", { class: "filters" });
    const row = ui.el("div", { class: "row" });

    const qBox = ui.el("input", {
      id: "masjid-search",
      type: "search",
      placeholder: "Cari masjid, daerah…",
      "aria-label": "Cari masjid"
    });
    const districtSel = ui.el("select", { id: "filter-district", "aria-label": "Tapis mengikut daerah" },
      [ui.el("option", { value: "" }, ["Semua daerah"])]);
    ME.masjids.districts().forEach(function (d) {
      districtSel.appendChild(ui.el("option", { value: d }, [d]));
    });

    filters.appendChild(ui.el("label", { for: "masjid-search" }, ["Carian"]));
    filters.appendChild(qBox);
    row.appendChild(districtSel);
    filters.appendChild(row);
    container.appendChild(filters);

    const gridBox = ui.el("div");
    container.appendChild(gridBox);

    function refresh() {
      const results = ME.masjids.filterMasjids(qBox.value, {
        district: districtSel.value || null
      });
      ME.masjids.renderGrid(gridBox, results, counts);
    }

    qBox.addEventListener("input", refresh);
    districtSel.addEventListener("change", refresh);
    refresh();
  }

  // ---- Masjid detail ----
  function renderMasjidPage(container, data) {
    const id = param("id");
    const masjid = ME.masjids.get(id);
    if (!masjid) {
      showError(container);
      return;
    }
    container.appendChild(ui.el("h1", {}, [masjid.name]));
    const meta = [masjid.district, masjid.state].filter(Boolean).join(", ");
    if (meta) container.appendChild(ui.el("p", { class: "muted" }, [meta]));
    if (masjid.address) container.appendChild(ui.el("p", {}, [masjid.address]));

    const sub = ui.el("div", { class: "masjid-links" });
    if (masjid.latitude != null && masjid.longitude != null) {
      // Directions / maps — zero-key links to open services (Stage 9).
      ME.maps.buttons(masjid.latitude, masjid.longitude).forEach(function (b, i) {
        sub.appendChild(ui.el("a", {
          class: i === 0 ? "btn" : "btn btn-ghost",
          rel: "noopener",
          target: "_blank",
          href: b.href
        }, [b.label]));
      });
    }
    if (masjid.contact) {
      // Show phone number as a plain, safe text link (no auto-dial unless we
      // can ensure it's a phone number).
      sub.appendChild(ui.el("a", {
        class: "btn btn-ghost",
        href: "tel:" + encodeURIComponent(String(masjid.contact).replace(/[^\d+]/g, ""))
      }, ["Hubungi"]));
    }
    if (masjid.website) {
      sub.appendChild(ui.el("a", {
        class: "btn btn-ghost",
        rel: "noopener",
        target: "_blank",
        href: masjid.website
      }, ["Laman web"]));
    }
    if (sub.childNodes.length) container.appendChild(sub);

    const today = ui.todayKL();
    container.appendChild(heading("Hari Ini"));
    const todayBox = ui.el("div");
    container.appendChild(todayBox);
    ME.events.renderList(todayBox, ME.events.occurrencesOn(data.events, today)
      .filter(function (ev) { return ev.masjid_id === masjid.id; }));

    container.appendChild(heading("Akan Datang"));
    const listBox = ui.el("div");
    container.appendChild(listBox);
    const upcoming = ME.events.upcoming(data.events, today, 10, { masjid: masjid.id })
      .filter(function (ev) {
        return (ev._occurrenceDate || ev.date) > today;
      });
    ME.events.renderList(listBox, upcoming);
  }

  const pages = {
    home: renderHome,
    events: renderEventsPage,
    event: renderEventPage,
    masjids: renderMasjidsPage,
    masjid: renderMasjidPage
  };

  document.addEventListener("DOMContentLoaded", function () {
    const app = document.getElementById("app");
    if (!app) return;
    const page = document.body.dataset.page || "home";
    const renderer = pages[page] || renderHome;

    ME.data.load()
      .then(function (data) {
        ME.masjids.init(data);
        ME.speakers = {
          get: function (id) {
            if (!id) return null;
            return (data.speakers || []).find(function (s) { return s.id === id; }) || null;
          }
        };
        ME.categories = {
          get: function (id) {
            if (!id) return null;
            return (data.categories || []).find(function (c) { return c.id === id; }) || null;
          }
        };
        renderer(app, data);
      })
      .catch(function () {
        showError(app);
      });
  });
})();

// PWA: install the service worker on secure origins only (GitHub Pages). It
// is a progressive enhancement — the app works fine with or without it.
if ("serviceWorker" in navigator && window.location.protocol === "https:") {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("sw.js").catch(function () {
      /* offline support unavailable — app still works */
    });
  });
}