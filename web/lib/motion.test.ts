import { describe, expect, it } from "vitest";

import {
  DURATION,
  PAGE_FADE,
  PRESS,
  SPRING,
  STAGGER,
  countUpSeconds,
  fade,
  pageFadeMs,
  presets,
  pressScale,
  sheet,
  staggerDelayMs,
} from "./motion";

describe("motion tokens (plan 5.5)", () => {
  it("uses the default spring from the plan", () => {
    expect(SPRING).toEqual({ type: "spring", stiffness: 420, damping: 34, mass: 0.9 });
  });

  it("has micro 120 ms, small 200 ms and sheet 320 ms durations (in seconds)", () => {
    expect(DURATION).toEqual({ micro: 0.12, small: 0.2, sheet: 0.32 });
  });
});

describe("sheets", () => {
  it("scale from 0.96 and fade on desktop", () => {
    const v = sheet({ mobile: false, reduced: false });
    expect(v.hidden).toEqual({ opacity: 0, scale: 0.96 });
    expect(v.visible).toEqual({ opacity: 1, scale: 1 });
  });

  it("rise from the bottom on mobile", () => {
    const v = sheet({ mobile: true, reduced: false });
    expect(v.hidden).toEqual({ y: "100%" });
    expect(v.visible).toEqual({ y: 0 });
  });

  it("only fade, with no movement or scaling, when the user prefers reduced motion", () => {
    for (const mobile of [true, false]) {
      const v = sheet({ mobile, reduced: true });
      expect(Object.keys(v.hidden)).toEqual(["opacity"]);
      expect(Object.keys(v.visible)).toEqual(["opacity"]);
    }
  });
});

describe("presets", () => {
  it("move with the spring normally and cross-fade quickly when reduced", () => {
    expect(presets(false).transition).toEqual(SPRING);
    expect(presets(true).transition).toEqual({ duration: DURATION.small, ease: "easeOut" });
  });

  it("rise-in items slide 8 px normally and never move when reduced", () => {
    expect(presets(false).riseIn.hidden).toEqual({ opacity: 0, y: 8 });
    expect(presets(true).riseIn.hidden).toEqual({ opacity: 0 });
    expect(fade.hidden).toEqual({ opacity: 0 });
  });
});

describe("countUpSeconds", () => {
  it("counts up over 0.8 s, or shows the final number at once when reduced", () => {
    expect(countUpSeconds(false)).toBe(0.8);
    expect(countUpSeconds(true)).toBe(0);
  });
});

describe("press feedback (U6.1.9)", () => {
  it("shrinks to 0.98 for 80 ms", () => {
    expect(PRESS).toEqual({ scale: 0.98, ms: 80 });
    expect(pressScale(false)).toBe(0.98);
  });

  it("keeps its size with reduced motion", () => {
    expect(pressScale(true)).toBe(1);
  });
});

describe("entrance stagger (U6.1.9)", () => {
  it("starts items 20 ms apart and never later than 180 ms, so a list is under way within 200 ms", () => {
    expect(STAGGER).toEqual({ stepMs: 20, maxMs: 180 });
    expect([0, 1, 2, 9, 10, 500].map((i) => staggerDelayMs(i, false))).toEqual([
      0, 20, 40, 180, 180, 180,
    ]);
    expect(staggerDelayMs(-3, false)).toBe(0);
    expect(STAGGER.maxMs).toBeLessThan(200);
  });

  it("delays nothing with reduced motion", () => {
    for (const index of [0, 1, 5, 50]) expect(staggerDelayMs(index, true)).toBe(0);
  });
});

describe("page cross-fade (U6.1.9)", () => {
  it("fades out in 120 ms and in over 160 ms", () => {
    expect(PAGE_FADE).toEqual({ outMs: 120, inMs: 160 });
    expect(pageFadeMs(false)).toEqual(PAGE_FADE);
  });

  it("swaps at once with reduced motion", () => {
    expect(pageFadeMs(true)).toEqual({ outMs: 0, inMs: 0 });
  });
});
