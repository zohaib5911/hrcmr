// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SubscriptionsAdmin } from "./subscriptions-admin";

const get = vi.fn();

vi.mock("@/lib/auth/request", () => ({
  attempt: async (fn: (c: unknown) => Promise<{ data?: unknown; error?: unknown }>) => {
    const r = await fn({ GET: get });
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
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SubscriptionsAdmin", () => {
  it("lists subscriptions with Stripe ids as text", async () => {
    render(<SubscriptionsAdmin />);
    expect(await screen.findByText("Acme Care")).toBeInTheDocument();
    expect(screen.getByText(/pi_123/)).toBeInTheDocument();
  });

  it("offers no refund action to anyone", async () => {
    render(<SubscriptionsAdmin />);
    await screen.findByText("Acme Care");
    expect(screen.queryByRole("button", { name: /refund/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/refund reason/i)).not.toBeInTheDocument();
  });
});

describe("SubscriptionsAdmin expired platform session", () => {
  it.each(["UNAUTHENTICATED", "FORBIDDEN"])("returns to the start page on %s", async (code) => {
    const replace = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace });
    get.mockResolvedValue({ error: { code, message: "no" } });
    render(<SubscriptionsAdmin />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/session?next=%2Fsubscriptions"));
    vi.unstubAllGlobals();
  });
});
