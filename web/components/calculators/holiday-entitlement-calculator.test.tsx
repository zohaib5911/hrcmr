// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/holiday-entitlement-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("public holiday entitlement calculator", () => {
  it("renders the sources table and privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Holiday entitlement");
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getAllByRole("link").length).toBeGreaterThan(0);
  });

  it("calculates locally, rejects bad input and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    await user.type(screen.getByLabelText("Days worked per week"), "3");
    await user.click(screen.getByRole("button", { name: "Calculate holiday" }));
    // GOV.UK: 3 days a week = 16.8 days
    expect(screen.getByRole("region", { name: "Holiday result" })).toHaveTextContent("16.8 days");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(
      screen.queryByRole("heading", { name: "Your holiday entitlement" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate holiday" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("caps hours mode at 28 days and explains missing or uneven patterns", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.selectOptions(screen.getByLabelText("How do they work?"), "hours");
    await user.type(screen.getByLabelText("Hours worked per week"), "45");
    await user.click(screen.getByRole("button", { name: "Calculate holiday" }));
    expect(screen.getByRole("alert")).toHaveTextContent("days per week");
    await user.type(screen.getByLabelText("Days those hours are worked over"), "6");
    await user.click(screen.getByRole("button", { name: "Calculate holiday" }));
    const result = screen.getByRole("region", { name: "Holiday result" });
    expect(result).toHaveTextContent("210 hours");
    expect(result).toHaveTextContent("Capped at the statutory maximum of 28 days.");
    await user.selectOptions(screen.getByLabelText("Is every working day the same length?"), "no");
    await user.click(screen.getByRole("button", { name: "Calculate holiday" }));
    expect(screen.getByRole("alert")).toHaveTextContent("different lengths");
  });

  it("shows the complete frame and fills the form from a preset", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Quick answer" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Are bank holidays included?" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "More tools" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Part time, 3 days a week" }));
    expect(screen.getByLabelText("Days worked per week")).toHaveValue(3);
    await user.click(screen.getByRole("button", { name: "Calculate holiday" }));
    expect(screen.getByRole("region", { name: "Holiday result" })).toHaveTextContent("16.8 days");
  });
});
