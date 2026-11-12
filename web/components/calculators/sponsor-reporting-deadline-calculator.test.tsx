// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/sponsor-reporting-deadline-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("sponsor reporting deadline calculator page", () => {
  it("shows both sources and calculates locally", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getAllByRole("row")).toHaveLength(3);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await user.selectOptions(screen.getByLabelText("Event type"), "org-change");
    fireEvent.change(screen.getByLabelText("Event date"), { target: { value: "2026-08-28" } });
    await user.click(screen.getByRole("button", { name: "Work out the deadline" }));
    expect(screen.getByText("2026-09-28")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
