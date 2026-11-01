import { describe, expect, it } from "vitest";

import { FOOTER_COLUMNS, HEADER_LINKS, legalLine } from "./marketing-nav";

const none = {
  companyName: null,
  companyNumber: null,
  registeredOffice: null,
  countryOfRegistration: null,
  icoNumber: null,
};

describe("the public website's links", () => {
  it("has four footer columns, and every link is a site path", () => {
    expect(FOOTER_COLUMNS.map((column) => column.title)).toEqual([
      "Product",
      "Resources",
      "Company",
      "Legal",
    ]);
    for (const link of [...HEADER_LINKS, ...FOOTER_COLUMNS.flatMap((column) => column.links)]) {
      expect(link.href).toMatch(/^\/[a-z0-9/-]*$/);
    }
  });
});

describe("legalLine", () => {
  it("shows only what has been supplied", () => {
    expect(legalLine(none, "Brand", 2026)).toBe("© 2026 Brand.");
    expect(
      legalLine(
        {
          companyName: "Example Ltd",
          companyNumber: "01234567",
          registeredOffice: "1 High Street, London",
          countryOfRegistration: "England and Wales",
          icoNumber: "ZA123456",
        },
        "Brand",
        2026,
      ),
    ).toBe(
      "© 2026 Example Ltd. Registered in England and Wales, company number 01234567. Registered office: 1 High Street, London. ICO registration number ZA123456.",
    );
  });
});
