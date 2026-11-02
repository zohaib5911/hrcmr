// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Outcome } from "@/lib/auth/request";

const attempt = vi.fn<(run: unknown) => Promise<Outcome<unknown>>>();
vi.mock("@/lib/auth/request", () => ({ attempt: (run: unknown) => attempt(run) }));

import { SetupWizard } from "./setup-wizard";

async function firstStep(company = "Harbourside Care Ltd") {
  await userEvent.type(screen.getByLabelText("Company name"), company);
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
}

async function secondStep() {
  await userEvent.type(screen.getByLabelText("First name"), "Amira");
  await userEvent.type(screen.getByLabelText("Last name"), "Hassan");
  await userEvent.type(screen.getByLabelText("Work email"), "amira@example.com");
  await userEvent.type(screen.getByLabelText("Password"), "a long enough password");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
}

describe("SetupWizard", () => {
  beforeEach(() => attempt.mockReset());

  it("needs a company name before the second step, then shows the choices so far", async () => {
    render(<SetupWizard />);
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Enter your company name.")).toBeInTheDocument();
    expect(screen.queryByLabelText("First name")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Company name"), "Harbourside Care Ltd");
    await userEvent.click(screen.getByRole("radio", { name: /Scotland/ }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    const summary = await screen.findByText("Your choices so far");
    expect(summary.closest("details")).toHaveTextContent("Harbourside Care Ltd");
    expect(summary.closest("details")).toHaveTextContent("Scotland");
  });

  it("asks for everything on the second step before it calls the API", async () => {
    render(<SetupWizard />);
    await firstStep();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Enter your first name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid work email address.")).toBeInTheDocument();
    expect(screen.getByText("Use at least 12 characters.")).toBeInTheDocument();
    expect(screen.getByText("Accept the terms to create your account.")).toBeInTheDocument();
    expect(attempt).not.toHaveBeenCalled();
  });

  it("sends the company and the account together, then waits for the e-mailed link", async () => {
    attempt.mockResolvedValueOnce({ ok: true, data: { status: "check_your_inbox" } });
    render(<SetupWizard />);
    await firstStep();
    await secondStep();
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument(),
    );
    expect(screen.getByText("amira@example.com")).toBeInTheDocument();
    // Another e-mail cannot be asked for straight away.
    expect(screen.getByRole("button", { name: "Send the email again" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByText(/You can ask for another one in 60 seconds/)).toBeInTheDocument();
  });

  it("puts the API's complaint about the password on the password field", async () => {
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: {
        code: "WEAK_PASSWORD",
        message: "That password has appeared in a data breach. Choose another.",
        field: "password",
      },
    });
    render(<SetupWizard />);
    await firstStep();
    await secondStep();
    expect(
      await screen.findByText("That password has appeared in a data breach. Choose another."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute("aria-invalid", "true");
  });
});
