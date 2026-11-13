// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlatformBar } from "./platform-bar";

describe("PlatformBar", () => {
  it("names the admin area in a bar that is not a heading", () => {
    render(<PlatformBar />);
    const bar = screen.getByTestId("platform-bar");
    expect(bar).toHaveTextContent("Platform admin");
    expect(screen.getByRole("banner")).toBe(bar);
    // Pages keep their own h1; the bar must not become a second one.
    expect(bar.tagName).not.toMatch(/^H[1-6]$/);
    expect(screen.queryByRole("heading")).toBeNull();
  });
});
