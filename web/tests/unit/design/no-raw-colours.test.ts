/**
 * The Tailwind default palette is switched off (globals.css: `--color-*: initial`), so a class such as
 * `bg-white` or `text-blue-500` generates NOTHING and the element silently loses its colour. A switch
 * thumb went invisible that way. This scans the source for such classes, so the next one fails here
 * instead of in a screenshot.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(import.meta.dirname, "../../..");
const SCAN = ["app", "components", "lib"];
const EXTENSIONS = new Set([".tsx", ".ts"]);

const PALETTE =
  "(?:white|black|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-\\d{2,3})?)";
const PREFIX =
  "(?:bg|text|border|ring|outline|fill|stroke|from|to|via|divide|decoration|caret|placeholder|shadow)";
// A class name, with any variants in front ("hover:", "dark:", "md:").
const RAW_COLOUR = new RegExp(`(?<![\\w-])${PREFIX}-${PALETTE}(?![\\w-])(?:/\\d+)?`, "g");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (name === "node_modules" || name === ".next" || name === "schema.ts") return [];
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return EXTENSIONS.has(path.extname(name)) &&
      !name.endsWith(".test.ts") &&
      !name.endsWith(".test.tsx") &&
      !name.endsWith(".spec.ts")
      ? [full]
      : [];
  });
}

describe("no class uses the disabled Tailwind palette", () => {
  const files = SCAN.flatMap((dir) => sourceFiles(path.join(ROOT, dir)));

  it("scans a meaningful number of files", () => {
    expect(files.length).toBeGreaterThan(40);
  });

  it("finds none", () => {
    const found = files.flatMap((file) =>
      [...readFileSync(file, "utf8").matchAll(RAW_COLOUR)].map(
        (match) => `${path.relative(ROOT, file)}: ${match[0]}`,
      ),
    );
    expect(found).toEqual([]);
  });

  it("would notice one (the pattern itself works)", () => {
    expect("bg-white hover:text-blue-500 ring-red-500/40 border-black".match(RAW_COLOUR)).toEqual([
      "bg-white",
      "text-blue-500",
      "ring-red-500/40",
      "border-black",
    ]);
    // Design tokens that merely contain a colour word must not be flagged.
    expect(
      "bg-accent text-label text-on-accent bg-success-tint border-separator".match(RAW_COLOUR),
    ).toBeNull();
  });
});
