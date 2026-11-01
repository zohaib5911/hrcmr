import { describe, expect, it } from "vitest";

import { STATUSES, statusTone } from "./status";

describe("status chips", () => {
  it("maps the plan's statuses to a tone and a label", () => {
    expect(STATUSES.verified).toEqual({ tone: "success", label: "Verified" });
    expect(STATUSES.expiring).toEqual({ tone: "warning", label: "Expiring" });
    expect(STATUSES.expired).toEqual({ tone: "danger", label: "Expired" });
    expect(STATUSES.pending).toEqual({ tone: "info", label: "Pending" });
    expect(STATUSES["not-recorded"]).toEqual({ tone: "neutral", label: "Not recorded" });
    expect(STATUSES.draft.tone).toBe("neutral");
    expect(STATUSES.open.tone).toBe("info");
    expect(STATUSES.closed.tone).toBe("neutral");
  });

  it("never leaves a status without a text label (colour alone is not allowed, plan 5.11)", () => {
    for (const [key, status] of Object.entries(STATUSES)) {
      expect(status.label.length, key).toBeGreaterThan(2);
    }
  });

  it("looks a status up safely", () => {
    expect(statusTone("verified")).toBe("success");
    expect(statusTone("something-new")).toBe("neutral");
  });
});
