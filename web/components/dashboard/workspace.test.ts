import { existsSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { STEP_LINKS } from "./workspace";

describe("set-up checklist links (C6.1.12)", () => {
  it("has a page for every step the API sends", () => {
    expect(Object.keys(STEP_LINKS).sort()).toEqual([
      "company_details",
      "departments_locations",
      "first_employee",
      "first_rtw",
      "key_personnel",
    ]);
  });

  it("points each step at a page that exists", () => {
    for (const href of Object.values(STEP_LINKS)) {
      const page = path.join(process.cwd(), "app", "(app)", href, "page.tsx");
      expect(existsSync(page), href).toBe(true);
    }
  });
});
