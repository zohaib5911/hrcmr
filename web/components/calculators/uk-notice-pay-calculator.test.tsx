// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/uk-notice-pay-calculator/page";

// DatePicker commits typed dates on blur, as a person leaves the field.
function changeAndBlur(...args: Parameters<typeof fireEvent.change>) {
  fireEvent.change(...args);
  fireEvent.blur(args[0]);
}

afterEach(() => vi.restoreAllMocks());

describe("uk notice pay calculator page", () => {
  it("shows sources and calculates locally", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getAllByRole("row")).toHaveLength(4);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    changeAndBlur(screen.getByLabelText("Start date"), { target: { value: "2020-06-01" } });
    changeAndBlur(screen.getByLabelText("Date notice is given"), {
      target: { value: "2026-11-12" },
    });
    changeAndBlur(screen.getByLabelText("Weekly pay (£)"), { target: { value: "500" } });
    await user.click(screen.getByRole("button", { name: "Work out notice pay" }));
    expect(screen.getByText("£3,000.00")).toBeInTheDocument();
    expect(screen.getByText("24 Dec 2026")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("reports a validation error", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Work out notice pay" }));
    expect(screen.getByText("Enter both dates.")).toBeInTheDocument();
  });
});
