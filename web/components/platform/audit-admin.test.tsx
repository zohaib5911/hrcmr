// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AuditAdmin } from "./audit-admin";
import { auditFilters, pageOffset } from "@/lib/platform/operations";
beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.configured.test/api/v1"));
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});
it("shares normalized action, actor and inclusive UTC dates between results, paging and CSV", () => {
  const filters = auditFilters({
    action: " platform. ",
    actor_type: "platform_admin",
    since: "2026-11-01",
    until: "2026-11-02",
  });
  expect(filters).toEqual({
    action: "platform.",
    actor_type: "platform_admin",
    since: "2026-11-01T00:00:00Z",
    until: "2026-11-02T23:59:59.999999Z",
  });
  render(
    <AuditAdmin
      filters={filters}
      offset={50}
      data={{
        items: [
          {
            id: "a1",
            created_at: "2026-11-01T10:00:00Z",
            actor_type: "platform_admin",
            actor: "admin@example.test",
            action: "platform.job_rerun",
            entity_type: "job",
            entity_id: null,
            summary: "Re-run job",
            reason: "Investigate failure",
            request_id: null,
          },
        ],
        total: 101,
      }}
    />,
  );
  expect(screen.getByText("admin@example.test")).toBeInTheDocument();
  for (const name of ["Export CSV", "Previous", "Next"]) {
    const url = new URL(
      screen.getByRole("link", { name }).getAttribute("href")!,
      "http://admin.test",
    );
    for (const [k, v] of Object.entries(filters)) expect(url.searchParams.get(k)).toBe(v);
    if (name === "Export CSV") {
      expect(screen.getByRole("link", { name }).getAttribute("href")).toMatch(
        /^https:\/\/api\.configured\.test\/api\/v1\/platform\/audit\/export\?/,
      );
      expect(url.pathname).toBe("/api/v1/platform/audit/export");
      expect(url.searchParams.has("offset")).toBe(false);
    }
  }
  expect(screen.getByRole("button", { name: "Apply filters" }).closest("form")).toHaveAttribute(
    "method",
    "get",
  );
});
it("handles empty and failed loads", () => {
  const { rerender } = render(
    <AuditAdmin data={{ items: [], total: 0 }} filters={{}} offset={0} />,
  );
  expect(screen.getByText("No audit events match these filters.")).toBeInTheDocument();
  rerender(<AuditAdmin data={null} filters={{}} offset={0} />);
  expect(screen.getByText("Could not load audit log")).toBeInTheDocument();
});
it("rejects malformed filters and offsets", () => {
  expect(auditFilters({ actor_type: "owner", since: "wrong", until: ["2026-11-01"] })).toEqual({});
  for (const n of ["-1", "NaN", "1.5", "100001"]) expect(pageOffset(n)).toBe(0);
  expect(pageOffset("50")).toBe(50);
});
