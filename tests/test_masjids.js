#!/usr/bin/env node
/* Tests for public/js/masjids.js pure logic (lookups, featured selection).
   Run directly with Node (no browser required):
       node tests/test_masjids.js
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
  console: console
};
window.MasjidEvents = {};

loadModule("ui.js");
loadModule("masjids.js");

const ME = window.MasjidEvents;

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error("  FAIL: " + msg); }
}

const masjids = [
  { id: "m1", name: "Masjid Alwi", district: "Kangar" },
  { id: "m2", name: "Masjid An-Nur", district: "Kangar" },
  { id: "m3", name: "Masjid A-Rahmah", district: "Arau" }
];

ME.masjids.init({ masjids: masjids });

// get() resolves by id
assert(ME.masjids.get("m1").name === "Masjid Alwi", "get() finds masjid by id");
assert(ME.masjids.get("m-none") === null, "get() returns null for unknown id");

// list() returns all
assert(ME.masjids.list().length === 3, "list returns all masjids");

// featured(): masjids with upcoming events first
const events = [
  { id: "e1", masjid_id: "m2", status: "published" },
  { id: "e2", masjid_id: "m3", status: "published" },
  { id: "e3", masjid_id: "m-none", status: "draft" }
];
const feat = ME.masjids.featured(events, 3);
assert(feat.length === 2, "featured returns only masjids that have events, got " + feat.length);
assert(feat[0].id === "m2" && feat[1].id === "m3",
  "featured prioritises masjids with events, got " + feat.map(function (m) { return m.id; }).join(","));

// featured fallback: no events -> returns first masjids in order
const featNone = ME.masjids.featured([], 2);
assert(featNone.length === 2 && featNone[0].id === "m1", "featured falls back to first entries");

// featured limit is honoured
assert(ME.masjids.featured(events, 1).length === 1, "featured respects limit");

// --- Stage 6: directory search + district filter ---
const byName = ME.masjids.filterMasjids("alwi");
assert(byName.length === 1 && byName[0].id === "m1", "search finds by name");

const byDistrict = ME.masjids.filterMasjids("", { district: "Kangar" });
assert(byDistrict.length === 2 && byDistrict.every(function (m) { return m.district === "Kangar"; }),
  "district filter returns only Kangar masjids");

const byId = ME.masjids.filterMasjids("m3");
assert(byId.length === 1 && byId[0].id === "m3", "search finds by id");

const none = ME.masjids.filterMasjids("tidak-wujud");
assert(none.length === 0, "no matches returns empty array");

const ds = ME.masjids.districts();
assert(ds.length === 2 && ds[0] === "Arau" && ds[1] === "Kangar",
  "districts() returns sorted distinct values");

console.log("\nmasjids module tests:\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);