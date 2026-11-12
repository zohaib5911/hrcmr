// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/uk-take-home-salary-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("public take-home salary calculator", () => {
  it("renders the sources table and privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("take-home salary");
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    expect(within(screen.getAllByRole("table")[0]!).getAllByRole("link").length).toBeGreaterThan(0);
  });

  it("calculates locally, rejects bad input and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    await user.type(screen.getByLabelText("Annual salary (£)"), "30000");
    await user.click(screen.getByRole("button", { name: "Calculate take-home" }));
    // Hand-worked from the rates file: £30,000 -> £25,119.60
    expect(screen.getByRole("region", { name: "Take-home result" })).toHaveTextContent(
      "£25,119.60 a year",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByRole("heading", { name: "Your take-home pay" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate take-home" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
  it("switches tax years, updates results and sources, rejects Plan 5 and resets the year", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    const submit = screen.getByRole("button", { name: "Calculate take-home" });
    const year = screen.getByLabelText("Tax year");
    await user.type(screen.getByLabelText("Annual salary (£)"), "40000");
    await user.selectOptions(screen.getByLabelText("Where do you live?"), "scotland");
    await user.selectOptions(screen.getByLabelText("Student loan plan"), "plan 2");
    await user.click(submit);
    expect(screen.getByRole("row", { name: /Income tax/ })).toHaveTextContent("-£5,551.07");
    expect(screen.getByRole("row", { name: /Student loan/ })).toHaveTextContent("-£955.35");
    const result = screen.getByRole("region", { name: "Take-home result" });
    expect(within(result).getByRole("link")).toHaveAttribute(
      "href",
      expect.stringContaining("2026-to-2027"),
    );
    await user.selectOptions(year, "2025-2026");
    expect(screen.queryByRole("heading", { name: "Your take-home pay" })).not.toBeInTheDocument();
    await user.click(submit);
    expect(screen.getByRole("row", { name: /Income tax/ })).toHaveTextContent("-£5,582.82");
    expect(screen.getByRole("row", { name: /Student loan/ })).toHaveTextContent("-£1,037.70");
    expect(result).toHaveTextContent("2025 to 2026 tax year");
    expect(within(result).getByRole("link")).toHaveAttribute(
      "href",
      expect.stringContaining("2025-to-2026"),
    );
    await user.selectOptions(screen.getByLabelText("Student loan plan"), "plan 5");
    await user.click(submit);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Plan 5 repayments are not supported for 2025–2026",
    );
    expect(screen.queryByRole("heading", { name: "Your take-home pay" })).not.toBeInTheDocument();
    await user.selectOptions(year, "2026-2027");
    await user.click(submit);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Student loan/ })).toHaveTextContent("-£1,350.00");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.selectOptions(year, "2025-2026");
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(year).toHaveValue("2026-2027");
  });

  it("uses a custom Scottish code and explains unsupported codes", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.selectOptions(screen.getByLabelText("Where do you live?"), "scotland");
    await user.type(screen.getByLabelText("Annual salary (£)"), "30000");
    const code = screen.getByLabelText("Tax code");
    await user.clear(code);
    await user.type(code, "SD1");
    await user.click(screen.getByRole("button", { name: "Calculate take-home" }));
    expect(screen.getByRole("row", { name: /Income tax/ })).toHaveTextContent("-£12,600.00");
    await user.clear(code);
    await user.type(code, "SD4");
    await user.click(screen.getByRole("button", { name: "Calculate take-home" }));
    expect(screen.getByRole("alert")).toHaveTextContent("supported tax code for your region");
    expect(screen.queryByRole("heading", { name: "Your take-home pay" })).not.toBeInTheDocument();
    await user.clear(code);
    await user.type(code, "BR");
    await user.click(screen.getByRole("button", { name: "Calculate take-home" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Income tax/ })).toHaveTextContent("-£6,000.00");
  });
});
