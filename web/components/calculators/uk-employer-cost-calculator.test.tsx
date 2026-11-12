// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Page from "@/app/(marketing)/resources/tools/uk-employer-cost-calculator/page";

afterEach(() => vi.restoreAllMocks());
const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const submit = () =>
  fireEvent.click(screen.getByRole("button", { name: "Calculate employer cost" }));
const result = () => within(screen.getByRole("region", { name: "Employer cost result" }));

describe("employer cost calculator page", () => {
  it("shows sources and computes annual cost without transmitting or storing answers", async () => {
    const request = vi.spyOn(globalThis, "fetch");
    const local = vi.spyOn(Storage.prototype, "setItem");
    const user = userEvent.setup();
    render(<Page />);
    expect(
      screen.getByRole("heading", { level: 1, name: "UK employer cost calculator" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Rates and thresholds for employers 2026 to 2027/ }),
    ).toHaveAttribute(
      "href",
      "https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027",
    );
    expect(screen.getByRole("link", { name: /Workplace pensions/ })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Annual gross salary (£)"), "30000");
    await user.type(screen.getByLabelText("Age in whole years"), "30");
    await user.click(screen.getByRole("button", { name: "Calculate employer cost" }));
    expect(result().getByText("£3,750.00")).toBeInTheDocument();
    expect(result().getByText("£712.80")).toBeInTheDocument();
    expect(result().getByText("£34,462.80")).toBeInTheDocument();
    expect(result().getByText(/Connected employers share the allowance/)).toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
    expect(local).not.toHaveBeenCalled();
  });
  it("clears stale results and recalculates age, type, pension basis and year", () => {
    render(<Page />);
    fill("Annual gross salary (£)", "60000");
    fill("Age in whole years", "24");
    fill("Employee type", "apprentice");
    submit();
    expect(result().getByText("£1,459.50")).toBeInTheDocument();
    fill("Age in whole years", "25");
    expect(
      result().queryByRole("heading", { name: "Estimated annual employer cost" }),
    ).not.toBeInTheDocument();
    fill("Tax year", "2025-2026");
    fill("Pension earnings basis", "full");
    fill("Employer pension contribution (%)", "5");
    submit();
    expect(result().getByText("£8,250.00")).toBeInTheDocument();
    expect(result().getByText("£3,000.00")).toBeInTheDocument();
    expect(result().getByText("£71,250.00")).toBeInTheDocument();
  });
  it("requires values, rejects fractional ages and allows explicit zero contribution", () => {
    render(<Page />);
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter salary, age and pension percentage");
    fill("Annual gross salary (£)", "30000");
    fill("Age in whole years", "20.5");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("whole-year age");
    fill("Age in whole years", "20");
    fill("Employer pension contribution (%)", "0");
    submit();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      within(
        result().getByText("Total annual cost before allowances and Levy").parentElement!,
      ).getByText("£30,000.00"),
    ).toBeInTheDocument();
  });
  it("resets all answers and removes results", () => {
    render(<Page />);
    fill("Annual gross salary (£)", "30000");
    fill("Age in whole years", "30");
    submit();
    fireEvent.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.getByLabelText("Annual gross salary (£)")).toHaveValue(null);
    expect(screen.getByLabelText("Age in whole years")).toHaveValue(null);
    expect(screen.getByLabelText("Employer pension contribution (%)")).toHaveValue(3);
    expect(
      result().queryByRole("heading", { name: "Estimated annual employer cost" }),
    ).not.toBeInTheDocument();
  });
});
