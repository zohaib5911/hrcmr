// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Holiday from "@/app/(marketing)/resources/tools/holiday-entitlement-calculator/page";
import TakeHome from "@/app/(marketing)/resources/tools/uk-take-home-salary-calculator/page";
import Employer from "@/app/(marketing)/resources/tools/uk-employer-cost-calculator/page";
import Redundancy from "@/app/(marketing)/resources/tools/uk-redundancy-pay-calculator/page";
import Notice from "@/app/(marketing)/resources/tools/uk-notice-pay-calculator/page";
import Sick from "@/app/(marketing)/resources/tools/uk-sick-pay-calculator/page";
import Wage from "@/app/(marketing)/resources/tools/uk-minimum-wage-underpayment-checker/page";
import Risk from "@/app/(marketing)/resources/tools/risk-assessment-template/page";
import { storageKey } from "@/lib/calculators/risk-assessment-template";

const tools = [
  {
    Page: Holiday,
    preset: "Part time, 3 days a week",
    region: "Holiday result",
    field: "Days worked per week",
    value: "4",
  },
  {
    Page: TakeHome,
    preset: "£35,000 standard salary",
    region: "Take-home result",
    field: "Annual salary (£)",
    value: "40000",
  },
  {
    Page: Employer,
    preset: "£35,000 employee aged 30",
    region: "Employer cost result",
    field: "Annual gross salary (£)",
    value: "40000",
  },
  {
    Page: Redundancy,
    preset: "10 years, £600 weekly pay",
    region: "Redundancy result",
    field: "Average gross weekly pay (£)",
    value: "500",
  },
  {
    Page: Notice,
    preset: "Employer notice, 6 years of service",
    region: "Notice result",
    field: "Weekly pay (£)",
    value: "600",
  },
  {
    Page: Sick,
    preset: "One week, £500 weekly earnings",
    region: "Sick pay result",
    field: "Average weekly earnings (£)",
    value: "100",
  },
  {
    Page: Wage,
    preset: "40 hours, £520 weekly pay",
    region: "Minimum wage result",
    field: "Gross period pay before the reductions below (£)",
    value: "400",
  },
];

function expectFrame() {
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
  for (const name of ["Quick answer", "How it works", "Sources and dates", "Questions"])
    expect(screen.getByRole("region", { name })).toBeInTheDocument();
  expect(screen.getByText("Free tool")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "More tools" })).toBeInTheDocument();
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("employment tool frames and live scenarios", () => {
  it.each(tools)(
    "$region supports presets, live edits, invalid answers and reset locally",
    ({ Page, preset, region, field, value }) => {
      const request = vi.spyOn(globalThis, "fetch");
      const save = vi.spyOn(Storage.prototype, "setItem");
      render(<Page />);
      expectFrame();
      const output = screen.getByRole("region", { name: region });
      const incomplete = output.textContent;
      fireEvent.click(screen.getByRole("button", { name: preset }));
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(within(output).getByRole("heading", { name: "2. Live result" })).toBeInTheDocument();
      expect(output.textContent).not.toBe(incomplete);
      const original = output.textContent;
      fireEvent.change(screen.getByLabelText(field), { target: { value } });
      expect(output.textContent).not.toBe(original);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      fireEvent.change(screen.getByLabelText(field), { target: { value: "-1" } });
      expect(screen.getByRole("alert")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Reset answers" }));
      expect(output.textContent).toBe(incomplete);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(request).not.toHaveBeenCalled();
      expect(save).not.toHaveBeenCalled();
    },
  );

  it("risk scenario previews, saves, restores and clears only the browser draft", () => {
    const request = vi.spyOn(globalThis, "fetch");
    const view = render(<Risk />);
    expectFrame();
    expect(screen.getByText(/Your draft is saved only in this browser/)).toBeInTheDocument();
    expect(screen.queryByText(/Nothing you enter is saved or sent/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Office walkway example" }));
    const preview = screen.getByRole("region", { name: "Assessment preview" });
    expect(preview).toHaveTextContent("Trailing cables");
    expect(preview).toHaveTextContent("Draft incomplete");
    fireEvent.change(screen.getByLabelText("Organisation"), { target: { value: "My workplace" } });
    expect(preview).toHaveTextContent("My workplace");
    expect(JSON.parse(localStorage.getItem(storageKey)!)).toMatchObject({
      organisation: "My workplace",
    });
    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    view.unmount();
    render(<Risk />);
    expect(screen.getByLabelText("Organisation")).toHaveValue("My workplace");
    fireEvent.click(screen.getByRole("button", { name: "Clear saved draft" }));
    expect(localStorage.getItem(storageKey)).toBeNull();
    expect(screen.getByLabelText("Organisation")).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent("Draft cleared from this browser.");
    expect(request).not.toHaveBeenCalled();
  });
});
