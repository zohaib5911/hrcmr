import { afterEach, describe, expect, it, vi } from "vitest";
import sitemap from "@/app/sitemap";
import robots from "@/app/robots";
import {
  breadcrumbData,
  marketingPages,
  pageMetadata,
  serializeJsonLd,
  websiteData,
} from "@/lib/seo";

afterEach(() => vi.unstubAllEnvs());

describe("public search metadata", () => {
  it("uses the configured site for canonicals and social URLs", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://www.example.test");
    const metadata = pageMetadata("/pricing", "Pricing", "Plan prices.");
    expect(metadata.alternates).toEqual({ canonical: "https://www.example.test/pricing" });
    expect(metadata.openGraph).toMatchObject({
      url: "https://www.example.test/pricing",
      title: "Pricing",
      description: "Plan prices.",
      locale: "en_GB",
    });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });
  it("indexes published routes exactly once and excludes private pages and drafts", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://www.example.test");
    const urls = sitemap().map(({ url }) => url);
    expect(new Set(urls).size).toBe(urls.length);
    expect(urls).toContain("https://www.example.test/resources/guides/right-to-work-checks");
    expect(urls).not.toEqual(
      expect.arrayContaining([
        expect.stringMatching(/\/(legal|vs|compare|platform|dashboard|sign-in)(\/|$)/),
      ]),
    );
    expect(urls).toHaveLength(marketingPages.length);
  });
  it("allows only exact published paths in robots and advertises the sitemap", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://www.example.test");
    expect(robots()).toEqual({
      rules: {
        userAgent: "*",
        disallow: "/",
        allow: [
          ...marketingPages.map(([path]) => `${path}$`),
          "/_next/",
          "/brand/",
          "/marketing/",
          "/opengraph-image",
          "/sitemap.xml$",
          "/sponsors/regions/",
          "/sponsors/changes",
          "/sponsors/profile/",
          "/sponsors/methodology$",
          "/sponsors/terms$",
          "/sponsors/sitemap",
        ],
      },
      sitemap: [
        "https://www.example.test/sitemap.xml",
        "https://www.example.test/sponsors/sitemap.xml",
      ],
    });
  });
  it("builds ordered breadcrumbs without linking unpublished folder routes", () => {
    const data = breadcrumbData("/sponsor-licence-compliance/reporting-duties");
    expect(data.itemListElement.map(({ position, name }) => [position, name])).toEqual([
      [1, "Home"],
      [2, "Sponsor licence compliance"],
      [3, "Sponsor reporting duties"],
    ]);
    expect(
      breadcrumbData("/resources/guides/right-to-work-checks").itemListElement.map(
        ({ name }) => name,
      ),
    ).toEqual(["Home", "Right to Work checks"]);
  });
  it("describes the real organisation, website and software without invented reviews", () => {
    const graph = websiteData()["@graph"];
    expect(graph.map((node) => node["@type"])).toEqual([
      "Organization",
      "WebSite",
      "SoftwareApplication",
    ]);
    expect(JSON.stringify(graph)).not.toMatch(/aggregateRating|reviewCount/);
  });
  it("prevents script termination in structured data while retaining the values", () => {
    const input = { name: '</script><script>alert("x")</script>&' };
    const serialized = serializeJsonLd(input);
    expect(serialized).not.toMatch(/[<>&]/);
    expect(JSON.parse(serialized)).toEqual(input);
  });
});
