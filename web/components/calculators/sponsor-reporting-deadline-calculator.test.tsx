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
    const result = screen.getByRole("region", { name: "Deadline result" });
    expect(result).toHaveTextContent("Incomplete");
    fireEvent.change(screen.getByLabelText("Event date"), { target: { value: "2026-08-28" } });
    expect(result).toHaveTextContent("2026-09-28");
    expect(result).not.toHaveTextContent("Incomplete");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows the frame, fills presets and updates live, then resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByRole("heading", { name: "Quick answer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questions" })).toBeInTheDocument();
    const result = screen.getByRole("region", { name: "Deadline result" });
    await user.click(screen.getByRole("button", { name: "Worker did not start, Scotland" }));
    expect(screen.getByLabelText("Event date")).toHaveValue("2026-11-27");
    expect(screen.getByLabelText("Nation (bank holidays)")).toHaveValue("scotland");
    // St Andrew's Day (Monday 30 November) is skipped in Scotland only.
    expect(result).toHaveTextContent("2026-12-14");
    await user.selectOptions(screen.getByLabelText("Nation (bank holidays)"), "england-and-wales");
    expect(result).toHaveTextContent("2026-12-11");
    await user.click(screen.getByRole("button", { name: "Salary increase" }));
    expect(result).toHaveTextContent("No fixed reporting deadline");
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(result).not.toHaveTextContent("Your deadline");
    expect(screen.getByLabelText("Event date")).toHaveValue("");
  });
});
