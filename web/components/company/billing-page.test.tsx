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
    cooling_off_ends_at: null,
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
