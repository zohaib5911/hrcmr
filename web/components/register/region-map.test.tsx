// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { REGIONS, RegionMap } from "./region-map";

describe("RegionMap", () => {
  it("draws all 12 ITL1 regions with counts and deltas", () => {
    const { container } = render(<RegionMap counts={{ London: { count: 1200, delta: 5 } }} />);
    expect(REGIONS).toHaveLength(12);
    expect(container.querySelectorAll("path[data-region]")).toHaveLength(12);
    expect(container.querySelector('[data-region="London"] title')).toHaveTextContent(
      "London: 1,200 (+5 today)",
    );
    expect(container.querySelector('[data-region="Wales"] title')).toHaveTextContent("no data");
    expect(screen.getByRole("img")).toHaveAccessibleName(/UK regions/);
    expect(screen.getByText("Scotland: 0")).toBeInTheDocument();
  });
});
