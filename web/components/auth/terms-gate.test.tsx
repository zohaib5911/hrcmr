// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Outcome } from "@/lib/auth/request";

const refresh = vi.fn();
const push = vi.fn();
const attempt = vi.fn<(run: unknown) => Promise<Outcome<unknown>>>();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push }) }));
vi.mock("@/lib/auth/request", () => ({ attempt: (run: unknown) => attempt(run) }));

import { TermsGate } from "./terms-gate";

describe("TermsGate", () => {
  beforeEach(() => {
    refresh.mockReset();
    push.mockReset();
    attempt.mockReset();
  });

  it("cannot be closed with Esc, needs the box ticked, and then lets the page carry on", async () => {
    attempt.mockResolvedValueOnce({ ok: true, data: undefined });
    render(<TermsGate version="2026-11" />);
    const dialog = screen.getByRole("dialog", { name: "Please accept our terms" });

    await userEvent.keyboard("{Escape}");
    expect(dialog).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Accept the terms to continue.")).toBeInTheDocument();
    expect(attempt).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("says so when sign-out fails, stays put, and a retry signs out (ISS-03)", async () => {
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: { code: "NETWORK", message: "We could not reach the server." },
    });
    render(<TermsGate version="2026-11" />);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByText(/We could not confirm you are signed out/)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();

    attempt.mockResolvedValueOnce({ ok: true, data: undefined });
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });
});
