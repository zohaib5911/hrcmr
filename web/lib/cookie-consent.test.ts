import { describe, expect, it } from "vitest";

import {
  CONSENT_KEY,
  CONSENT_VERSION,
  makeConsent,
  parseConsent,
  readConsent,
  saveConsent,
} from "./cookie-consent";

const NOW = new Date("2026-11-02T10:00:00Z");

describe("cookie consent", () => {
  it("round-trips a choice", () => {
    const stored = new Map<string, string>();
    const store = {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => void stored.set(key, value),
    };
    expect(readConsent(store)).toBeNull();
    expect(saveConsent(makeConsent(true, NOW), store)).toBe(true);
    expect(stored.has(CONSENT_KEY)).toBe(true);
    expect(readConsent(store)).toEqual({
      version: CONSENT_VERSION,
      marketing: true,
      decidedAt: "2026-11-02T10:00:00.000Z",
    });
  });

  it("treats anything odd in storage as no choice yet", () => {
    for (const raw of [
      null,
      "",
      "not json",
      "null",
      "[]",
      '{"version":1,"marketing":"yes","decidedAt":"2026-11-02T10:00:00Z"}',
      '{"version":1,"marketing":true,"decidedAt":"never"}',
      '{"version":0,"marketing":true,"decidedAt":"2026-11-02T10:00:00Z"}',
    ]) {
      expect(parseConsent(raw)).toBeNull();
    }
  });

  it("copes with storage that throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(readConsent(broken)).toBeNull();
    expect(saveConsent(makeConsent(false, NOW), broken)).toBe(false);
    expect(saveConsent(makeConsent(false, NOW), null)).toBe(false);
  });
});
