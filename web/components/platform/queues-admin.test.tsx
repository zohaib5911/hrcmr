// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
    expect(last?.[1].params.query).toEqual({ limit: 50, offset: 0, status: "completed" });
  });

  it("pages each list independently and resets the offset on a filter change", async () => {
    get.mockImplementation(async (path: string) =>
      path === "/platform/deletion-requests"
        ? { data: { items: [deletion], total: 120 } }
        : { data: { items: [], total: 0 } },
    );
    render(<QueuesAdmin />);
    await screen.findByText("Acme Care");
    const next = screen.getAllByRole("button", { name: "Next" });
    expect(next[1]).toBeDisabled();
    await userEvent.click(next[0]!);
    await waitFor(() => {
      const last = get.mock.calls.filter((c) => c[0] === "/platform/deletion-requests").at(-1);
      expect(last?.[1].params.query).toEqual({ limit: 50, offset: 50 });
    });
    const exportCalls = get.mock.calls.filter((c) => c[0] === "/platform/data-exports");
    expect(exportCalls).toHaveLength(1);
    await screen.findByText("Acme Care");
    await userEvent.selectOptions(screen.getAllByLabelText("Status")[0]!, "scheduled");
    await waitFor(() => {
      const last = get.mock.calls.filter((c) => c[0] === "/platform/deletion-requests").at(-1);
      expect(last?.[1].params.query).toEqual({ limit: 50, offset: 0, status: "scheduled" });
    });
  });

  it("pages data exports and shows an error for a failed page", async () => {
    const exp = {
      id: "x1",
      company_name: "Beta Care",
      status: "ready",
      requested_at: "2026-11-01T10:00:00Z",
      finished_at: null,
      error_code: null,
    };
    let calls = 0;
    get.mockImplementation(async (path: string) => {
      if (path !== "/platform/data-exports") return { data: { items: [], total: 0 } };
      calls += 1;
      return calls === 1
        ? { data: { items: [exp], total: 70 } }
        : { error: { code: "SERVER", message: "Export page failed" } };
    });
    render(<QueuesAdmin />);
    await screen.findByText("Beta Care");
    await userEvent.click(screen.getAllByRole("button", { name: "Next" })[1]!);
    expect(await screen.findByText("Export page failed")).toBeInTheDocument();
    const last = get.mock.calls.filter((c) => c[0] === "/platform/data-exports").at(-1);
    expect(last?.[1].params.query).toEqual({ limit: 50, offset: 50 });
  });
});

describe("QueuesAdmin expired platform session", () => {
  it.each(["UNAUTHENTICATED", "FORBIDDEN"])("returns to the start page on %s", async (code) => {
    const replace = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace });
    get.mockResolvedValue({ error: { code, message: "no" } });
    render(<QueuesAdmin />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/session?next=%2Fqueues"));
    vi.unstubAllGlobals();
  });
});
