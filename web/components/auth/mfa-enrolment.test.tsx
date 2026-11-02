// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Outcome } from "@/lib/auth/request";

const attempt = vi.fn<(run: unknown) => Promise<Outcome<unknown>>>();
vi.mock("@/lib/auth/request", () => ({ attempt: (run: unknown) => attempt(run) }));

import { MfaEnrolment } from "./mfa-enrolment";

const SETUP = {
  ok: true,
  data: {
    secret: "JBSWY3DPEHPK3PXP",
    otpauth_uri: "otpauth://totp/Brand:a@b.c?secret=JBSWY3DPEHPK3PXP",
  },
} as const;
const CODES = Array.from({ length: 10 }, (_, index) => `code${index}-abcde`);

describe("MfaEnrolment", () => {
  beforeEach(() => attempt.mockReset());

  it("shows the QR code and the key, refuses a wrong code, then shows the 10 recovery codes once", async () => {
    attempt
      .mockResolvedValueOnce(SETUP)
      .mockResolvedValueOnce({
        ok: false,
        problem: { code: "INVALID_MFA_CODE", message: "That code is not right. Try the next one." },
      })
      .mockResolvedValueOnce({ ok: true, data: { recovery_codes: CODES } });
    const onDone = vi.fn();
    render(<MfaEnrolment onDone={onDone} />);

    expect(await screen.findByAltText("QR code for your authenticator app")).toHaveAttribute(
      "src",
      expect.stringContaining("data:image/png"),
    );
    expect(screen.getByText("JBSW Y3DP EHPK 3PXP")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(
      await screen.findByText("That code is not right. Try the next one."),
    ).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("6-digit code"), "654321");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    const list = await screen.findByRole("list", { name: "Recovery codes" });
    expect(list.querySelectorAll("li")).toHaveLength(10);
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "I've saved them" }));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("starts the set-up once, and says so when it cannot", async () => {
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: { code: "NETWORK", message: "We could not reach the server." },
    });
    render(<MfaEnrolment onDone={vi.fn()} onSignOut={vi.fn()} />);
    expect(await screen.findByText("We could not reach the server.")).toBeInTheDocument();
    await waitFor(() => expect(attempt).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
