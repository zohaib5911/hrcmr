import { existsSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import ResourcesPage from "@/app/(marketing)/resources/page";
import GuidesPage from "@/app/(marketing)/resources/guides/page";
import ToolsPage from "@/app/(marketing)/resources/tools/page";
import TemplatesPage from "@/app/(marketing)/resources/templates/page";
import { GET } from "@/app/(marketing)/resources/templates/download/[file]/route";
import { guides } from "@/lib/guides/catalogue";
import { resourceCategories, resourceTools } from "@/lib/resources";
import * as manifest from "@/lib/templates/manifest";
import { marketingPages } from "@/lib/seo";

afterEach(() => vi.restoreAllMocks());

describe("public resource hubs", () => {
  it("links all categories, guides and existing tool routes and indexes them", () => {
    const home = renderToStaticMarkup(<ResourcesPage />);
    const guidePage = renderToStaticMarkup(<GuidesPage />);
    const toolsPage = renderToStaticMarkup(<ToolsPage />);
    for (const { href } of resourceCategories) expect(home).toContain(`href="${href}"`);
    for (const guide of guides) {
      expect(guidePage).toContain(`href="/resources/guides/${guide.slug}"`);
      expect(guidePage).toContain(guide.reviewedOn);
    }
    expect(resourceTools).toHaveLength(15);
    for (const tool of resourceTools) {
      const route = `/resources/tools/${tool.slug}`;
      expect(toolsPage).toContain(`href="${route}"`);
      expect(existsSync(path.join(process.cwd(), "app/(marketing)", route, "page.tsx"))).toBe(true);
      expect(marketingPages.some(([href]) => href === route)).toBe(true);
    }
  });

  it("keeps every unreviewed template out of the public listing", () => {
    const html = renderToStaticMarkup(<TemplatesPage />);
    expect(html).toContain("awaiting human review");
    expect(html).not.toContain("/resources/templates/download/");
    for (const entry of manifest.loadTemplates()) expect(html).not.toContain(entry.title);
  });

  it("lists reviewed templates with a version, review date and download", () => {
    const entry = { ...manifest.loadTemplates()[0], reviewed_on: "2026-11-12" };
    vi.spyOn(manifest, "loadTemplates").mockReturnValue([entry]);
    const html = renderToStaticMarkup(<TemplatesPage />);
    expect(html).toContain(`href="/resources/templates/download/${entry.file}"`);
    expect(html).toContain("Version 1.0");
    expect(html).toContain("2026-11-12");
    expect(html).not.toContain("awaiting human review");
  });

  it("blocks direct downloads of unreviewed, unknown and path-like files", async () => {
    for (const file of [manifest.loadTemplates()[0].file, "missing.docx", "../manifest.json"]) {
      const response = await GET(new Request("http://localhost"), {
        params: Promise.resolve({ file }),
      });
      expect(response.status).toBe(404);
    }
  });

  it("serves reviewed files as attachments with the correct media type", async () => {
    const entry = { ...manifest.loadTemplates()[0], reviewed_on: "2026-11-12" };
    vi.spyOn(manifest, "loadTemplates").mockReturnValue([entry]);
    const response = await GET(new Request("http://localhost"), {
      params: Promise.resolve({ file: entry.file }),
    });
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Disposition")).toBe(
      `attachment; filename="${entry.file}"`,
    );
    expect(response.headers.get("Content-Type")).toContain("wordprocessingml.document");
    const bytes = new Uint8Array(await response.arrayBuffer());
    expect(Array.from(bytes.slice(0, 2))).toEqual([0x50, 0x4b]); // DOCX ZIP signature
  });
});
