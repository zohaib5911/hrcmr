import { existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { isPublishable, loadTemplates, parseManifest, type TemplateEntry } from "./manifest";

describe("template manifest", () => {
  it("lists the six templates and every file exists", () => {
    const list = loadTemplates();
    expect(list).toHaveLength(6);
    for (const t of list) {
      expect(existsSync(path.join(process.cwd(), "content", "templates", t.file))).toBe(true);
    }
  });

  it("treats unreviewed templates as not publishable", () => {
    expect(loadTemplates().every((t) => !isPublishable(t))).toBe(true);
    const t = loadTemplates()[0] as TemplateEntry;
    expect(isPublishable({ ...t, reviewed_on: "2026-11-12" })).toBe(true);
  });

  it("rejects path-like file names and missing fields", () => {
    const bad = (file: string) =>
      JSON.stringify([
        { slug: "a", title: "A", description: "d", file, version: "1", reviewed_on: null },
      ]);
    expect(() => parseManifest(bad("../x.docx"))).toThrow();
    expect(() => parseManifest("[{}]")).toThrow();
    expect(() => parseManifest(bad("a.docx"))).not.toThrow();
  });
});
