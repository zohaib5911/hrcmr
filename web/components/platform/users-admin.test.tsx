// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UsersAdmin } from "./users-admin";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ GET: get, POST: post });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

const user = {
  id: "u1",
  email: "ada@example.com",
  first_name: "Ada",
  last_name: "Lovelace",
  email_verified: true,
  mfa_enabled: false,
  locked: false,
  last_login_at: null,
  companies: [],
};

beforeEach(() => {
  get.mockResolvedValue({ data: { items: [user] } });
  post.mockResolvedValue({ data: { ...user, locked: true } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UsersAdmin", () => {
  it("does not search until three characters are typed", async () => {
    render(<UsersAdmin />);
    const input = screen.getByLabelText("E-mail address");
    await userEvent.type(input, "ad");
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
    await userEvent.type(input, "a");
    expect(screen.getByRole("button", { name: "Search" })).toBeEnabled();
  });

  it("finds a user, locks them after confirming, with the optional reason", async () => {
    render(<UsersAdmin />);
    await userEvent.type(screen.getByLabelText("E-mail address"), "ada");
    await userEvent.type(screen.getByLabelText("Reason (optional)"), "abuse report");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Lock" }));
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(await screen.findByRole("button", { name: "Lock", hidden: false }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0]?.[0]).toBe("/platform/users/{user_id}/lock");
    expect(post.mock.calls[0]?.[1].body).toEqual({ reason: "abuse report" });
    expect(await screen.findByText("Locked")).toBeInTheDocument();
  });

  it("shows an empty state when nobody matches", async () => {
    get.mockResolvedValue({ data: { items: [] } });
    render(<UsersAdmin />);
    await userEvent.type(screen.getByLabelText("E-mail address"), "zzz");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText(/No user matches/)).toBeInTheDocument();
  });
});
