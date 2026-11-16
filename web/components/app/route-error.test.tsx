// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RouteError } from "./route-error";

describe("RouteError", () => {
  it("reports the error, shows no detail of it, and offers a retry, a way home and the reference", async () => {
    const report = vi.fn();
    const reset = vi.fn();
    const error = Object.assign(new Error("secret internal detail"), { digest: "abc123" });
    render(
      <RouteError
        error={error}
        reset={reset}
        report={report}
        homeHref="/dashboard"
        homeLabel="Go to the dashboard"
      />,
    );

    expect(report).toHaveBeenCalledWith(error);
    expect(screen.getByRole("heading", { level: 1, name: "Something went wrong" })).toBeVisible();
    expect(screen.queryByText(/secret internal detail/)).toBeNull();
    expect(screen.getByText("abc123")).toBeVisible();
    expect(screen.getByRole("link", { name: "Go to the dashboard" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("leaves the reference out when there is none", () => {
    render(<RouteError error={new Error("x")} reset={() => {}} report={() => {}} />);
    expect(screen.queryByText(/Request ID/)).toBeNull();
    expect(screen.getByRole("link", { name: "Go to the home page" })).toHaveAttribute("href", "/");
  });
});
