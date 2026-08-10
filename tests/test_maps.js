#!/usr/bin/env node
/* Tests for public/js/maps.js (zero-key mapping URL builders).
   Run directly with Node (no browser required):
       node tests/test_maps.js
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
const sandbox = { window: window, console: console };
window.MasjidEvents = {};

loadModule("maps.js");
const ME = window.MasjidEvents;

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error("  FAIL: " + msg); }
}

const LAT = 6.4405;
const LON = 100.1952;

const osm = ME.maps.osmUrl(LAT, LON);
assert(osm.indexOf("https://www.openstreetmap.org/") === 0, "osmUrl points at openstreetmap.org");
assert(osm.indexOf("mlat=6.4405") !== -1 && osm.indexOf("mlon=100.1952") !== -1, "osmUrl uses coordinates");

const waze = ME.maps.wazeUrl(LAT, LON);
assert(waze.indexOf("https://waze.com/ul?ll=") === 0 && waze.indexOf("navigate=yes") !== -1,
  "wazeUrl is keyless navigate link");

const gmap = ME.maps.googleUrl(LAT, LON);
assert(gmap.indexOf("https://www.google.com/maps/dir/?api=1&destination=6.4405,100.1952") === 0,
  "googleUrl is a plain keyless directions link");

const apple = ME.maps.appleUrl(LAT, LON);
assert(apple.indexOf("https://maps.apple.com/?ll=6.4405,100.1952") === 0, "appleUrl is a point link");

const btns = ME.maps.buttons(LAT, LON);
assert(btns.length === 4, "buttons returns all four providers");
assert(btns[0].label === "OpenStreetMap" && btns[3].label === "Apple Maps", "buttons in stable order");
assert(btns.every(function (b) { return /^https:\/\//.test(b.href); }), "all links are https");
assert(new Set(btns.map(function (b) { return b.href; })).size === 4, "all provider URLs distinct");

console.log("\nmaps module tests:\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);