// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { REGIONS, RegionMap } from "./region-map";
import { MAP_HEIGHT, MAP_WIDTH } from "./uk-regions";

describe("RegionMap", () => {
  it("draws the 12 ITL1 regions from real boundaries inside the frame", () => {
    expect(REGIONS).toHaveLength(12);
    for (const r of REGIONS) {
      const [x, y, w, h] = r.box;
      expect(x).toBeGreaterThanOrEqual(0);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(x + w).toBeLessThanOrEqual(MAP_WIDTH);
      expect(y + h).toBeLessThanOrEqual(MAP_HEIGHT);
      // A real outline, not a box: many points per region.
      expect(r.d.split(" ").length).toBeGreaterThan(40);
    }
  });

  it("labels every region with the API figures and lists them in a table", () => {
    const { container } = render(<RegionMap counts={{ London: { count: 1200, delta: 5 } }} />);
    expect(container.querySelectorAll("path[data-region]")).toHaveLength(12);
    expect(screen.getByRole("group", { name: /UK regions/ })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "London: 1,200 sponsors (+5 today)" }),
    ).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("button", { name: "Wales: no data" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Sponsors by region" });
    const london = within(table).getByRole("row", { name: /London/ });
    expect(london).toHaveTextContent("1,200");
    expect(london).toHaveTextContent("+5");
    expect(within(table).getAllByRole("row")).toHaveLength(13);
  });

  it("zooms into a chosen region by keyboard and shows its tooltip", async () => {
    const { container } = render(<RegionMap counts={{ Scotland: { count: 40, delta: -2 } }} />);
    const scotland = screen.getByRole("button", { name: /^Scotland:/ });
    const zoom = container.querySelector("[data-zoom]")!;
    expect(zoom).toHaveAttribute("data-zoom", "none");
    fireEvent.focus(scotland);
    expect(screen.getByTestId("region-tooltip")).toHaveTextContent(
      "Scotland40 sponsors · -2 today",
    );
    fireEvent.keyDown(scotland, { key: "Enter" });
    expect(scotland).toHaveAttribute("aria-pressed", "true");
    expect(zoom).toHaveAttribute("data-zoom", "Scotland");
    await waitFor(() => expect(zoom.getAttribute("transform")).not.toBe("translate(0 0) scale(1)"));
    fireEvent.keyDown(scotland, { key: "Escape" });
    expect(scotland).toHaveAttribute("aria-pressed", "false");
    expect(zoom).toHaveAttribute("data-zoom", "none");
  });
});
