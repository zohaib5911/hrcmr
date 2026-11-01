import { describe, expect, it } from "vitest";

import { MARKETING_STYLES, RADII, TYPE_STYLES } from "./design/catalog";
import { cn } from "./utils";

describe("cn keeps a text size and a text colour together", () => {
  // tailwind-merge only knows Tailwind's own sizes. Without help it reads `text-callout` as a colour
  // and throws away the real colour, which turned every filled button's label black.
  it("keeps both when one is a size from the design scale and the other a colour token", () => {
    expect(cn("text-on-accent", "text-callout")).toBe("text-on-accent text-callout");
    expect(cn("text-callout", "text-label-secondary")).toBe("text-callout text-label-secondary");
    expect(cn("text-footnote text-danger mt-1.5")).toBe("text-footnote text-danger mt-1.5");
  });

  it.each([...TYPE_STYLES, ...MARKETING_STYLES].map((style) => [style.utility] as const))(
    "treats %s as a size, so a later size replaces it and a colour does not",
    (utility) => {
      expect(cn(utility, "text-label")).toBe(`${utility} text-label`);
      expect(cn("text-body", utility)).toBe(utility === "text-body" ? "text-body" : utility);
    },
  );

  it("still lets a later colour replace an earlier one", () => {
    expect(cn("text-label", "text-danger")).toBe("text-danger");
    expect(cn("bg-accent", "bg-fill-secondary")).toBe("bg-fill-secondary");
  });
});

describe("cn knows the design system's radius and shadow names", () => {
  it.each(RADII.map((radius) => [radius.utility] as const))(
    "%s replaces another radius",
    (utility) => {
      expect(cn("rounded-card", utility)).toBe(utility);
    },
  );

  it("lets a later elevation replace an earlier one", () => {
    expect(cn("shadow-e1", "shadow-e3")).toBe("shadow-e3");
  });

  it("does not confuse a shadow with a colour", () => {
    expect(cn("shadow-e1", "text-label")).toBe("shadow-e1 text-label");
  });
});
