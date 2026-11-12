// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { QueuesAdmin } from "./queues-admin";

const get = vi.fn();

vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ GET: get });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

const deletion = {
  id: "d1",
  company_id: "c1",
  company_name: "Acme Care",
  status: "scheduled",
  requested_at: "2026-11-01T10:00:00Z",
  scheduled_for: "2026-12-01T10:00:00Z",
  withdrawn_at: null,
  completed_at: null,
  export_requested: true,
};

beforeEach(() => {
  get.mockImplementation(async (path: string) =>
    path === "/platform/deletion-requests"
      ? { data: { items: [deletion], total: 1 } }
      : { data: { items: [], total: 0 } },
  );
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("QueuesAdmin", () => {
  it("lists deletion requests and shows the empty state for exports", async () => {
    render(<QueuesAdmin />);
    expect(await screen.findByText("Acme Care")).toBeInTheDocument();
    expect(await screen.findByText("No data exports.")).toBeInTheDocument();
  });

  it("asks the API for the chosen status", async () => {
    render(<QueuesAdmin />);
    await screen.findByText("Acme Care");
    await userEvent.selectOptions(screen.getAllByLabelText("Status")[0]!, "completed");
    await screen.findByText("Acme Care");
    const last = get.mock.calls.filter((c) => c[0] === "/platform/deletion-requests").at(-1);
    expect(last?.[1].params.query).toEqual({ status: "completed" });
  });
});
