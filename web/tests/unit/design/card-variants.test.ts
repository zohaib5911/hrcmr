/**
 * U6.1.4: the dashboard, employee and company pages use only the two card looks in
 * components/ui/card.tsx: glass (CARD_VARIANTS.glass) or solid (CARD_VARIANTS.solid, written out as
 * "bg-elevated rounded-card shadow-e1"). No hand-made card with a hard border creeps back.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { CARD_VARIANTS } from "../../../components/ui/card";

const ROOT = path.resolve(__dirname, "../../../components");
const files = ["dashboard", "employees", "company"].flatMap((dir) =>
  readdirSync(path.join(ROOT, dir))
    .filter((name) => name.endsWith(".tsx") && !name.endsWith(".test.tsx"))
    .map((name) => path.join(dir, name)),
);

describe("one card style (U6.1.4)", () => {
  it("has exactly two variants: glass and solid", () => {
    expect(CARD_VARIANTS).toEqual({
      glass: "material-glass-thin rounded-card",
      solid: "bg-elevated rounded-card shadow-e1",
    });
  });

  it.each(files)("%s draws cards only with a card variant", (file) => {
    const source = readFileSync(path.join(ROOT, file), "utf8");
    for (const [classes] of source.matchAll(/"[^"\n]*\brounded-card\b[^"\n]*"/g)) {
      expect(classes, file).toContain(CARD_VARIANTS.solid);
    }
  });
});
