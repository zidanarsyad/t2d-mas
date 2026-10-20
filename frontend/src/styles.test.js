// Keeps styles.css and the JSX in step: no CSS class without a user, no JSX class without CSS,
// and colours only inside the two token blocks.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = dirname(fileURLToPath(import.meta.url));
const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => (entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)]));
const css = readFileSync(join(SRC, "styles.css"), "utf8");
const sourceFiles = walk(SRC).filter((file) => /\.(js|jsx)$/.test(file) && !file.endsWith(".test.js"));
const sources = sourceFiles.map((file) => readFileSync(file, "utf8")).join("\n") + readFileSync(join(SRC, "..", "index.html"), "utf8");

// Classes built at runtime from these prefixes (tag-${tone}, is-${state}, arm-${id}...).
const DYNAMIC_PREFIXES = ["tag-", "sev-", "trend-", "notice-", "tone-", "state-", "is-", "kind-", "status-", "decision-", "swatch-", "family-", "arm-"];

function cssClasses(text) {
  const names = new Set();
  const withoutComments = text.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, selector] of withoutComments.matchAll(/([^{}]+)\{/g)) {
    if (selector.trim().startsWith("@")) continue;
    for (const match of selector.matchAll(/\.([a-zA-Z_][\w-]*)/g)) names.add(match[1]);
  }
  return names;
}

/** The text of every className={...} expression, found by counting braces. */
function classExpressions(text) {
  const found = [];
  let start = text.indexOf("className={");
  while (start !== -1) {
    let depth = 0;
    let index = start + "className=".length;
    for (; index < text.length; index += 1) {
      if (text[index] === "{") depth += 1;
      if (text[index] === "}") depth -= 1;
      if (depth === 0) break;
    }
    found.push(text.slice(start + "className={".length, index));
    start = text.indexOf("className={", index);
  }
  return found;
}

function jsxClassTokens(text) {
  const tokens = new Set();
  const add = (chunk) =>
    chunk
      .split(/\s+/)
      .filter((token) => /^[a-zA-Z][\w-]*$/.test(token) && !token.endsWith("-"))
      .forEach((token) => tokens.add(token));
  for (const [, value] of text.matchAll(/className="([^"]*)"/g)) add(value);
  for (const raw of classExpressions(text)) {
    // Strings that are compared or looked up are not class names: `state === "done"`, `set.has("x")`.
    const expression = raw
      .replace(/[=!]==\s*"[^"]*"/g, "")
      .replace(/"[^"]*"\s*[=!]==/g, "")
      .replace(/\.(has|includes)\(\s*"[^"]*"\s*\)/g, "")
      // A ${...} glued to a prefix (sev-${x}) only adds a suffix, so its strings are not classes.
      .replace(/([\w-])\$\{[^}]*\}/g, "$1");
    for (const [, template] of expression.matchAll(/`([^`]*)`/g)) {
      add(template.replace(/\$\{[^}]*\}/g, " "));
      for (const [, inner] of template.matchAll(/\$\{([^}]*)\}/g)) for (const [, value] of inner.matchAll(/"([^"]*)"/g)) add(value);
    }
    for (const [, value] of expression.replace(/`[^`]*`/g, "").matchAll(/"([^"]*)"/g)) add(value);
  }
  return tokens;
}

const defined = cssClasses(css);

test("every class used in JSX has a CSS rule", () => {
  const missing = sourceFiles.flatMap((file) => [...jsxClassTokens(readFileSync(file, "utf8"))].filter((token) => !defined.has(token)).map((token) => `${file.slice(SRC.length + 1)}: ${token}`));
  assert.deepEqual(missing, []);
});

test("every CSS class is used somewhere", () => {
  const unused = [...defined].filter((name) => {
    if (DYNAMIC_PREFIXES.some((prefix) => name.startsWith(prefix))) return false;
    return !new RegExp(`(^|[^\\w-])${name}([^\\w-]|$)`).test(sources);
  });
  assert.deepEqual(unused, []);
});

test("hex colours appear only in the light and dark token blocks", () => {
  const outside = css.replace(/:root\s*\{[\s\S]*?\n\}/, "").replace(/:root\[data-theme="dark"\]\s*\{[\s\S]*?\n\}/, "");
  assert.deepEqual(outside.match(/#[0-9a-fA-F]{3,8}\b/g) || [], []);
});

test("the CSS stays small", () => {
  assert.ok(css.length < 60000, `styles.css is ${css.length} bytes`);
});
