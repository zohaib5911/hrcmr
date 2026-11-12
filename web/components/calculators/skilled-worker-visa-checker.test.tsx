// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/skilled-worker-visa-checker/page";

afterEach(() => vi.restoreAllMocks());

describe("skilled worker visa checker page", () => {
  it("shows the privacy notice and the sources table", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Skilled Worker visa checker",
    );
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getAllByRole("link").length).toBe(4);
  });

  it("searches locally, checks a salary and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await user.click(screen.getByRole("button", { name: "Check eligibility" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose an occupation");
    await user.type(screen.getByLabelText("SOC code or job title"), "chief executives");
    await user.click(screen.getByRole("button", { name: /1111 Chief executives/ }));
    await user.type(screen.getByLabelText("Annual salary offered"), "90000");
    await user.click(screen.getByRole("button", { name: "Check eligibility" }));
    const result = screen.getByRole("region", { name: "Checker result" });
    expect(result).toHaveTextContent("Salary requirement met");
    expect(result).toHaveTextContent("B2");
    expect(fetchSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByText("Salary requirement met")).not.toBeInTheDocument();
  });
});
