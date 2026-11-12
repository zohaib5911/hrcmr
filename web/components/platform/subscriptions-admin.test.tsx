// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SubscriptionsAdmin } from "./subscriptions-admin";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ GET: get, POST: post });
    return r.error ? { ok: false, problem: r.error } : { ok: true, data: r.data };
  },
}));

const row = {
  id: "s1",
  company_id: "c1",
  company_name: "Acme Care",
  plan: "ten_year",
  status: "active",
  created_at: "2026-10-01T09:00:00Z",
  current_period_end: null,
  cancel_at: null,
  refunded_at: null,
  stripe_subscription_id: null,
  stripe_payment_intent_id: "pi_123",
};

beforeEach(() => {
  get.mockResolvedValue({ data: { items: [row], total: 1 } });
  post.mockResolvedValue({
    data: {
      subscription: { ...row, refunded_at: "2026-11-12T10:00:00Z" },
      stripe_refund_id: "re_1",
    },
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SubscriptionsAdmin", () => {
  it("lists subscriptions with Stripe ids as text", async () => {
    render(<SubscriptionsAdmin isOwner />);
    expect(await screen.findByText("Acme Care")).toBeInTheDocument();
    expect(screen.getByText(/pi_123/)).toBeInTheDocument();
  });

  it("hides Refund from a support-level admin", async () => {
    render(<SubscriptionsAdmin isOwner={false} />);
    await screen.findByText("Acme Care");
    expect(screen.queryByRole("button", { name: "Refund" })).not.toBeInTheDocument();
  });

  it("needs a reason, then confirms and sends confirm: true once", async () => {
    render(<SubscriptionsAdmin isOwner />);
    await screen.findByText("Acme Care");
    expect(screen.getByRole("button", { name: "Refund" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Refund reason"), "Customer asked in 14 days");
    await userEvent.click(screen.getByRole("button", { name: "Refund" }));
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(await screen.findByRole("button", { name: "Refund in full" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0]?.[0]).toBe("/platform/refunds");
    expect(post.mock.calls[0]?.[1].body).toEqual({
      subscription_id: "s1",
      reason: "Customer asked in 14 days",
      confirm: true,
    });
    expect(await screen.findByText(/^Refunded \d/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refund" })).not.toBeInTheDocument();
  });

  it("shows the API's message when the refund is refused", async () => {
    post.mockResolvedValue({ error: { code: "ALREADY_REFUNDED", message: "Already refunded." } });
    render(<SubscriptionsAdmin isOwner />);
    await screen.findByText("Acme Care");
    await userEvent.type(screen.getByLabelText("Refund reason"), "Customer asked");
    await userEvent.click(screen.getByRole("button", { name: "Refund" }));
    await userEvent.click(await screen.findByRole("button", { name: "Refund in full" }));
    expect(await screen.findByText("Already refunded.")).toBeInTheDocument();
  });
});

describe("SubscriptionsAdmin expired platform session", () => {
  it.each(["UNAUTHENTICATED", "FORBIDDEN"])("returns to the start page on %s", async (code) => {
    const replace = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace });
    get.mockResolvedValue({ error: { code, message: "no" } });
    render(<SubscriptionsAdmin isOwner />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/session?next=%2Fsubscriptions"));
    vi.unstubAllGlobals();
  });
});
