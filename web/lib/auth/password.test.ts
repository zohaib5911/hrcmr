import { describe, expect, it } from "vitest";

import { destinationAfterSignIn, needsTurnstile } from "./next-step";
import { MIN_PASSWORD_LENGTH, passwordStrength } from "./password";

describe("passwordStrength", () => {
  it("says nothing until something is typed, then counts down to the minimum", () => {
    expect(passwordStrength("").label).toBe("");
    const short = passwordStrength("abcdefgh");
    expect(short).toMatchObject({ label: "Too short", meetsMinimum: false });
    expect(short.tip).toContain("4 more characters");
    expect(passwordStrength("a".repeat(MIN_PASSWORD_LENGTH - 1)).tip).toContain(
      "1 more character ",
    );
  });

  it("does not praise repetition", () => {
    expect(passwordStrength("aaaaaaaaaaaaaaaa")).toMatchObject({
      label: "Weak",
      meetsMinimum: true,
    });
  });

  it("rises with length and variety", () => {
    expect(passwordStrength("bluebirdwalks").label).toBe("Fair");
    expect(passwordStrength("Bluebird4walks").label).toBe("Good");
    expect(passwordStrength("Bluebird walks 4 miles to town!").label).toBe("Strong");
    expect(passwordStrength("correct horse battery staple").label).toBe("Strong");
  });
});

describe("after signing in", () => {
  it("goes to the second step only when the API asks for one", () => {
    expect(destinationAfterSignIn({ mfa_required: true })).toBe("/login/mfa");
    expect(destinationAfterSignIn({ mfa_required: false })).toBe("/dashboard");
  });

  it("asks for the Turnstile check after 3 failures, or when the API says so", () => {
    expect(needsTurnstile(2, "INVALID_CREDENTIALS")).toBe(false);
    expect(needsTurnstile(3, "INVALID_CREDENTIALS")).toBe(true);
    expect(needsTurnstile(0, "TURNSTILE_FAILED")).toBe(true);
  });
});
