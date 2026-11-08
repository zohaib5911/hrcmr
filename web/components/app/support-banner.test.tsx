// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { components } from "@/lib/api/client";

import { SessionProvider } from "./session-context";
import { SupportBanner } from "./support-banner";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

type Me = components["schemas"]["MeResponse"];

function me(support: Me["support"]): Me {
  return {
    user: {
      id: "u1",
      email: "admin@example.com",
      first_name: "Pat",
      last_name: "Admin",
      email_verified: true,
      mfa_enabled: true,
      theme_pref: "system",
    },
    companies: [],
    active_company_id: null,
    role: "company_admin",
    permissions: [],
    mfa: "not_required",
    terms_acceptance_required: false,
    terms_version: "1",
    step_up_active: false,
    platform_admin: true,
    ai_available: false,
    support,
  };
}

describe("SupportBanner", () => {
  it("is not shown outside support mode", () => {
    render(
      <SessionProvider me={me(null)}>
        <SupportBanner />
      </SessionProvider>,
    );
    expect(screen.queryByTestId("support-banner")).toBeNull();
  });

  it("names the company, the ticket, read-only and the end time, with a way out", () => {
    render(
      <SessionProvider
        me={me({
          id: "s1",
          company_name: "Acme Ltd",
          ticket_ref: "SUP-1042",
          expires_at: "2026-11-08T12:30:00Z",
          write_enabled: false,
        })}
      >
        <SupportBanner />
      </SessionProvider>,
    );
    const banner = screen.getByTestId("support-banner");
    expect(banner).toHaveTextContent("Support mode");
    expect(banner).toHaveTextContent("Acme Ltd");
    expect(banner).toHaveTextContent("SUP-1042");
    expect(banner).toHaveTextContent("Read-only.");
    expect(banner).toHaveTextContent("Ends at 12:30.");
    expect(screen.getByRole("button", { name: "End support mode" })).toBeEnabled();
  });
});
