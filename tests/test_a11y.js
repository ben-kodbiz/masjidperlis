#!/usr/bin/env node
/* Tests for the accessibility helper exposed by public/js/ui.js
   (resultCountMessage). Run directly with Node (no browser required):
       node tests/test_a11y.js
*/

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const window = {};
const sandbox = {
  window: window,
  document: {
    createElement: () => ({
      setAttribute() {}, addEventListener() {}, appendChild() {}, removeAttribute() {},
      style: {}, classList: { add() {}, remove() {}, contains() { return false; } }
    })
  },
  console: console,
  Intl: Intl,
  require: require
};
window.MasjidEvents = {};

const src = fs.readFileSync(path.join(__dirname, "..", "public", "js", "ui.js"), "utf8");
vm.runInNewContext(src, sandbox, { filename: "ui.js" });

const ui = window.MasjidEvents.ui;

let failed = 0;
let passed = 0;

function assert(cond, msg) {
  if (cond) { passed++; } else { failed++; console.log("FAIL " + msg); }
}

assert(ui.resultCountMessage(0) === "Tiada acara ditemui.", "zero count");
assert(ui.resultCountMessage(1) === "1 acara dipaparkan.", "singular count");
assert(ui.resultCountMessage(12) === "12 acara dipaparkan.", "plural count");
assert(typeof ui.resultCountMessage === "function", "exported function");

console.log(`resultCountMessage module tests:\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);