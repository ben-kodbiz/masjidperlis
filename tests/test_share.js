#!/usr/bin/env node
/* Tests for public/js/share.js pure logic (summary + share URLs).
   Run directly with Node (no browser required):
       node tests/test_share.js
*/

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

function loadModule(filename) {
  const src = fs.readFileSync(path.join(__dirname, "..", "public", "js", filename), "utf8");
  vm.runInNewContext(src, sandbox, { filename });
}

const window = {};
const sandbox = {
  window: window,
  document: {
    createElement: function () {
      return {
        setAttribute() {}, addEventListener() {}, appendChild() {}, removeAttribute() {},
        style: {}, classList: { add() {}, remove() {}, contains() { return false; } }
      };
    }
  },
  navigator: {},
  console: console
};
window.location = { protocol: "http:", host: "localhost:8000" };
window.MasjidEvents = {};

loadModule("ui.js");
loadModule("share.js");

const ME = window.MasjidEvents;

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error("  FAIL: " + msg); }
}

// Lookups used by textSummary
ME.masjids = ME.masjids || {};
ME.masjids.get = function (id) {
  return { m1: { name: "Masjid Alwi" } }[id] || null;
};
ME.speakers = ME.speakers || {};
ME.speakers.get = function (id) {
  return { s1: { name: "Ustaz Ahmad" } }[id] || null;
};

const ev = {
  id: "evt-20260809-001",
  title: "Kuliyyah Maghrib: Keutamaan Ilmu",
  masjid_id: "m1",
  speaker_id: "s1",
  category_id: "kuliyyah",
  date: "2026-08-09",
  start_time: "20:00",
  end_time: "21:00",
  description: "Kuliyyah mingguan selepas solat Maghrib.",
  status: "published"
};

const summary = ME.share.textSummary(ev);

// Summary contains the essentials, joined by newlines
assert(summary.indexOf("Kuliyyah Maghrib") !== -1, "summary has title");
assert(summary.indexOf("Masjid Alwi") !== -1, "summary has masjid name");
assert(summary.indexOf("Ustaz Ahmad") !== -1, "summary has speaker name");
assert(summary.indexOf("8:00 PM") !== -1, "summary has formatted time");
assert(summary.indexOf("Kuliyyah mingguan") !== -1, "summary has description");
assert(summary.indexOf("NOTA") === -1, "published events carry no status note");

// Cancelled events append a note
const cancelled = ME.share.textSummary(Object.assign({}, ev, { status: "cancelled" }));
assert(cancelled.indexOf("dibatalkan") !== -1, "cancelled events carry a notice");

// Event URL is absolute + targets the clean canonical page (Stage 11)
const url = ME.share.eventUrl(ev.id);
assert(url === "http://localhost:8000/event/evt-20260809-001/", "eventUrl is absolute + clean");

// Share links encode the payload
const wa = ME.share.whatsappUrl(summary);
assert(wa.indexOf("https://wa.me/?text=") === 0, "whatsappUrl scheme correct");

const tg = ME.share.telegramUrl(summary, url);
assert(tg.indexOf("https://t.me/share/url?url=") === 0, "telegramUrl scheme correct");
assert(tg.indexOf(encodeURIComponent(url)) !== -1, "telegramUrl includes encoded url");
assert(tg.indexOf("&text=") !== -1, "telegramUrl includes text param");

console.log("\nshare module tests:\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);