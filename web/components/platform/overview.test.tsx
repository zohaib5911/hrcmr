// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { PlatformOverview, type PlatformMetrics } from "./overview";

const metrics: PlatformMetrics = {
  generated_at: "2026-11-12T09:00:00Z",
  signups_24h: 3,
  signups_7d: 21,
  companies_active: 12,
  plans_active: { free: 8, annual: 3, ten_year: 1 },
  paid_entitled: 4,
  mrr_pence: 25000,
  arr_pence: 300000,
  churn_30d: 1,
  refunds_30d: 2,
};

beforeAll(() => {
  // KpiCard counts up when seen; jsdom has no IntersectionObserver.
  globalThis.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  } as unknown as typeof IntersectionObserver;
});

describe("PlatformOverview", () => {
  it("shows the figures as cards and links every screen", () => {
    render(<PlatformOverview metrics={metrics} queueWaiting={5} />);
    expect(screen.getByText("Active companies")).toBeInTheDocument();
    expect(screen.getByText("£250.00")).toBeInTheDocument();
    expect(screen.getByText("ARR estimate £3,000.00")).toBeInTheDocument();
    expect(screen.getByText("Job queue depth")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Companies" })).toHaveAttribute("href", "/companies");
    expect(screen.getByRole("link", { name: "Dossier links" })).toHaveAttribute(
      "href",
      "/dossier-links",
    );
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  });
  it("shows an error when the figures are missing, and still links the screens", () => {
    render(<PlatformOverview metrics={null} queueWaiting={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent("could not load");
    expect(screen.getByRole("link", { name: "SOC rules" })).toBeInTheDocument();
  });
});
