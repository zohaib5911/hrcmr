// @vitest-environment jsdom
import { readFileSync } from "node:fs";

import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/ilr-citizenship-checker/page";
import { settlementSources } from "@/lib/calculators/ilr-citizenship-checker";

// DatePicker commits typed dates on blur, as a person leaves the field.
function changeAndBlur(...args: Parameters<typeof fireEvent.change>) {
  fireEvent.change(...args);
  fireEvent.blur(args[0]);
}

afterEach(() => vi.restoreAllMocks());

function dates() {
  changeAndBlur(screen.getByLabelText("Qualifying route residence start"), {
    target: { value: "2021-06-20" },
  });
  changeAndBlur(screen.getByLabelText("UK residence start for citizenship"), {
    target: { value: "2021-06-20" },
  });
}

describe("public ILR and citizenship checker", () => {
  it("renders 14 pathways, official source evidence and the shared privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "ILR and citizenship checker",
    );
    expect(within(screen.getByLabelText("Visa pathway")).getAllByRole("option")).toHaveLength(14);
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    const table = screen.getByRole("table");
    for (const source of settlementSources) {
      expect(within(table).getByRole("link", { name: source.title })).toHaveAttribute(
        "href",
        source.url,
      );
    }
  });

  it("calculates locally, updates the citizenship basis live and resets answers", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    dates();
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "20 Jun 2027",
    );
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "Indicative citizenship",
    );
    await user.selectOptions(
      screen.getByLabelText("Married to or civil partner of a British citizen?"),
      "yes",
    );
    expect(
      screen.getByLabelText("Days abroad in the citizenship 3-year period"),
    ).toBeInTheDocument();
    changeAndBlur(screen.getByLabelText("Actual ILR grant date (optional)"), {
      target: { value: "2026-11-15" },
    });
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "Earliest citizenship residence milestone: 15 Nov 2026",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(
      screen.queryByRole("region", { name: "Settlement timeline result" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Qualifying route residence start")).toHaveValue("");
    expect(screen.getByLabelText("Actual ILR grant date (optional)")).toHaveValue("");
  });

  it("shows absence and historical residence review flags", async () => {
    const user = userEvent.setup();
    render(<Page />);
    dates();
    await user.selectOptions(screen.getByLabelText("Visa pathway"), "long_residence");
    changeAndBlur(screen.getByLabelText("Days abroad in the citizenship 5-year period"), {
      target: { value: "451" },
    });
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "Individual residence review required",
    );
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "Absences need individual review",
    );
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "physical presence",
    );
  });

  it("reports inconsistent dates and absence totals accessibly", () => {
    render(<Page />);
    dates();
    changeAndBlur(screen.getByLabelText("UK residence start for citizenship"), {
      target: { value: "2022-01-01" },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("UK residence cannot start after");
    dates();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    changeAndBlur(screen.getByLabelText("Days abroad in the final 12 months before citizenship"), {
      target: { value: "1" },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Last-year absences cannot exceed");
  });

  it("shows the frame, fills presets and flags incomplete answers", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByRole("heading", { name: "Quick answer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questions" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Skilled Worker since June 2021" }));
    expect(screen.getByLabelText("Qualifying route residence start")).toHaveValue("20 Jun 2021");
    const result = screen.getByRole("region", { name: "Settlement timeline result" });
    expect(result).toHaveTextContent("ILR qualifying-residence milestone: 20 Jun 2026");
    await user.click(screen.getByRole("button", { name: "Long residence with long absences" }));
    expect(screen.getByRole("region", { name: "Settlement timeline result" })).toHaveTextContent(
      "Absences need individual review",
    );
    changeAndBlur(screen.getByLabelText("UK residence start for citizenship"), {
      target: { value: "" },
    });
    expect(
      screen.queryByRole("region", { name: "Settlement timeline result" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Incomplete: enter both residence start dates/)).toBeInTheDocument();
  });

  it("keeps the page and form free of transport and persistence", () => {
    for (const file of [
      "./ilr-citizenship-checker.tsx",
      "../../app/(marketing)/resources/tools/ilr-citizenship-checker/page.tsx",
    ]) {
      expect(readFileSync(new URL(file, import.meta.url), "utf8")).not.toMatch(
        /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
      );
    }
  });
});
