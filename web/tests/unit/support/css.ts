/**
 * Just enough CSS reading for the design-token tests: find a block by its selector, list its custom
 * properties, and evaluate the few colour forms the tokens use. It is deliberately strict: an
 * unknown form throws, so a token written in a way the tests cannot judge never slips through.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

export const GLOBALS_CSS = readFileSync(
  path.resolve(import.meta.dirname, "../../../app/globals.css"),
  "utf8",
);

/** The text between the braces that follow the first match of `header`. */
export function blockBody(css: string, header: RegExp): string {
  const match = header.exec(css);
  if (!match) throw new Error(`No CSS block matches ${header}`);
  const open = css.indexOf("{", match.index);
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") depth -= 1;
    if (depth === 0) return css.slice(open + 1, i);
  }
  throw new Error(`Unclosed CSS block for ${header}`);
}

/** `--name: value;` pairs in a block body (comments removed). Later duplicates are an error. */
export function declarations(body: string): Map<string, string> {
  const result = new Map<string, string>();
  const clean = body.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const match of clean.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    const [, name, value] = match;
    if (name === undefined || value === undefined) continue;
    if (result.has(name)) throw new Error(`${name} is declared twice in one block`);
    result.set(name, value.trim());
  }
  return result;
}

/** Normal form for comparing values: lower case, tidy spaces, leading zeros on decimals. */
export function normalise(value: string): string {
  return value
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/\s*,\s*/g, ",")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .replace(/(^|[^\d])\.(\d)/g, "$10.$2")
    .trim();
}

export const LIGHT_BLOCK = /:root,\s*\[data-theme="light"\]\s*\{/;
// Top level only: the `dark:` variant near the top of the file has its own, indented media query.
export const SYSTEM_DARK_MEDIA = /^@media \(prefers-color-scheme: dark\)\s*\{/m;
export const SYSTEM_DARK_BLOCK = /:root:not\(\[data-theme\]\)\s*\{/;
export const EXPLICIT_DARK_BLOCK = /^\[data-theme="dark"\]\s*\{/m;

export function themeBlocks(css = GLOBALS_CSS) {
  return {
    light: declarations(blockBody(css, LIGHT_BLOCK)),
    systemDark: declarations(blockBody(blockBody(css, SYSTEM_DARK_MEDIA), SYSTEM_DARK_BLOCK)),
    explicitDark: declarations(blockBody(css, EXPLICIT_DARK_BLOCK)),
  };
}

export { resolveColour, visibleColour } from "../../support/colour";
