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
    await user.type(screen.getByLabelText("Job title or SOC code"), "zzzz");
    expect(screen.getByRole("alert")).toHaveTextContent("Incomplete");
    await user.clear(screen.getByLabelText("Job title or SOC code"));
    await user.type(screen.getByLabelText("Job title or SOC code"), "1111");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
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

  it("shows review guidance, not an amount, when the going rate is missing", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.type(screen.getByLabelText("Job title or SOC code"), "3214");
    const result = screen.getByRole("region", { name: "Salary result" });
    expect(result).toHaveTextContent("We can’t give a figure for this situation");
    expect(result).toHaveTextContent("no standard going rate");
    expect(result).not.toHaveTextContent("At least");
    expect(result).not.toHaveTextContent("£41,700");
  });

  it("shows the frame, fills presets and pro-rates live as the hours change", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByRole("heading", { name: "Quick answer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questions" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chief executive, 30 hours a week" }));
    expect(screen.getByLabelText("Job title or SOC code")).toHaveValue("1111");
    expect(screen.getByLabelText("Weekly working hours")).toHaveValue(30);
    const result = screen.getByRole("region", { name: "Salary result" });
    // Hand-worked: £88,100 × 30 / 37.5 = £70,480.
    expect(result).toHaveTextContent("At least £70,480 a year");
    await user.clear(screen.getByLabelText("Weekly working hours"));
    await user.type(screen.getByLabelText("Weekly working hours"), "37.5");
    expect(result).toHaveTextContent("At least £88,100 a year");
    await user.clear(screen.getByLabelText("Weekly working hours"));
    expect(screen.getByRole("alert")).toHaveTextContent("Incomplete");
    expect(result).not.toHaveTextContent("At least");
  });
});
