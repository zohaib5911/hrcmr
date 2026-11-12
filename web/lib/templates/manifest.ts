import { readFileSync } from "node:fs";
import path from "node:path";

export interface TemplateEntry {
  slug: string;
  title: string;
  description: string;
  file: string;
  version: string;
  reviewed_on: string | null;
}

const DIR = path.join(process.cwd(), "content", "templates");

/** Parse and check a manifest; throws on a malformed entry. */
export function parseManifest(raw: string): TemplateEntry[] {
  const data: unknown = JSON.parse(raw);
  if (!Array.isArray(data)) throw new Error("manifest must be a list");
  return data.map((e: Record<string, unknown>) => {
    for (const k of ["slug", "title", "description", "file", "version"]) {
      if (typeof e[k] !== "string" || !e[k]) throw new Error(`manifest entry missing ${k}`);
    }
    if (!/^[a-z0-9-]+\.(docx|pdf)$/.test(e.file as string)) {
      throw new Error(`bad template file name: ${String(e.file)}`);
    }
    if (e.reviewed_on !== null && typeof e.reviewed_on !== "string") {
      throw new Error("reviewed_on must be a date string or null");
    }
    return e as unknown as TemplateEntry;
  });
}

export function loadTemplates(): TemplateEntry[] {
  return parseManifest(readFileSync(path.join(DIR, "manifest.json"), "utf8"));
}

/** Only reviewed templates may be published to the public. */
export function isPublishable(t: TemplateEntry): boolean {
  return t.reviewed_on !== null;
}
