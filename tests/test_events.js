#!/usr/bin/env node
/* Tests for public/js/events.js pure logic (filtering, recurrence, upcoming).
   Run directly with Node (no browser required):
       node tests/test_events.js
*/

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

// --- Load public/js modules into a stubbed window context ---
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
  console: console,
  URLSearchParams: URLSearchParams,
  Intl: Intl,
  require: require
};
window.MasjidEvents = {};

loadModule("ui.js");
loadModule("events.js");

const ME = window.MasjidEvents;

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error("  FAIL: " + msg); }
}

const events = [
  { id: "e1", title: "Kuliyyah", masjid_id: "m1", date: "2026-08-09", start_time: "20:00", status: "published" },
  { id: "e2", title: "Ceramah", masjid_id: "m2", date: "2026-08-09", start_time: "21:00", status: "cancelled" },
  { id: "e3", title: "Draft", masjid_id: "m1", date: "2026-08-10", start_time: "09:00", status: "draft" },
  { id: "e4", title: "Recurring Sun", masjid_id: "m1", date: "2026-08-02", start_time: "10:00", status: "published",
    recurrence: { type: "weekly", days: ["sunday"], start_date: "2026-08-02", end_date: null } },
  { id: "e5", title: "Postponed", masjid_id: "m2", date: "2026-08-11", start_time: "15:00", status: "postponed" },
  { id: "e6", title: "Recurring Wed", masjid_id: "m2", date: "2026-08-12", start_time: "14:00", status: "published",
    recurrence: { type: "weekly", days: ["wednesday"], start_date: "2026-08-12", end_date: null } },
  { id: "e7", title: "Recurring Wed (exceptions)", masjid_id: "m2", date: "2026-08-12", start_time: "15:00", status: "published",
    recurrence: { type: "weekly", days: ["wednesday"], start_date: "2026-08-12", end_date: null, exceptions: ["2026-08-26"] } }
];

console.log("events module tests:");

// visible filtering
assert(ME.events.isVisible(events[0]), "published visible");
assert(ME.events.isVisible(events[1]), "cancelled visible");
assert(!ME.events.isVisible(events[2]), "draft not visible");
assert(ME.events.isVisible(events[4]), "postponed visible");

// occurrence on a holiday date: 2026-08-09 is a Sunday
const today = ME.events.occurrencesOn(events, "2026-08-09");
assert(today.length === 3, "on 2026-08-09: base(e1,e2) + recurring(e4) = 3, got " + today.length);

// filterEvents: cancelled-less, by masjid, by category, date bounds
let filt = ME.events.filterEvents(events, {});
assert(filt.length === 6, "filters out draft: got " + filt.length);

filt = ME.events.filterEvents(events, { masjid: "m1" });
assert(filt.length === 2, "masjid m1 filtered: got " + filt.length);

filt = ME.events.filterEvents(events, { from: "2026-08-10" });
assert(filt.length === 3 && filt[0].id === "e5" && filt[1].id === "e6" && filt[2].id === "e7",
  "from 2026-08-10 leaves posted e5,e6,e7, got " + filt.length);

filt = ME.events.filterEvents(events, { q: "ceramah" });
assert(filt.length === 1 && filt[0].id === "e2", "search 'ceramah' finds e2");

// upcoming: bounded and correct
const upc = ME.events.upcoming(events, "2026-08-09", 10);
assert(upc.length >= 1, "upcoming non-empty");
assert(upc.every(function (o) { return o.status !== "draft"; }), "no drafts in upcoming");

// upcoming with masjid filter
const m1up = ME.events.upcoming(events, "2026-08-09", 10, { masjid: "m1" });
assert(m1up.every(function (o) { return o.masjid_id === "m1"; }), "masjid filter respected");

// filterEvents date-range (from/to): only event between dates
const ranged = ME.events.filterEvents(events, { from: "2026-08-10", to: "2026-08-11" });
assert(ranged.length === 1 && ranged[0].id === "e5",
  "date range 08-10..08-11 -> only e5, got " + ranged.length);

const ranged2 = ME.events.filterEvents(events, { from: "2026-08-09", to: "2026-08-09" });
assert(ranged2.length === 2, "date range 08-09..08-09 -> e1,e2, got " + ranged2.length);

// status filter catches cancelled and postponed
const cancelledOnly = ME.events.filterEvents(events, { status: "cancelled" });
assert(cancelledOnly.length === 1 && cancelledOnly[0].id === "e2", "status=cancelled -> e2");
const postponedOnly = ME.events.filterEvents(events, { status: "postponed" });
assert(postponedOnly.length === 1 && postponedOnly[0].id === "e5", "status=postponed -> e5");

