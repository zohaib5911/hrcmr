import { describe, expect, it } from "vitest";

import { addressLine, labelOf, RELATIONSHIPS } from "./personal";

describe("personal tab helpers", () => {
  it("joins the parts of an address that are set", () => {
    expect(
      addressLine({
        postcode: "SW1A 1AA",
        line1: "1 High Street",
        line2: null,
        line3: null,
        city_county: "London",
        country: null,
      }),
    ).toBe("1 High Street, London, SW1A 1AA");
  });

  it("offers the ten relationships in the plan's words", () => {
    expect(RELATIONSHIPS.map((r) => r.label)).toEqual([
      "Spouse",
      "Civil partner",
      "Partner",
      "Parent",
      "Child",
      "Sibling",
      "Guardian",
      "Other relative",
      "Friend",
      "Other",
    ]);
    expect(labelOf(RELATIONSHIPS, "other_relative")).toBe("Other relative");
  });
});
