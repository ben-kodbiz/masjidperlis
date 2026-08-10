#!/usr/bin/env node
/* Tests for public/js/ics.js (RFC 5545 .ics generation).
   Run directly with Node (no browser required):
       node tests/test_ics.js
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
    createElement: function () { return { setAttribute() {}, click() {} }; },
    body: { appendChild() {}, removeChild() {} }
  },
  console: console
};
window.MasjidEvents = {};

loadModule("ics.js");
const ME = window.MasjidEvents;

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error("  FAIL: " + msg); }
}

const ev = {
  id: "evt-20260809-001",
  title: "Kuliyyah Maghrib: Keutamaan Ilmu",
  masjid_id: "m1",
  speaker_id: "s1",
  date: "2026-08-09",
  start_time: "20:00",
  end_time: "21:00",
  description: "Kuliyyah mingguan selepas solat Maghrib.",
  status: "published"
};

const opts = { now: new Date("2026-08-09T12:00:00Z") };
const ics = ME.ics.eventToIcs(ev, opts);

// Structural validity
assert(ics.indexOf("BEGIN:VCALENDAR\r\n") === 0, "starts with BEGIN:VCALENDAR");
assert(ics.indexOf("END:VCALENDAR\r\n") !== -1, "ends with END:VCALENDAR");
assert(ics.indexOf("VERSION:2.0") !== -1, "has VERSION:2.0");
assert(ics.indexOf("PRODID:") !== -1, "has PRODID");
assert(ics.indexOf("CALSCALE:GREGORIAN") !== -1, "has CALSCALE");

// Core event properties
assert(ics.indexOf("UID:evt-20260809-001@masjidperlis.org") !== -1, "stable UID");
assert(ics.indexOf("SUMMARY:" + ev.title) !== -1, "SUMMARY = title");
assert(ics.indexOf("DTSTAMP:20260809T120000Z") !== -1, "DTSTAMP is UTC Z");
assert(ics.indexOf("DTSTART;TZID=Asia/Kuala_Lumpur:20260809T200000") !== -1,
  "DTSTART anchored to KL timezone");
assert(ics.indexOf("DTEND;TZID=Asia/Kuala_Lumpur:20260809T210000") !== -1,
  "DTEND anchored to KL timezone");
assert(ics.indexOf("STATUS:CONFIRMED") !== -1, "published -> CONFIRMED");
assert(ics.indexOf("LOCATION:") !== -1, "has LOCATION");

// Status mapping
assert(ME.ics.eventToIcs(Object.assign({}, ev, { status: "cancelled" }), opts).indexOf("STATUS:CANCELLED") !== -1,
  "cancelled -> CANCELLED");
assert(ME.ics.eventToIcs(Object.assign({}, ev, { status: "postponed" }), opts).indexOf("STATUS:TENTATIVE") !== -1,
  "postponed -> TENTATIVE");

// Missing end_time defaults to start_time
const noEnd = ME.ics.eventToIcs(Object.assign({}, ev, { end_time: null }), opts);
assert(noEnd.indexOf("DTEND;TZID=Asia/Kuala_Lumpur:20260809T200000") !== -1,
  "no end_time -> DTEND = start_time");

// Text escaping
const escEv = Object.assign({}, ev, { title: "Ceramah: Fiqh, Usul & Dakwah" });
const escIcs = ME.ics.eventToIcs(escEv, opts);
assert(escIcs.indexOf('SUMMARY:Ceramah: Fiqh\\, Usul & Dakwah') !== -1, "commas escaped, ampersand kept");
assert(escIcs.indexOf("BEGIN:VEVENT") !== -1, "single event only");

// Recurrence -> RRULE
const recEv = {
  id: "evt-20260812-001",
  title: "Kuliyyah Mingguan",
  masjid_id: "m1",
  date: "2026-08-12",
  start_time: "20:00",
  end_time: "21:00",
  status: "published",
  recurrence: { type: "weekly", days: ["wednesday"], start_date: "2026-08-12", end_date: null }
};
const recIcs = ME.ics.eventToIcs(recEv, opts);
assert(recIcs.indexOf("RRULE:FREQ=WEEKLY;BYDAY=WE") !== -1, "weekly recurrence has RRULE");
assert(recIcs.indexOf("DTSTART;TZID=Asia/Kuala_Lumpur:20260812T200000") !== -1,
  "recurring DTSTART on base date");

// Recurrence with end_date -> UNTIL
const recEnd = Object.assign({}, recEv, { recurrence: { type: "weekly", days: ["wednesday"], start_date: "2026-08-12", end_date: "2026-09-30" } });
const recEndIcs = ME.ics.eventToIcs(recEnd, opts);
assert(recEndIcs.indexOf("UNTIL=20260930T000000Z") !== -1, "recurrence has UNTIL date");

// rruleFor helper (exported for direct testing)
assert(ME.ics.rruleFor({}) === "", "no recurrence -> empty rrule");

console.log("\nics module tests:\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);