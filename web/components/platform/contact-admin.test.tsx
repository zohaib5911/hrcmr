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
    expect(get.mock.calls[0]?.[1].params.query).toEqual({ limit: 50, offset: 0, handled: false });
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

  it("pages past 50 messages and resets to the first page on a filter change", async () => {
    get.mockResolvedValue({ data: { items: [message], total: 120 } });
    render(<ContactAdmin />);
    await screen.findByText("Sam Jones");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(get.mock.calls.at(-1)?.[1].params.query).toEqual({
        limit: 50,
        offset: 50,
        handled: false,
      }),
    );
    await screen.findByText("Sam Jones");
    await userEvent.selectOptions(screen.getByLabelText("Show"), "true");
    await waitFor(() =>
      expect(get.mock.calls.at(-1)?.[1].params.query).toEqual({
        limit: 50,
        offset: 0,
        handled: true,
      }),
    );
  });

  it("shows an error when a later page fails", async () => {
    get.mockResolvedValueOnce({ data: { items: [message], total: 120 } });
    get.mockResolvedValueOnce({ error: { code: "SERVER", message: "Page failed" } });
    render(<ContactAdmin />);
    await screen.findByText("Sam Jones");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Page failed")).toBeInTheDocument();
  });
});

describe("ContactAdmin expired platform session", () => {
  it.each(["UNAUTHENTICATED", "FORBIDDEN"])("returns to the start page on %s", async (code) => {
    const replace = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace });
    get.mockResolvedValue({ error: { code, message: "no" } });
    render(<ContactAdmin />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/session?next=%2Fcontact"));
    vi.unstubAllGlobals();
  });
});

describe("ContactAdmin delayed update", () => {
  const other = { ...message, id: "m2", name: "Page Two" };
  function deferPatch() {
    let resolve: (v: unknown) => void = () => {};
    patch.mockReturnValue(new Promise((r) => (resolve = r)));
    return () => resolve({ data: { ...message, handled_at: "2026-11-02T09:00:00Z" } });
  }

  it("keeps the second page visible when a delayed update resolves after paging", async () => {
    get.mockResolvedValueOnce({ data: { items: [message], total: 120 } });
    get.mockResolvedValueOnce({ data: { items: [other], total: 120 } });
    const finish = deferPatch();
    render(<ContactAdmin />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    await userEvent.click(screen.getByRole("button", { name: "Mark handled" }));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Page Two")).toBeInTheDocument();
    finish();
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.getByText("Page Two")).toBeInTheDocument();
    expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
  });

  it("keeps the new filter's list when a delayed update resolves after a filter change", async () => {
    get.mockResolvedValueOnce({ data: { items: [message], total: 1 } });
    get.mockResolvedValueOnce({ data: { items: [other], total: 1 } });
    const finish = deferPatch();
    render(<ContactAdmin />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    await userEvent.click(screen.getByRole("button", { name: "Mark handled" }));
    await userEvent.selectOptions(screen.getByLabelText("Show"), "true");
    expect(await screen.findByText("Page Two")).toBeInTheDocument();
    finish();
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.getByText("Page Two")).toBeInTheDocument();
  });

  it("removes the handled row from the active page", async () => {
    get.mockResolvedValue({ data: { items: [message, other], total: 2 } });
    render(<ContactAdmin />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Open" }))[0]!);
    await userEvent.click(screen.getByRole("button", { name: "Mark handled" }));
    await waitFor(() => expect(screen.queryByText("Sam Jones")).not.toBeInTheDocument());
    expect(screen.getByText("Page Two")).toBeInTheDocument();
  });
});
