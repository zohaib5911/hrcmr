import { describe, expect, it } from "vitest";

import { expiryText } from "./compliance";

describe("expiryText", () => {
  it("says what each state means, with the date written out", () => {
    expect(expiryText("missing", null)).toBe("Missing");
    expect(expiryText("current", null)).toBe("Current, no expiry");
    expect(expiryText("current", "2027-03-01")).toBe("Current until 1 Mar 2027");
    expect(expiryText("expiring", "2026-12-03")).toBe("Expires 3 Dec 2026");
    expect(expiryText("expired", "2026-11-03")).toBe("Expired 3 Nov 2026");
  });
});
