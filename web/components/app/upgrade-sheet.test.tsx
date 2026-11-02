// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/client";
import { PLAN_REQUIRED_EVENT } from "@/lib/auth/request";

import { SessionProvider } from "./session-context";
import { UpgradeSheet } from "./upgrade-sheet";

const meWith = (permissions: string[]) => ({ permissions }) as components["schemas"]["MeResponse"];

function announce(message: string) {
  act(() => {
    window.dispatchEvent(new CustomEvent(PLAN_REQUIRED_EVENT, { detail: { message } }));
  });
}

describe("UpgradeSheet", () => {
  it("stays closed until a request is refused for being on the free plan", () => {
    render(
      <SessionProvider me={meWith(["billing.manage"])}>
        <UpgradeSheet />
      </SessionProvider>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sends someone who can subscribe to the plans", async () => {
    render(
      <SessionProvider me={meWith(["billing.manage"])}>
        <UpgradeSheet />
      </SessionProvider>,
    );
    announce("Subscribe to add employees.");
    const dialog = await screen.findByRole("dialog", { name: "Subscribe to carry on" });
    expect(dialog).toHaveTextContent("Subscribe to add employees.");
    expect(screen.getByRole("link", { name: "See the plans" })).toHaveAttribute(
      "href",
      "/company/billing",
    );
  });

  it("tells everyone else to ask a Company Admin", async () => {
    render(
      <SessionProvider me={meWith(["leave.request.read_own"])}>
        <UpgradeSheet />
      </SessionProvider>,
    );
    announce("Subscribe to add employees.");
    expect(await screen.findByText(/Ask a Company Admin/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "See the plans" })).not.toBeInTheDocument();
  });
});
