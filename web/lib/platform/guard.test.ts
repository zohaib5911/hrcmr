import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    throw new Error(`REDIRECT ${to}`);
  },
}));

import { dataOrSessionRedirect, sessionStartPath } from "./guard";

describe("dataOrSessionRedirect", () => {
  it("returns the data on success", () => {
    expect(dataOrSessionRedirect({ data: { a: 1 }, response: { status: 200 } }, "/")).toEqual({
      a: 1,
    });
  });
  it("returns null on another failure", () => {
    expect(dataOrSessionRedirect({ response: { status: 500 } }, "/")).toBeNull();
  });
  it.each([401, 403])("sends a %i to the start page", (status) => {
    expect(() => dataOrSessionRedirect({ response: { status } }, "/companies")).toThrow(
      "REDIRECT /session?next=%2Fcompanies",
    );
  });
  it("builds the start path", () => {
    expect(sessionStartPath("/")).toBe("/session?next=%2F");
  });
});
