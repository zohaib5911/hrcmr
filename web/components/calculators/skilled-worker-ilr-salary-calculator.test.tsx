// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/skilled-worker-ilr-salary-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("public skilled worker ILR salary calculator", () => {
  it("renders the sources table and privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("ILR salary");
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getAllByRole("link").length).toBeGreaterThan(1);
  });

  it("calculates locally, rejects bad input and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    await user.click(screen.getByRole("button", { name: "Calculate salary" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Job title or SOC code"), "1111");
    await user.click(screen.getByRole("button", { name: "Calculate salary" }));
    const result = screen.getByRole("region", { name: "Salary result" });
    // Hand-worked from the rates file: 1111 going rate £88,100 > £41,700.
    expect(result).toHaveTextContent("At least £88,100 a year");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(
      screen.queryByRole("heading", { name: "Your settlement salary requirement" }),
    ).not.toBeInTheDocument();
  });
});
