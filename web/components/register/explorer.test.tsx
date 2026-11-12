// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { registerFixture } from "@/tests/fixtures/register";
import { RegisterExplorer } from "./explorer";

const get = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth/request", () => ({
  attempt: (run: (client: { GET: typeof get }) => unknown) => run({ GET: get }),
}));
beforeEach(() => get.mockReset().mockResolvedValue({ ok: true, data: registerFixture }));

async function ready() {
  await screen.findByText("51 matching sponsors in the selected publication.");
}

describe("RegisterExplorer", () => {
  it("shows pulse, all breakdowns and all four views", async () => {
    const user = userEvent.setup();
    render(<RegisterExplorer />);
    await ready();
    expect(screen.getByRole("img", { name: /Register pulse/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Schematic map/ })).toBeInTheDocument();
    for (const name of [
      "Then and now",
      "Sponsors by town",
      "Routes",
      "Ratings",
      "Licence types",
      "Placement precision",
      "Industries",
      "Newest on the register",
    ])
      expect(screen.getByRole("heading", { name, exact: true })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Trend", exact: true }));
    expect(screen.getByRole("img", { name: "Sponsor count by publication" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table", exact: true }));
    expect(
      within(screen.getByRole("table", { name: "Matching sponsors" })).getByText("Stable Ltd"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "List", exact: true }));
    expect(screen.getByRole("heading", { name: "Stable Ltd" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/public/register/explore", {
        params: { query: { window: "30", page: 2 } },
      }),
    );
  });

  it("sends search, filters, timeline and compare window, resetting pagination", async () => {
    const user = userEvent.setup();
    render(<RegisterExplorer />);
    await ready();
    await user.type(screen.getByRole("searchbox"), "Leeds");
    await user.click(screen.getByRole("button", { name: "Search register" }));
    for (const [label, value] of [
      ["Region", "Yorkshire and The Humber"],
      ["Route", "Skilled Worker"],
      ["Rating and licence", "Worker (A rating)"],
      ["Industry", "J"],
      ["Compare window", "90"],
    ]) {
      await user.selectOptions(screen.getByRole("combobox", { name: label, exact: true }), value!);
      await ready();
    }
    fireEvent.change(screen.getByRole("slider", { name: "Publication timeline" }), {
      target: { value: "0" },
    });
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/public/register/explore", {
        params: {
          query: {
            q: "Leeds",
            region: "Yorkshire and The Humber",
            route: "Skilled Worker",
            rating: "Worker (A rating)",
            industry: "J",
            window: "90",
            page: 1,
            publication_id: registerFixture.publications![0]!.id,
          },
        },
      }),
    );
    await user.click(screen.getByRole("button", { name: "Reset filters" }));
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/public/register/explore", {
        params: { query: { window: "30", page: 1 } },
      }),
    );
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("recovers from errors and explains an empty archive", async () => {
    get.mockResolvedValueOnce({ ok: false, problem: { message: "Register unavailable" } });
    const user = userEvent.setup();
    render(<RegisterExplorer />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Register unavailable");
    get.mockResolvedValue({ ok: true, data: { publications: [] } });
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByText("No register publications are available yet."),
    ).toBeInTheDocument();
  });

  it("explains no matches and disables pagination", async () => {
    get.mockResolvedValue({ ok: true, data: { ...registerFixture, total: 0, results: [] } });
    const user = userEvent.setup();
    render(<RegisterExplorer />);
    await screen.findByText("0 matching sponsors in the selected publication.");
    expect(screen.getByText(/No sponsors match these filters/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table", exact: true }));
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });
});
