// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContactAdmin } from "./contact-admin";

const get = vi.fn();
const patch = vi.fn();

vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ GET: get, PATCH: patch });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

const message = {
  id: "m1",
  name: "Sam Jones",
  company: "Jones Care",
  email: "sam@example.com",
  topic: "sales",
  message: "Do you do rotas?",
  created_at: "2026-11-01T10:00:00Z",
  handled_at: null,
};

beforeEach(() => {
  get.mockResolvedValue({ data: { items: [message], total: 1 } });
  patch.mockResolvedValue({ data: { ...message, handled_at: "2026-11-02T09:00:00Z" } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ContactAdmin", () => {
  it("opens a message and marks it handled, which removes it from the not handled list", async () => {
    render(<ContactAdmin />);
    expect(get.mock.calls[0]?.[1].params.query).toEqual({ handled: false });
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(screen.getByText("Do you do rotas?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark handled" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0]?.[1].body).toEqual({ handled: true });
    expect(await screen.findByText("No messages.")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    get.mockResolvedValue({ data: { items: [], total: 0 } });
    render(<ContactAdmin />);
    expect(await screen.findByText("No messages.")).toBeInTheDocument();
  });
});
