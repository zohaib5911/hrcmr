// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DateTimePicker } from "./date-time-picker";

function Harness({
  initial = null,
  onChange,
}: {
  initial?: string | null;
  onChange?: (value: string | null) => void;
}) {
  const [value, setValue] = useState<string | null>(initial);
  return (
    <DateTimePicker
      legend="Interview date and time"
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe("DateTimePicker", () => {
  it("shows a stored value the UK way, in a named group", () => {
    render(<Harness initial="2026-11-01T09:30" />);
    expect(screen.getByRole("group", { name: "Interview date and time" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Date" })).toHaveValue("1 Nov 2026");
    expect(screen.getByRole("textbox", { name: "Time" })).toHaveValue("09:30");
  });

  it("gives the datetime-local wire value only once both halves are filled in", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await userEvent.type(screen.getByRole("textbox", { name: "Date" }), "1/11/26{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole("textbox", { name: "Date" })).toHaveValue("1 Nov 2026");
    await userEvent.type(screen.getByRole("textbox", { name: "Time" }), "930{Enter}");
    expect(onChange).toHaveBeenLastCalledWith("2026-11-01T09:30");
  });
});
