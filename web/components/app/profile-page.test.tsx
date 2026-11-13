// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { components } from "@/lib/api/client";

const applyTheme = vi.fn();
vi.mock("@/lib/theme-dom", () => ({ applyTheme: (...args: unknown[]) => applyTheme(...args) }));

import { ProfilePage } from "./profile-page";
import { SessionProvider } from "./session-context";

type Me = components["schemas"]["MeResponse"];

const me: Me = {
  user: {
    id: "u1",
    email: "ada@example.com",
    first_name: "Ada",
    last_name: "Lovelace",
    email_verified: true,
    mfa_enabled: true,
    theme_pref: "system",
  },
  companies: [
    {
      company_id: "c1",
      company_name: "Acme Care",
      plan: "free",
      role: "employee",
      status: "active",
    },
  ],
  active_company_id: "c1",
  role: "employee",
  permissions: [],
  mfa: "not_required",
  terms_acceptance_required: false,
  terms_version: "1",
  step_up_active: false,
  platform_admin: false,
  ai_available: false,
} as Me;

describe("ProfilePage", () => {
  it("shows the person's details and pages, and changes the theme", async () => {
    render(
      <SessionProvider me={me}>
        <ProfilePage theme="system" />
      </SessionProvider>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "My profile" })).toBeInTheDocument();
    expect(screen.queryByText(/on its way/)).not.toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Acme Care")).toBeInTheDocument();
    expect(screen.getByText("Employee")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /My profile/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Dark" }));
    expect(applyTheme).toHaveBeenCalledWith("dark", document, false);
  });
});
