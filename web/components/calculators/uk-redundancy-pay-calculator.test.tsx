// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Page from "@/app/(marketing)/resources/tools/uk-redundancy-pay-calculator/page";

// DatePicker commits typed dates on blur, as a person leaves the field.
function changeAndBlur(...args: Parameters<typeof fireEvent.change>) {
  fireEvent.change(...args);
  fireEvent.blur(args[0]);
}

afterEach(() => vi.restoreAllMocks());
function fill() {
  for (const [label, value] of [
    ["Date of birth", "1981-11-12"],
    ["Continuous employment start date", "2011-11-12"],
    ["Redundancy relevant date", "2026-11-12"],
    ["Average gross weekly pay (£)", "600"],
  ])
    changeAndBlur(screen.getByLabelText(label!), { target: { value } });
}

describe("redundancy pay calculator page", () => {
  it("shows sources and works locally without transport or persistence", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByRole("link", { name: "GB statutory redundancy pay" })).toHaveAttribute(
      "href",
      "https://www.gov.uk/redundancy-your-rights/redundancy-pay",
    );
    expect(
      screen.getByRole("link", { name: "Northern Ireland redundancy rules" }),
    ).toBeInTheDocument();
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storage = vi.spyOn(Storage.prototype, "setItem");
    fill();
    await user.click(screen.getByRole("button", { name: "Calculate redundancy pay" }));
    const result = within(screen.getByRole("region", { name: "Redundancy result" }));
    expect(result.getByText("£10,200.00")).toBeInTheDocument();
    expect(result.getByText("17 weeks × £600.00 = £10,200.00")).toBeInTheDocument();
    expect(result.getByText("£600.00 (cap: £751.00)")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storage).not.toHaveBeenCalled();
  });
  it("switches jurisdiction, clears stale results and resets answers", async () => {
    const user = userEvent.setup();
    render(<Page />);
    fill();
    changeAndBlur(screen.getByLabelText("Average gross weekly pay (£)"), {
      target: { value: "1000" },
    });
    await user.click(screen.getByRole("button", { name: "Calculate redundancy pay" }));
    expect(screen.getByText("£12,767.00")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Jurisdiction"), "NI");
    expect(screen.queryByText("£12,767.00")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate redundancy pay" }));
    expect(screen.getByText("£13,311.00")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.getByLabelText("Date of birth")).toHaveValue("");
    expect(screen.queryByText("£13,311.00")).not.toBeInTheDocument();
  });
  it("requires weekly pay instead of silently interpreting blank as zero", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Calculate redundancy pay" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your average gross weekly pay.");
  });
  it("explains unsupported dates", async () => {
    const user = userEvent.setup();
    render(<Page />);
    fill();
    changeAndBlur(screen.getByLabelText("Redundancy relevant date"), {
      target: { value: "2027-04-06" },
    });
    await user.click(screen.getByRole("button", { name: "Calculate redundancy pay" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Verified rates cover");
  });
  it("withholds an estimate for uncertain employment status", async () => {
    const user = userEvent.setup();
    render(<Page />);
    fill();
    await user.selectOptions(screen.getByLabelText("Employment status"), "unsure");
    await user.click(screen.getByRole("button", { name: "Calculate redundancy pay" }));
    expect(screen.getByRole("heading", { name: "Check eligibility" })).toBeInTheDocument();
    expect(screen.queryByText("£10,200.00")).not.toBeInTheDocument();
  });
});
