// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/sponsor-licence-cost-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("public sponsor licence cost calculator", () => {
  it("renders the sources table and privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sponsor licence cost");
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getAllByRole("link").length).toBeGreaterThan(5);
  });

  it("calculates locally, rejects bad input and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    await user.type(screen.getByLabelText("Annual turnover (£)"), "20000000");
    await user.type(screen.getByLabelText("Total assets (£)"), "10000000");
    await user.type(screen.getByLabelText("Employees"), "100");
    await user.clear(screen.getByLabelText("Certificate length (months, 1–60)"));
    await user.type(screen.getByLabelText("Certificate length (months, 1–60)"), "24");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    const result = screen.getByRole("region", { name: "Cost result" });
    // £819 visa + 2 × £1,035 healthcare surcharge = £2,889 (GOV.UK worked example)
    expect(result).toHaveTextContent("medium or large");
    expect(result).toHaveTextContent("£1,682.00");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByRole("heading", { name: "Your estimated costs" })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Number of workers"));
    await user.type(screen.getByLabelText("Number of workers"), "0");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
