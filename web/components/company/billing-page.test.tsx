// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";

import { BillingPage } from "./billing-page";

const { attempt } = vi.hoisted(() => ({ attempt: vi.fn() }));
vi.mock("@/lib/auth/request", () => ({ attempt }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

beforeEach(() => {
  attempt.mockReset();
});

type Billing = components["schemas"]["BillingOut"];

const NOW = "2026-11-09T10:00:00Z";

function billing(overrides: Partial<Billing>): Billing {
  return {
    cancel_at: null,
    comp_until: null,
    ends_at: null,
    has_billing_account: false,
    payment_grace_ends_at: null,
    payments_enabled: true,
    plan: "free",
    started_at: null,
    subscription_status: null,
    support_email: "support@example.com",
    ...overrides,
  };
}

function renderPage(value: Billing) {
  return render(
    <ToastProvider>
      <BillingPage billing={value} checkout={undefined} now={NOW} />
    </ToastProvider>,
  );
}

describe("BillingPage complimentary access (C3.1.14)", () => {
  it("says until when the access is complimentary, so the company is not offered a plan as if it had none", () => {
    renderPage(billing({ comp_until: "2027-01-15T12:00:00Z" }));
    expect(screen.getByText("Complimentary access", { exact: true })).toBeInTheDocument();
    expect(screen.getByText(/Complimentary access until 15 Jan 2027/)).toBeInTheDocument();
  });

  it("says nothing about it once the complimentary access has ended", () => {
    renderPage(billing({ comp_until: "2026-10-01T12:00:00Z" }));
    expect(screen.queryByText(/Complimentary access/)).toBeNull();
  });
});

describe("BillingPage data export (C3.1.11)", () => {
  it("asks for the password when the export needs a fresh sign-in, then requests the export", async () => {
    attempt
      .mockResolvedValueOnce({
        ok: false,
        problem: { code: "STEP_UP_REQUIRED", message: "Confirm it is you." },
      })
      .mockResolvedValueOnce({ ok: true, data: undefined })
      .mockResolvedValueOnce({ ok: true, data: undefined });
    const user = userEvent.setup();
    renderPage(billing({}));
    await user.click(screen.getByRole("button", { name: "Request an export" }));
    await user.type(await screen.findByLabelText("Your password"), "a long passphrase here");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByText("We are preparing your export. We will e-mail you a link."),
    ).toBeInTheDocument();
    expect(attempt).toHaveBeenCalledTimes(3);
  });

  it("shows the API's message when an export is already being prepared", async () => {
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: {
        code: "EXPORT_IN_PROGRESS",
        message: "An export is already being prepared. It will be ready soon.",
      },
    });
    const user = userEvent.setup();
    renderPage(billing({}));
    await user.click(screen.getByRole("button", { name: "Request an export" }));
    expect(
      await screen.findByText("An export is already being prepared. It will be ready soon."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Confirm it is you" })).toBeNull();
  });
});

describe("BillingPage plan step-up (T25.3)", () => {
  it("reauthenticates and retries the same checkout plan", async () => {
    const post = vi.fn().mockResolvedValue({});
    const requests: unknown[] = [];
    attempt.mockImplementation(async (call: (api: { POST: typeof post }) => unknown) => {
      await call({ POST: post });
      requests.push(post.mock.calls.at(-1));
      if (requests.length === 1) {
        return { ok: false, problem: { code: "STEP_UP_REQUIRED", message: "Confirm it is you." } };
      }
      if (requests.length === 2) return { ok: true, data: undefined };
      return { ok: false, problem: { code: "PAYMENTS_UNAVAILABLE", message: "Try again later." } };
    });
    const user = userEvent.setup();
    renderPage(billing({}));
    await user.click(screen.getByRole("button", { name: "Choose 10 years" }));
    await user.type(await screen.findByLabelText("Your password"), "a long passphrase here");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Try again later.")).toBeInTheDocument();
    expect(requests).toEqual([
      ["/billing/checkout-session", { body: { plan: "ten_year" } }],
      ["/auth/step-up", { body: { password: "a long passphrase here" } }],
      ["/billing/checkout-session", { body: { plan: "ten_year" } }],
    ]);
  });

  it("reauthenticates and retries cancellation without requesting an export", async () => {
    const post = vi.fn().mockResolvedValue({});
    const requests: unknown[] = [];
    attempt.mockImplementation(async (call: (api: { POST: typeof post }) => unknown) => {
      await call({ POST: post });
      requests.push(post.mock.calls.at(-1));
      if (requests.length === 1) {
        return { ok: false, problem: { code: "STEP_UP_REQUIRED", message: "Confirm it is you." } };
      }
      if (requests.length === 2) return { ok: true, data: undefined };
      return { ok: true, data: { ends_at: "2027-11-09T10:00:00Z" } };
    });
    const user = userEvent.setup();
    renderPage(
      billing({
        plan: "annual",
        subscription_status: "active",
        started_at: "2026-10-01T10:00:00Z",
        ends_at: "2027-11-09T10:00:00Z",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel subscription" }));
    await user.click(screen.getByRole("button", { name: /^Cancel subscription$/ }));
    await user.type(await screen.findByLabelText("Your password"), "a long passphrase here");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText(/Your plan ends on/)).toBeInTheDocument();
    expect(requests).toEqual([
      ["/billing/cancel"],
      ["/auth/step-up", { body: { password: "a long passphrase here" } }],
      ["/billing/cancel"],
    ]);
  });
});
