// @vitest-environment jsdom
import { readFileSync } from "node:fs";

import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/right-to-work-october-2026-checker/page";
import { rightToWorkSource } from "@/lib/calculators/right-to-work-october-2026-checker";

afterEach(() => vi.restoreAllMocks());

describe("public right-to-work calculator", () => {
  it("renders the shared source table and privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Right-to-work October 2026 checker",
    );
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByRole("link")).toHaveAttribute("href", rightToWorkSource.url);
    expect(within(table).getByText(rightToWorkSource.checkedOn)).toBeInTheDocument();
    expect(within(table).getByText(rightToWorkSource.validFrom)).toBeInTheDocument();
  });

  it("checks local answers without network or storage writes and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    await user.selectOptions(screen.getByLabelText("Is the work carried out in the UK?"), "yes");
    await user.selectOptions(
      screen.getByLabelText("Buying directly from an independent business?"),
      "no",
    );
    fireEvent.change(screen.getByLabelText("Employment / engagement start date"), {
      target: { value: "2026-10-01" },
    });
    await user.selectOptions(
      screen.getByLabelText("Contracting workers to deliver services onwards?"),
      "no",
    );
    await user.selectOptions(screen.getByLabelText("Does the contract permit substitution?"), "no");
    const result = screen.getByRole("region", { name: "Checker result" });
    expect(result).toHaveTextContent("In scope");
    expect(result).toHaveTextContent("2 years after");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByRole("heading", { name: "Your scope check" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Employment / engagement start date")).toHaveValue("");
  });

  it("asks for the contractual date and updates the result live as answers change", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.selectOptions(screen.getByLabelText("Engagement type"), "matching");
    await user.selectOptions(screen.getByLabelText("Is the work carried out in the UK?"), "yes");
    expect(screen.getByLabelText("Relevant contractual arrangement date")).toBeInTheDocument();
    const result = screen.getByRole("region", { name: "Checker result" });
    expect(result).toHaveTextContent("Needs review");
    expect(result).toHaveTextContent("Incomplete or needs review");
    fireEvent.change(screen.getByLabelText("Relevant contractual arrangement date"), {
      target: { value: "2026-10-01" },
    });
    expect(result).toHaveTextContent("written terms");
  });

  it("hides irrelevant questions for overseas work", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.selectOptions(screen.getByLabelText("Is the work carried out in the UK?"), "no");
    expect(screen.queryByLabelText("Employment / engagement start date")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Checker result" })).toHaveTextContent(
      "outside the UK",
    );
  });

  it("shows the frame sections and fills the form from a preset", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByRole("heading", { name: "Quick answer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questions" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /1\. The working arrangement/ }),
    ).toBeInTheDocument();
    const result = screen.getByRole("region", { name: "Checker result" });
    expect(result).not.toHaveTextContent("Your scope check");
    await user.click(screen.getByRole("button", { name: "Online matching service" }));
    expect(screen.getByLabelText("Engagement type")).toHaveValue("matching");
    expect(screen.getByLabelText("Relevant contractual arrangement date")).toHaveValue(
      "2026-11-02",
    );
    expect(result).toHaveTextContent("Extended liability");
    expect(result).toHaveTextContent("written terms");
    await user.click(screen.getByRole("button", { name: "Work done outside the UK" }));
    expect(result).toHaveTextContent("outside the UK");
  });

  it("has no transport or persistence in the template, page or client form", () => {
    for (const file of [
      "./calculator-template.tsx",
      "./right-to-work-checker.tsx",
      "../../app/(marketing)/resources/tools/right-to-work-october-2026-checker/page.tsx",
    ]) {
      const source = readFileSync(new URL(file, import.meta.url), "utf8");
      expect(source).not.toMatch(
        /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
      );
    }
  });
});
