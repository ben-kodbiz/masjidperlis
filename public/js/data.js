/* DataLoader — loads canonical JSON used by the public site.
   Data path is configurable so the same JS works from GitHub Pages
   and local static servers. */

(function () {
  "use strict";

  window.MasjidEvents = window.MasjidEvents || {};
  const ME = window.MasjidEvents;

  const FILES = ["events", "masjids", "speakers", "categories", "settings"];

  let basePath = ME.dataPath || "data";

  // Resolve the base path. If the page lives under a sub-path (e.g. GitHub
  // Pages project sites), relative "data/…" still resolves from the page URL,
  // so we can keep it as a relative path for portability.
  function pathFor(file) {
    return basePath + "/" + file + ".json";
  }

  let cache = null;
  let inflight = null;

  function fetchAll() {
    if (inflight) return inflight;
    inflight = Promise.all(
      FILES.map(function (name) {
        return fetch(pathFor(name)).then(function (res) {
          if (!res.ok) throw new Error(name + " failed (" + res.status + ")");
          return res.json();
        });
      })
    ).then(function (results) {
      const data = {};
      FILES.forEach(function (name, i) {
        data[name] = results[i];
      });
      cache = data;
      return data;
    }).catch(function (err) {
      inflight = null;
      cache = null;
      throw err;
    });
    return inflight;
  }

  ME.data = {
    load: fetchAll,
    get: function (name) {
      return cache ? cache[name] : null;
    },
    reload: function () {
      cache = null;
      inflight = null;
      return fetchAll();
    }
  };
})();