import { describe, expect, it } from "vitest";

import { saveSidebarState } from "./sidebar-dom";

describe("saveSidebarState", () => {
  it("writes the cookie the server reads", () => {
    const target = { cookie: "" };
    saveSidebarState("collapsed", target, true);
    expect(target.cookie).toMatch(/^sidebar=collapsed;/);
  });
});