// rangeEvents style open-ended horizon produces sane, bounded results
const openEnded = ME.events.upcoming(events, "2026-08-09", 100);
assert(openEnded.length <= 100 && openEnded.length >= 1, "upcoming is bounded");

// status notices / visibility for cancelled and postponed display logic
assert(ME.events.statusNotice(events[1]).length > 0, "cancelled returns a notice");
assert(!ME.events.statusNotice(events[0]), "published returns no notice");

// range(): closed date window collects distinct occurrences in order
const rng = ME.events.range(events, "2026-08-09", "2026-08-12");
const rngIds = rng.map(function (o) { return o.id + "@" + o._occurrenceDate; });
assert(rng.length >= 3, "range 09..12 has at least 3 occurrences: got " + rng.length);
assert(new Set(rngIds).size === rngIds.length, "range returns distinct occurrences");
assert(rngIds.indexOf("e4@2026-08-09") !== -1, "recurring e4 appears on the 9th");
assert(rngIds.indexOf("e6@2026-08-12") !== -1, "recurring e6 appears on the 12th");
assert(rngIds.indexOf("e2@2026-08-09") !== -1, "cancelled e2 appears within range");

// range(): open-ended still bounded and non-empty
const oe = ME.events.range(events, "2026-08-09", null, 50);
assert(oe.length <= 50 && oe.length >= 1, "open-ended range bounded, got " + oe.length);

// --- Stage 6: search across masjid/speaker/category names ---
ME.masjids = ME.masjids || {};
ME.masjids.get = function (id) {
  return { m1: { name: "Masjid Alwi" }, m2: { name: "Masjid An-Nur" } }[id] || null;
};
ME.speakers = ME.speakers || {};
ME.speakers.get = function (id) {
  return { s1: { name: "Ustaz Ahmad" }, s2: { name: "Ustazah Siti" } }[id] || null;
};
ME.categories = ME.categories || {};
ME.categories.get = function (id) {
  return { c1: { name: "Ceramah" }, c2: { name: "Tazkirah" } }[id] || null;
};

// searchText includes masjid, speaker and category names
const evSearch = { id: "es1", masjid_id: "m1", speaker_id: "s2", category_id: "c2", title: "Kuliyyah", date: "2026-08-09" };
const st = ME.events.searchText(evSearch);
assert(st.indexOf("masjid alwi") !== -1, "searchText includes masjid name");
assert(st.indexOf("ustazah siti") !== -1, "searchText includes speaker name");
assert(st.indexOf("tazkirah") !== -1, "searchText includes category name");

// filterEvents matches on masjid name via q
let qf = ME.events.filterEvents(events, { q: "an-nur" });
assert(qf.every(function (o) { return o.masjid_id === "m2"; }),
  "q 'an-nur' matches by masjid name, got " + qf.map(function (o) { return o.id; }).join(","));

// mukim filter (masjid lookup again)
ME.masjids.get = function (id) {
  return { m1: { mukim: "Kangar" }, m2: { mukim: "Arau" } }[id] || null;
};
let df = ME.events.filterEvents(events, { mukim: "Kangar" });
assert(df.length === 2 && df.every(function (o) { return o.masjid_id === "m1"; }),
  "mukim Kangar returns only m1 events, got " + df.length);

// --- Stage 10: recurrence exceptions (cancel individual occurrences) ---
// e7 recurs weekly on Wednesdays from 2026-08-12, with 2026-08-26 excluded.
const e7 = events[6];

// Normal Wednesday occurrence still appears.
const occAug26 = ME.events.occurrencesOn(events, "2026-08-26");
assert(occAug26.filter(function (o) { return o.id === "e7"; }).length === 0,
  "exception date 2026-08-26 omits e7");

const occAug19 = ME.events.occurrencesOn(events, "2026-08-19");
assert(occAug19.filter(function (o) { return o.id === "e7"; }).length === 1,
  "non-exception Wednesday 2026-08-19 still has e7");

const occAug12 = ME.events.occurrencesOn(events, "2026-08-12");
assert(occAug12.filter(function (o) { return o.id === "e7"; }).length === 1,
  "base Wednesday still has e7");

// isExceptionDate helper
assert(ME.events.isExceptionDate(e7, "2026-08-26"), "isExceptionDate true for excluded date");
assert(!ME.events.isExceptionDate(e7, "2026-08-19"), "isExceptionDate false for normal date");
assert(!ME.events.isExceptionDate(events[0], "2026-08-26"), "isExceptionDate false without recurrence");

// upcoming() never surfaces an exception occurrence
const up = ME.events.upcoming(events, "2026-08-19", 50);
assert(up.filter(function (o) { return o.id === "e7" && o._occurrenceDate === "2026-08-26"; }).length === 0,
  "upcoming skips exception occurrences");

console.log("\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);