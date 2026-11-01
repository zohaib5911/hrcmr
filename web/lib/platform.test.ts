import { describe, expect, it } from "vitest";

import { isApplePlatform, keyLabel } from "./platform";

describe("platform", () => {
  it("recognises Apple devices", () => {
    for (const platform of ["MacIntel", "MacPPC", "iPhone", "iPad", "iPod"])
      expect(isApplePlatform(platform), platform).toBe(true);
    for (const platform of ["Win32", "Linux x86_64", "Linux armv8l", ""])
      expect(isApplePlatform(platform), platform).toBe(false);
  });

  it("writes the modifier as Cmd or Ctrl and leaves other keys alone", () => {
    expect(keyLabel("Mod", true)).toBe("⌘");
    expect(keyLabel("Mod", false)).toBe("Ctrl");
    expect(keyLabel("K", true)).toBe("K");
    expect(keyLabel("Esc", false)).toBe("Esc");
  });
});
