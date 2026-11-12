// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET as sitemapChild } from "@/app/(marketing)/sponsors/sitemap/[page]/route";
import { GET as sitemapIndex } from "@/app/(marketing)/sponsors/sitemap.xml/route";
import BulletinPage from "@/app/(marketing)/sponsors/changes/[date]/page";
import { OGL_ATTRIBUTION } from "@/lib/register";

function stub(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("register sitemaps", () => {
  it("lists one child per 45k profiles plus the fixed pages", async () => {
    stub({ pages: 3 });
    const xml = await (await sitemapIndex()).text();
    expect(xml.match(/<sitemap>/g)).toHaveLength(4);
    expect(xml).toContain("/sponsors/sitemap/2.xml");
  });
  it("lists profile URLs and refuses a bad page", async () => {
    stub({ items: [{ stable_id: "a".repeat(32), slug: "acme", last_seen_on: "2026-11-11" }] });
    const ok = await sitemapChild(new Request("http://x"), {
      params: Promise.resolve({ page: "0.xml" }),
    });
    expect(await ok.text()).toContain(`/sponsors/profile/${"a".repeat(32)}/acme`);
    const bad = await sitemapChild(new Request("http://x"), {
      params: Promise.resolve({ page: "../x" }),
    });
    expect(bad.status).toBe(404);
  });
});

describe("bulletin page", () => {
  it("shows the counts, the lists and the attribution", async () => {
    stub({
      date: "2026-11-11",
      added: 1,
      removed: 0,
      returned: 0,
      net: 1,
      median_added_last_28: 3,
      regions: [{ town: "London", count: 1 }],
      added_list: [
        {
          stable_id: "b".repeat(32),
          slug: "new-ltd",
          name: "New Ltd",
          town: "Bristol",
          region: null,
        },
      ],
      removed_list: [],
      returned_list: [],
      possibly_same: [],
      truncated: false,
    });
    render(await BulletinPage({ params: Promise.resolve({ date: "2026-11-11" }) }));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("11 Nov 2026");
    expect(screen.getByRole("link", { name: "New Ltd" }).getAttribute("href")).toBe(
      `/sponsors/profile/${"b".repeat(32)}/new-ltd`,
    );
    expect(screen.getByText(OGL_ATTRIBUTION)).toBeTruthy();
  });
});
