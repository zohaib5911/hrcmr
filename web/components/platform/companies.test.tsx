// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/client";
import { CompanyDetail } from "./company-detail";
import { CompaniesList } from "./companies-list";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("@/lib/auth/request", () => ({
  attempt: async (run: (c: { POST: typeof post }) => Promise<unknown>) => run({ POST: post }),
}));
const company: components["schemas"]["CompanyDetailOut"] = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Acme",
  slug: "acme",
  contact_email: "hello@example.test",
  status: "active",
  plan: "annual",
  subscription_status: "active",
  subscription_ends_at: null,
  created_at: "2026-01-01T00:00:00Z",
  last_active_at: null,
  members: 0,
  trading_name: null,
  registered_number: null,
  subscription_started_at: null,
  payment_grace_ends_at: null,
  stripe_customer_id: "cus_example",
  stripe_subscription_id: "sub_example",
  people: [],
  events: [],
};
const context: components["schemas"]["PlatformContextOut"] = {
  owner: true,
  web_origin: "https://app.example.test",
  support: null,
};
const liveSupport = { id: "support-id", expires_at: "2099-01-01T00:00:00Z", write_enabled: false };
afterEach(cleanup);
beforeEach(() => post.mockReset());

describe("company actions", () => {
  it("requires a reason, suspends once and reactivates with the returned status", async () => {
    const user = userEvent.setup();
    post
      .mockResolvedValueOnce({ ok: true, data: { ...company, status: "suspended" } })
      .mockResolvedValueOnce({ ok: true, data: company });
    render(<CompanyDetail company={company} context={context} />);
    await user.click(screen.getByRole("button", { name: "Suspend" }));
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    await user.type(screen.getByLabelText("Reason"), "    ");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    await user.type(screen.getByLabelText("Reason"), "Ticket investigated");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(screen.getByText("suspended")).toBeVisible();
    expect(post).toHaveBeenCalledExactlyOnceWith("/platform/companies/{company_id}/suspend", {
      params: { path: { company_id: company.id } },
      body: { reason: "Ticket investigated" },
    });
    await user.click(screen.getByRole("button", { name: "Reactivate" }));
    await user.type(screen.getByLabelText("Reason"), "Issue resolved");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(screen.getByText("active", { selector: "span" })).toBeVisible();
    expect(post.mock.calls[1]![0]).toBe("/platform/companies/{company_id}/reactivate");
  });

  it.each(["Extend plan", "Mark for deletion", "Start support mode"])(
    "requires a reason for %s",
    async (label) => {
      const user = userEvent.setup();
      render(<CompanyDetail company={company} context={context} />);
      await user.click(screen.getByRole("button", { name: label }));
      expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
      expect(post).not.toHaveBeenCalled();
    },
  );

  it("validates extension days and sends the reason and days", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ ok: true, data: company });
    render(<CompanyDetail company={company} context={context} />);
    await user.click(screen.getByRole("button", { name: "Extend plan" }));
    await user.type(screen.getByLabelText("Reason"), "Complimentary access");
    await user.clear(screen.getByLabelText("Days"));
    await user.type(screen.getByLabelText("Days"), "366");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Days"));
    await user.type(screen.getByLabelText("Days"), "14");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(post.mock.calls[0]).toEqual([
      "/platform/companies/{company_id}/extend-plan",
      {
        params: { path: { company_id: company.id } },
        body: { reason: "Complimentary access", days: 14 },
      },
    ]);
  });

  it("requires a ticket, starts read-only support, then opens the configured tenant origin", async () => {
    const user = userEvent.setup();
    const go = vi.fn();
    post.mockResolvedValue({ ok: true, data: liveSupport });
    render(<CompanyDetail company={company} context={context} go={go} />);
    await user.click(screen.getByRole("button", { name: "Start support mode" }));
    await user.type(screen.getByLabelText("Reason"), "Investigate ticket");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    await user.type(screen.getByLabelText("Ticket reference"), "HELP-123");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(post.mock.calls[0]![1].body).toEqual({
      reason: "Investigate ticket",
      ticket_ref: "HELP-123",
    });
    expect(go).toHaveBeenCalledWith("https://app.example.test/dashboard");
  });

  it("hides every owner-only action from support admins", () => {
    render(
      <CompanyDetail
        company={company}
        context={{ ...context, owner: false, support: liveSupport }}
      />,
    );
    for (const name of ["Mark for deletion", "Turn on writes", "End"])
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start support mode" })).toBeVisible();
  });

  it("requires a second confirmation for writes and sends confirm true", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ ok: true, data: { ...liveSupport, write_enabled: true } });
    render(<CompanyDetail company={company} context={{ ...context, support: liveSupport }} />);
    await user.click(screen.getByRole("button", { name: "Turn on writes" }));
    const buttons = screen.getAllByRole("button", { name: "Turn on writes" });
    expect(buttons.at(-1)).toBeDisabled();
    await user.type(screen.getByLabelText("Type ENABLE to confirm"), "ENABLE");
    await user.click(screen.getAllByRole("button", { name: "Turn on writes" }).at(-1)!);
    expect(post).toHaveBeenCalledExactlyOnceWith("/platform/impersonation/{support_id}/writes", {
      params: { path: { support_id: "support-id" } },
      body: { enabled: true, confirm: true },
    });
    expect(screen.getByText(/Changes are on/)).toBeVisible();
  });

  it("ends a live support session", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ ok: true, data: { ...liveSupport, ended_at: "2026-01-01" } });
    render(<CompanyDetail company={company} context={{ ...context, support: liveSupport }} />);
    await user.click(screen.getByRole("button", { name: "End" }));
    await user.click(screen.getByRole("button", { name: "End session" }));
    expect(post.mock.calls[0]![0]).toBe("/platform/impersonation/{support_id}/end");
    expect(screen.queryByText("Live support session")).not.toBeInTheDocument();
  });

  it("shows API refusal and retains the company status", async () => {
    const user = userEvent.setup();
    post.mockResolvedValue({ ok: false, problem: { code: "REFUSED", message: "Action refused." } });
    render(<CompanyDetail company={company} context={context} />);
    await user.click(screen.getByRole("button", { name: "Suspend" }));
    await user.type(screen.getByLabelText("Reason"), "Review ticket");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(screen.getByText("Action refused.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Suspend" })).toBeVisible();
  });

  it("shows a load failure", () => {
    render(<CompanyDetail company={null} context={null} />);
    expect(screen.getByText("Company could not be loaded")).toBeVisible();
  });
});

describe("companies search", () => {
  it("renders filter form, companies and paging preserving filters", () => {
    render(
      <CompaniesList
        data={{ items: [company], total: 30 }}
        filters={{ q: "Acme", plan: "annual", offset: 0 }}
      />,
    );
    expect(screen.getByRole("link", { name: "Acme" })).toHaveAttribute(
      "href",
      `/companies/${company.id}`,
    );
    expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute(
      "href",
      "/companies?q=Acme&plan=annual&offset=25",
    );
    expect(screen.getByLabelText("Plan")).toHaveValue("annual");
  });
  it("shows an empty result", () => {
    render(<CompaniesList data={{ items: [], total: 0 }} filters={{ offset: 0 }} />);
    expect(screen.getByText("No companies match these filters.")).toBeVisible();
  });
  it("shows a load error", () => {
    render(<CompaniesList data={null} filters={{ offset: 0 }} />);
    expect(screen.getByText("Companies could not be loaded")).toBeVisible();
  });
});
