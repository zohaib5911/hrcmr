// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

let pathname = "/rota";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

import { RouteLoading } from "./route-loading";
import { markShellReady } from "./shell-ready";

describe("RouteLoading", () => {
  it("shows the workspace splash before the shell has been on screen", () => {
    render(<RouteLoading />);
    expect(screen.getByText("Loading your workspace…")).toBeInTheDocument();
  });

  it("then shows a skeleton shaped like the coming page, inside the shell", () => {
    markShellReady();
    const { container, unmount } = render(<RouteLoading />);
    expect(screen.queryByText("Loading your workspace…")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector("[data-skeleton]")).toHaveAttribute("data-skeleton", "calendar");
    unmount();
    pathname = "/employees";
    render(<RouteLoading />);
    expect(document.querySelector("[data-skeleton]")).toHaveAttribute("data-skeleton", "list");
  });
});
