// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/sponsor-licence-cost-calculator/page";

afterEach(() => vi.restoreAllMocks());

describe("public sponsor licence cost calculator", () => {
  it("renders the sources table and privacy notice", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sponsor licence cost");
    expect(screen.getByText(/Nothing you enter is saved or sent/)).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getAllByRole("link").length).toBeGreaterThan(5);
  });

  it("calculates locally, rejects bad input and resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    await user.type(screen.getByLabelText("Annual turnover (£)"), "20000000");
    await user.type(screen.getByLabelText("Total assets (£)"), "10000000");
    await user.type(screen.getByLabelText("Employees"), "100");
    await user.clear(screen.getByLabelText("Certificate length (months, 1–60)"));
    await user.type(screen.getByLabelText("Certificate length (months, 1–60)"), "24");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    const result = screen.getByRole("region", { name: "Cost result" });
    // 24-month CoS + 14 days gives 2.5 years IHS.
    expect(result).toHaveTextContent("medium or large");
    expect(result).toHaveTextContent("£1,682.00");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByRole("heading", { name: "Your estimated costs" })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Number of workers"));
    await user.type(screen.getByLabelText("Number of workers"), "0");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("includes nursing ISC in the displayed Health and Care totals", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.type(screen.getByLabelText("Annual turnover (£)"), "20000000");
    await user.type(screen.getByLabelText("Total assets (£)"), "10000000");
    await user.type(screen.getByLabelText("Employees"), "100");
    await user.selectOptions(screen.getByLabelText("Route"), "health_care");
    await user.type(screen.getByLabelText("Occupation (SOC) code"), "2231");
    await user.clear(screen.getByLabelText("Certificate length (months, 1–60)"));
    await user.type(screen.getByLabelText("Certificate length (months, 1–60)"), "24");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    const result = screen.getByRole("region", { name: "Cost result" });
    const charge = within(result).getByText("Immigration Skills Charge × 1");
    expect(charge.parentElement).toHaveTextContent("£2,640.00");
    expect(within(result).getByText("Employer total").parentElement).toHaveTextContent("£4,847.00");
    expect(within(result).getByText("Worker-side total").parentElement).toHaveTextContent(
      "£324.00",
    );
    expect(result).toHaveTextContent("Grand total: £5,171.00");
  });
  it("shows matching visa assumptions and boundary IHS in the result and comparison", async () => {
    const user = userEvent.setup();
    render(<Page />);
    expect(screen.getByText(/visa normally ends 14 days/)).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Certificate length (months, 1–60)"));
    await user.type(screen.getByLabelText("Certificate length (months, 1–60)"), "36");
    await user.clear(screen.getByLabelText("Child dependants (under 18) per worker"));
    await user.type(screen.getByLabelText("Child dependants (under 18) per worker"), "1");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    const result = screen.getByRole("region", { name: "Cost result" });
    expect(result).toHaveTextContent(
      "CoS employment: 36 months. Estimated visa period: 36 months + 14 days.",
    );
    expect(result).toHaveTextContent(
      "Earlier visa grants or different dependant dates need review",
    );
    expect(within(result).getByText("Healthcare surcharge, adult").parentElement).toHaveTextContent(
      "£3,622.50",
    );
    expect(within(result).getByText("Healthcare surcharge, child").parentElement).toHaveTextContent(
      "£2,716.00",
    );
    const table = within(result).getByRole("table");
    expect(table).toHaveTextContent("IHS includes 14 days after CoS end");
    const row = within(table).getByRole("rowheader", { name: "36" }).parentElement!;
    expect(row).toHaveTextContent("36 months + 14 days");
    expect(row).toHaveTextContent("£7,976.50"); // 2 × £819 + adult £3622.50 + child £2716
    expect(within(result).getByText("Worker-side total").parentElement).toHaveTextContent(
      "£7,976.50",
    );
  });

  it("asks for GP specialty training confirmation and applies the four-month exception", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.type(screen.getByLabelText("Occupation (SOC) code"), "2211");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    expect(screen.getByRole("alert")).toHaveTextContent("confirm GP specialty training");
    await user.selectOptions(screen.getByLabelText("Is this GP specialty training?"), "yes");
    await user.click(screen.getByRole("button", { name: "Calculate costs" }));
    const result = screen.getByRole("region", { name: "Cost result" });
    expect(result).toHaveTextContent(
      "Estimated visa period: 40 months (includes 4 months for GP specialty training)",
    );
    expect(within(result).getByRole("table")).toHaveTextContent(
      "IHS includes 4 months for GP specialty training",
    );
  });
});
