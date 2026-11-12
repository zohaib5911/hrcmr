// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/uk-notice-pay-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("uk notice pay calculator page", () => {
  it("shows sources and calculates locally", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getAllByRole("row")).toHaveLength(4);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2020-06-01" } });
    fireEvent.change(screen.getByLabelText("Date notice is given"), {
      target: { value: "2026-11-12" },
    });
    fireEvent.change(screen.getByLabelText("Weekly pay (£)"), { target: { value: "500" } });
    await user.click(screen.getByRole("button", { name: "Work out notice pay" }));
    expect(screen.getByText("£3,000.00")).toBeInTheDocument();
    expect(screen.getByText("2026-12-24")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("reports a validation error", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Work out notice pay" }));
    expect(screen.getByText("Enter both dates.")).toBeInTheDocument();
  });
});
