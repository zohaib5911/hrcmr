// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Page from "@/app/(marketing)/resources/tools/uk-sick-pay-calculator/page";

afterEach(() => vi.restoreAllMocks());
const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Calculate sick pay" }));
const result = () => within(screen.getByRole("region", { name: "Sick pay result" }));

describe("sick pay calculator page", () => {
  it("shows sources and computes SSP without transmitting or storing answers", () => {
    const request = vi.spyOn(globalThis, "fetch");
    const local = vi.spyOn(Storage.prototype, "setItem");
    render(<Page />);
    expect(
      screen.getByRole("heading", { level: 1, name: "UK sick pay calculator" }),
    ).toBeInTheDocument();
    fill("First day of sickness", "2026-06-01");
    fill("Last day of sickness", "2026-06-07");
    fill("Average weekly earnings (£)", "400");
    submit();
    expect(result().getByText("Total SSP").nextSibling).toHaveTextContent("£123.25");
    expect(result().getByRole("table")).toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
    expect(local).not.toHaveBeenCalled();
  });
  it("requires values and shows errors for pre-April-2026 absences", () => {
    render(<Page />);
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the start date");
    fill("First day of sickness", "2026-03-01");
    fill("Last day of sickness", "2026-03-10");
    fill("Average weekly earnings (£)", "400");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("6 April 2026");
  });
  it("explains non-eligibility and resets", () => {
    render(<Page />);
    fill("Worker status", "other");
    fill("First day of sickness", "2026-06-01");
    fill("Last day of sickness", "2026-06-07");
    fill("Average weekly earnings (£)", "400");
    submit();
    expect(result().getByRole("status")).toHaveTextContent("Self-employed");
    fireEvent.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.getByLabelText("First day of sickness")).toHaveValue("");
    expect(result().queryByRole("status")).not.toBeInTheDocument();
  });
});
