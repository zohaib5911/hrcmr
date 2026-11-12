// @vitest-environment jsdom
import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MinimumWageChecker } from "./uk-minimum-wage-underpayment-checker";
afterEach(cleanup);
it("calculates a period and clears stale results and answers", () => {
  render(<MinimumWageChecker />);
  for (const [label, value] of [
    ["Pay-period start", "2026-04-01"],
    ["Age at pay-period start", "21"],
    ["Minimum-wage hours for this period", "40"],
    ["Gross period pay before the reductions below (£)", "500"],
  ] as const)
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "Check minimum wage" }));
  expect(screen.getByText("Potential underpayment")).toBeInTheDocument();
  expect(screen.getByText("Period shortfall: £8.40.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Age at pay-period start"), { target: { value: "20" } });
  expect(screen.queryByText("Potential underpayment")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Reset answers" }));
  expect(screen.getByLabelText("Age at pay-period start")).toHaveValue(null);
});
it("rejects missing fields without displaying a pass", () => {
  render(<MinimumWageChecker />);
  fireEvent.click(screen.getByRole("button", { name: "Check minimum wage" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Complete all fields");
  expect(screen.queryByText("No shortfall on these inputs")).not.toBeInTheDocument();
});
