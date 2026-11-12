import { readFile } from "node:fs/promises";
import path from "node:path";

import { compile, run } from "@mdx-js/mdx";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as runtime from "react/jsx-runtime";
import { describe, expect, it } from "vitest";

import remarkSafeGuides from "../../scripts/remark-safe-guides.mjs";
import { guides, findGuide, guideDisclaimer } from "./catalogue";

const options = { remarkPlugins: [remarkSafeGuides], outputFormat: "function-body" as const };

describe("guide content compiled with the production MDX guard", () => {
  it.each(guides)(
    "compiles and renders $slug with review metadata and official sources",
    async (guide) => {
      const source = await readFile(path.resolve("../content/guides", `${guide.slug}.mdx`), "utf8");
      const compiled = await compile(source, options);
      const compiledGuide = await run(String(compiled), { ...runtime, baseUrl: import.meta.url });
      const html = renderToStaticMarkup(createElement(compiledGuide.default));
      expect(html).toContain("<h2>");
      expect(html).not.toMatch(/<script|<iframe|onerror=/i);
      expect(source.split(/\s+/).length).toBeGreaterThan(130);
      expect(guide.reviewedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(guide.sources.length).toBeGreaterThan(0);
      for (const { url } of guide.sources) {
        expect(["www.gov.uk", "questions-statements.parliament.uk"]).toContain(
          new URL(url).hostname,
        );
      }
    },
  );

  it.each([
    '<script>alert("test")</script>',
    '<img src="x" onError={() => alert("test")} />',
    '<iframe src="https://example.com" />',
    "<CustomComponent />",
    "{process.env.SECRET}",
    'import fs from "node:fs"\n\nHello',
    "export const secret = 1\n\nHello",
    "[unsafe](javascript:alert%281%29)",
    "[unsafe][ref]\n\n[ref]: data:text/html,test",
    "![tracking](https://example.com/pixel)",
    "# Duplicate page title",
    "<!-- raw HTML -->",
  ])("rejects unsafe or unsupported content: %s", async (source) => {
    await expect(compile(source, options)).rejects.toThrow();
  });

  it("keeps code examples inert and permits HTTPS source links", async () => {
    const compiled = await compile(
      "`<script>`\n\n[Source](https://www.gov.uk/)\n\n## Next steps",
      options,
    );
    const compiledGuide = await run(String(compiled), { ...runtime, baseUrl: import.meta.url });
    const html = renderToStaticMarkup(createElement(compiledGuide.default));
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain('href="https://www.gov.uk/"');
  });

  it("only resolves the six explicit slugs", () => {
    expect(guides).toHaveLength(6);
    expect(findGuide("../../secret")).toBeUndefined();
    expect(findGuide("toString")).toBeUndefined();
    expect(guideDisclaimer).toContain("not legal");
  });
});
