import { describe, expect, it } from "vitest";

import { AVATAR_TONES, avatarTone, initials } from "./avatar";

describe("initials", () => {
  it.each([
    ["Ada Lovelace", "AL"],
    ["ada lovelace", "AL"],
    ["Ada", "A"],
    ["  Ada   Byron  Lovelace ", "AL"],
    ["Ada-Marie O'Neill", "AO"],
    ["Łukasz Żak", "ŁŻ"],
    ["", "?"],
    ["   ", "?"],
    ["(Contractor)", "C"],
  ])("takes %j as %s", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });

  it("is never more than two characters", () => {
    expect(initials("A B C D E").length).toBeLessThanOrEqual(2);
  });
});

describe("avatarTone", () => {
  it("gives the same person the same colour every time", () => {
    expect(avatarTone("Ada Lovelace")).toBe(avatarTone("Ada Lovelace"));
  });

  it("is pinned to fixed values, so a deploy can never recolour everyone", () => {
    expect(avatarTone("Ada Lovelace")).toBe("warning");
    expect(avatarTone("Grace Hopper")).toBe("danger");
    expect(avatarTone("Alan Turing")).toBe("accent");
    expect(avatarTone("Katherine Johnson")).toBe("danger");
  });

  it("spreads people across all the tones", () => {
    const names = Array.from({ length: 200 }, (_, i) => `Person ${i}`);
    const used = new Set(names.map(avatarTone));
    expect(used.size).toBe(AVATAR_TONES.length);
  });

  it("ignores letter case and surrounding spaces", () => {
    expect(avatarTone("  ADA lovelace ")).toBe(avatarTone("ada Lovelace"));
  });
});
