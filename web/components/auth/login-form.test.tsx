// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Outcome } from "@/lib/auth/request";

const push = vi.fn();
const attempt = vi.fn<(run: unknown) => Promise<Outcome<unknown>>>();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/auth/request", () => ({ attempt: (run: unknown) => attempt(run) }));

import { LoginForm } from "./login-form";

async function fill(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("Email address"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
}

describe("LoginForm", () => {
  beforeEach(() => {
    push.mockReset();
    attempt.mockReset();
  });

  it("asks for both fields before it calls the API", async () => {
    render(<LoginForm />);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(attempt).not.toHaveBeenCalled();
  });

  it("goes to the dashboard, or to the second step when the API asks for one", async () => {
    attempt.mockResolvedValueOnce({ ok: true, data: { mfa_required: false } });
    const { unmount } = render(<LoginForm />);
    await fill("amira@example.com", "a long enough password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    unmount();

    attempt.mockResolvedValueOnce({ ok: true, data: { mfa_required: true } });
    render(<LoginForm />);
    await fill("amira@example.com", "a long enough password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/login/mfa"));
  });

  it("shows the API's message when the sign-in is refused and keeps what was typed", async () => {
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: { code: "INVALID_CREDENTIALS", message: "That email and password do not match." },
    });
    render(<LoginForm />);
    await fill("amira@example.com", "wrong password here");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That email and password do not match.",
    );
    expect(screen.getByLabelText("Email address")).toHaveValue("amira@example.com");
    expect(push).not.toHaveBeenCalled();
  });

  it("offers UK only, shows the password on request, and links to reset and sign-up", async () => {
    render(<LoginForm />);
    const group = screen.getByRole("group", { name: "Region" });
    expect(group).toHaveTextContent("United Kingdom");
    expect(screen.getByRole("button", { name: /USA/ })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: /Australia/ })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
    expect(screen.getByRole("link", { name: "Create your company account" })).toHaveAttribute(
      "href",
      "/setup",
    );
  });
});
