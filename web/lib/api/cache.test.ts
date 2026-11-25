import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_ANSWERS,
  cacheContext,
  cacheKey,
  cached,
  clearApiCache,
  prefetch,
  remember,
} from "./cache";

beforeEach(() => clearApiCache());

describe("the GET answer cache (O6.1.6)", () => {
  it("keys by path and query, whatever the query's order", () => {
    expect(cacheKey("/candidates")).toBe("/candidates");
    expect(cacheKey("/candidates", { search: "a", limit: 100 })).toBe(
      cacheKey("/candidates", { limit: 100, search: "a" }),
    );
    expect(cacheKey("/candidates", { search: "a" })).not.toBe(
      cacheKey("/candidates", { search: "b" }),
    );
  });

  it("returns the last answer, and forgets everything on sign-out or a company switch", () => {
    remember("/documents", { items: [1] });
    remember("/documents", { items: [2] });
    expect(cached("/documents")).toEqual({ items: [2] });
    clearApiCache();
    expect(cached("/documents")).toBeUndefined();
  });

  it("holds at most MAX_ANSWERS, dropping the oldest", () => {
    for (let i = 0; i <= MAX_ANSWERS; i += 1) remember(`/k${i}`, i);
    expect(cached("/k0")).toBeUndefined();
    expect(cached(`/k${MAX_ANSWERS}`)).toBe(MAX_ANSWERS);
  });

  it("prefetches once, and keeps only a successful answer", async () => {
    const load = vi.fn().mockResolvedValue({ ok: true, data: { id: "c1" } });
    await prefetch("/candidates/c1", load);
    await prefetch("/candidates/c1", load);
    expect(load).toHaveBeenCalledTimes(1);
    expect(cached("/candidates/c1")).toEqual({ id: "c1" });

    const failing = vi.fn().mockResolvedValue({ ok: false, problem: { code: "X", message: "x" } });
    await prefetch("/candidates/c2", failing);
    expect(cached("/candidates/c2")).toBeUndefined();
  });

  it("never keeps an answer for a request started before a switch or sign-out (ISS-02)", async () => {
    const from = cacheContext();
    let finish: (value: unknown) => void = () => {};
    const late = prefetch(
      "/candidates/old",
      () => new Promise((resolve) => (finish = resolve)) as never,
    );
    clearApiCache(); // the company switch happens while the request is out
    expect(cacheContext()).toBe(from + 1);
    remember("/candidates", { items: ["old company"] }, from);
    finish({ ok: true, data: { id: "old" } });
    await late;
    expect(cached("/candidates")).toBeUndefined();
    expect(cached("/candidates/old")).toBeUndefined();
    remember("/candidates", { items: ["new company"] });
    expect(cached("/candidates")).toEqual({ items: ["new company"] });
  });
});
