// Architecture guards from the cleanup plan: one HTTP client, one event stream,
// and no policy thresholds hard-coded in the UI (they come from GET /policy).
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = dirname(fileURLToPath(import.meta.url));
const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => (entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)]));
const files = walk(SRC)
  .filter((file) => /\.(js|jsx)$/.test(file) && !file.endsWith(".test.js"))
  .map((file) => ({ name: relative(SRC, file).replaceAll("\\", "/"), text: readFileSync(file, "utf8") }));

test("only api.js calls fetch", () => {
  assert.deepEqual(files.filter((file) => /\bfetch\(/.test(file.text)).map((file) => file.name), ["api.js"]);
});

test("only useLiveEvents opens an EventSource", () => {
  assert.deepEqual(files.filter((file) => /new EventSource/.test(file.text)).map((file) => file.name), ["hooks/useLiveEvents.js"]);
});

test("pages and components contain no threshold literals", () => {
  const offenders = files
    .filter((file) => /^(pages|components)\//.test(file.name))
    .flatMap((file) => (file.text.match(/(?<![\d.])0\.(70|60|85|30)(?!\d)/g) || []).map((literal) => `${file.name}: ${literal}`));
  assert.deepEqual(offenders, []);
});

test("Tailwind is gone", () => {
  const pkg = JSON.parse(readFileSync(join(SRC, "..", "package.json"), "utf8"));
  const deps = { ...pkg.dependencies, ...pkg.devDependencies };
  assert.ok(!Object.keys(deps).some((name) => name.includes("tailwind")));
  assert.ok(!readFileSync(join(SRC, "styles.css"), "utf8").includes("tailwind"));
  assert.ok(!readFileSync(join(SRC, "..", "vite.config.js"), "utf8").includes("tailwind"));
});
