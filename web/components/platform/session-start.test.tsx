// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SessionStart, type StartResult } from "./session-start";

describe("SessionStart", () => {
  it("says it is starting, then goes on to the page the person asked for", async () => {
    const navigate = vi.fn();
    const run = vi.fn(async (): Promise<StartResult> => ({ ok: true }));
    render(<SessionStart next="/rules" run={run} navigate={navigate} />);
    expect(screen.getByRole("status")).toHaveTextContent("Starting a platform session");
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/rules"));
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("sends a refusal to the refusal page with its code", async () => {
    const navigate = vi.fn();
    const run = async (): Promise<StartResult> => ({ ok: false, code: "MFA_REQUIRED" });
    render(<SessionStart next="/rules" run={run} navigate={navigate} />);
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("/session-required?code=MFA_REQUIRED"),
    );
  });

  it("goes to the home page when the next path is not safe", async () => {
    const navigate = vi.fn();
    const run = async (): Promise<StartResult> => ({ ok: true });
    render(<SessionStart next="//evil.example" run={run} navigate={navigate} />);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
  });
});
