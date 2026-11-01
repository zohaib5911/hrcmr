// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CalendarMonth, type DayMarker } from "./calendar-month";

function Calendar(props: Partial<React.ComponentProps<typeof CalendarMonth>> & { start?: string }) {
  const [focused, setFocused] = useState(props.start ?? "2026-11-18");
  return (
    <CalendarMonth focused={focused} onFocusedChange={setFocused} onSelect={() => {}} {...props} />
  );
}

const day = (name: RegExp | string) => screen.getByRole("button", { name });

// "Today" is part of a day's name, so the clock is fixed: these tests must not depend on the date they run.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 5, 15, 12, 0));
});
afterEach(() => {
  vi.useRealTimers();
});

describe("CalendarMonth", () => {
  it("shows the month of the focused day, Monday first, as a labelled grid", () => {
    render(<Calendar />);
    expect(screen.getByRole("heading", { name: "November 2026" })).toBeInTheDocument();
    expect(screen.getByRole("grid", { name: "November 2026" })).toBeInTheDocument();
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]);
  });

  it("names every day in full, so a screen reader hears the weekday and the date", () => {
    render(<Calendar />);
    expect(day("Sunday 1 November 2026")).toBeInTheDocument();
    expect(day("Monday 30 November 2026")).toBeInTheDocument();
  });

  it("has exactly one tab stop: the focused day", () => {
    render(<Calendar />);
    const stops = screen
      .getAllByRole("button")
      .filter((b) => b.hasAttribute("data-iso") && b.tabIndex === 0);
    expect(stops).toHaveLength(1);
    expect(stops[0]).toHaveAccessibleName(/Wednesday 18 November 2026/);
  });

  it("moves by day, week, month and year with the keyboard, turning the page as needed", async () => {
    render(<Calendar autoFocus />);
    const focusedName = () => document.activeElement?.getAttribute("aria-label") ?? "";
    expect(focusedName()).toMatch(/^Wednesday 18 November 2026/);
    await userEvent.keyboard("{ArrowRight}");
    expect(focusedName()).toMatch(/^Thursday 19 November 2026/);
    await userEvent.keyboard("{ArrowDown}");
    expect(focusedName()).toMatch(/^Thursday 26 November 2026/);
    await userEvent.keyboard("{ArrowDown}");
    expect(focusedName()).toMatch(/^Thursday 3 December 2026/);
    expect(screen.getByRole("heading", { name: "December 2026" })).toBeInTheDocument();
    await userEvent.keyboard("{PageUp}");
    expect(screen.getByRole("heading", { name: "November 2026" })).toBeInTheDocument();
    await userEvent.keyboard("{Shift>}{PageDown}{/Shift}");
    expect(screen.getByRole("heading", { name: "November 2027" })).toBeInTheDocument();
    await userEvent.keyboard("{Home}");
    expect(focusedName()).toMatch(/^Monday 1 November 2027/);
    await userEvent.keyboard("{End}");
    expect(focusedName()).toMatch(/^Sunday 7 November 2027/);
  });

  it("the previous and next buttons turn the page", async () => {
    render(<Calendar />);
    await userEvent.click(screen.getByRole("button", { name: "Next month" }));
    expect(screen.getByRole("heading", { name: "December 2026" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Previous month" }));
    await userEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(screen.getByRole("heading", { name: "October 2026" })).toBeInTheDocument();
  });

  it("choosing a day reports it, by click and by Enter", async () => {
    const onSelect = vi.fn();
    render(<Calendar onSelect={onSelect} autoFocus />);
    await userEvent.click(day(/^Friday 20 November 2026/));
    expect(onSelect).toHaveBeenLastCalledWith("2026-11-20");
    await userEvent.keyboard("{ArrowRight}{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith("2026-11-21");
  });

  it("will not choose a day outside min and max, or one the app says is unavailable, and says so", async () => {
    const onSelect = vi.fn();
    render(
      <Calendar
        onSelect={onSelect}
        min="2026-11-10"
        max="2026-11-25"
        isDisabled={(iso) => iso === "2026-11-18"}
      />,
    );
    for (const name of [
      /^Monday 9 November 2026/,
      /^Thursday 26 November 2026/,
      /^Wednesday 18 November 2026/,
    ]) {
      const button = day(name);
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAccessibleName(/not available/);
      await userEvent.click(button);
    }
    expect(onSelect).not.toHaveBeenCalled();
    await userEvent.click(day(/^Tuesday 17 November 2026/));
    expect(onSelect).toHaveBeenCalledWith("2026-11-17");
  });

  it("describes markers in the day's name, not only with a dot", () => {
    const markers = new Map<string, DayMarker>([
      ["2026-12-25", { label: "Bank holiday", tone: "info" }],
    ]);
    render(<Calendar start="2026-12-01" markers={markers} />);
    expect(day(/^Friday 25 December 2026.*Bank holiday/)).toBeInTheDocument();
  });

  it("says which day is today", () => {
    render(<Calendar start="2026-06-10" />);
    expect(day(/^Monday 15 June 2026, today/)).toBeInTheDocument();
  });

  it("marks the selected day and a chosen range", () => {
    render(<Calendar selected="2026-11-18" />);
    expect(day(/^Wednesday 18 November 2026.*selected/)).toBeInTheDocument();
    render(<Calendar range={{ start: "2026-11-03", end: "2026-11-05" }} />);
    expect(
      screen.getAllByRole("button", { name: /Wednesday 4 November 2026.*in the chosen range/ })
        .length,
    ).toBeGreaterThan(0);
  });

  it("shows leap years correctly", () => {
    render(<Calendar start="2024-02-10" />);
    expect(day(/^Thursday 29 February 2024/)).toBeInTheDocument();
  });
});
