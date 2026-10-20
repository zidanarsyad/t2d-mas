import test from "node:test";
import assert from "node:assert/strict";
import { toCsv } from "./exportFile.js";

test("toCsv quotes every value and escapes quotes", () => {
  assert.equal(toCsv([["day", "note"], ["Sep 1", 'said "hi", twice'], [3, null]]), '"day","note"\n"Sep 1","said ""hi"", twice"\n"3",""');
});
