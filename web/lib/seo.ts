import type { Metadata } from "next";
import { brand } from "@brand";
import { resourceTools } from "@/lib/resources";
import { guides } from "@/lib/guides/catalogue";

/** Deployment URL only: never derive canonical links from an untrusted Host header. */
export function siteUrl(): URL {
  return new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000");
}

export function publicUrl(path: string): string {
  return new URL(path, siteUrl()).href;
}

export function pageMetadata(path: string, title: string, description: string): Metadata {
  const url = publicUrl(path);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      locale: "en_GB",
      siteName: brand.name,
      title,
      description,
      url,
      images: [
        {
          url: publicUrl("/opengraph-image"),
          width: 1200,
          height: 630,
          alt: `${brand.name} — HR and sponsor compliance`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [publicUrl("/opengraph-image")],
    },
  };
}

/** Only published routes belong here. Legal and comparison drafts stay out of search. */
export const marketingPages = [
  ["/", "HR and sponsor compliance"],
  ["/features", "Features"],
  ["/pricing", "Pricing"],
  ["/security", "Security"],
  ["/about", "About"],
  ["/contact", "Contact"],
  ["/accessibility", "Accessibility statement"],
  ["/careers", "Careers"],
  ["/sponsor-licence-compliance", "Sponsor licence compliance"],
  ["/sponsor-licence-compliance/reporting-duties", "Sponsor reporting duties"],
  ["/resources", "Employer resources"],
  ["/resources/guides", "Employer guides"],
  ["/resources/tools", "Free employer tools"],
  ["/resources/templates", "Employer templates"],
  ...resourceTools.map((tool) => [`/resources/tools/${tool.slug}`, tool.title] as const),
  ...guides.map((guide) => [`/resources/guides/${guide.slug}`, guide.title] as const),
] as const;

export function breadcrumbData(path: string) {
  const parts = path.split("/").filter(Boolean);
  const crumbs = [{ "@type": "ListItem", position: 1, name: "Home", item: publicUrl("/") }];
  for (let i = 0; i < parts.length; i++) {
    const itemPath = `/${parts.slice(0, i + 1).join("/")}`;
    // Omit virtual folders that are not published landing pages.
    const page = marketingPages.find(([route]) => route === itemPath);
    if (page)
      crumbs.push({
        "@type": "ListItem",
        position: crumbs.length + 1,
        name: page[1],
        item: publicUrl(itemPath),
      });
  }
  return { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: crumbs };
}

export function websiteData() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": publicUrl("/#organization"),
        name: brand.legal.companyName ?? brand.name,
        url: publicUrl("/"),
      },
      {
        "@type": "WebSite",
        "@id": publicUrl("/#website"),
        name: brand.name,
        url: publicUrl("/"),
        publisher: { "@id": publicUrl("/#organization") },
        inLanguage: "en-GB",
      },
      {
        "@type": "SoftwareApplication",
        name: brand.name,
        url: publicUrl("/features"),
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web browser",
        description: "HR records and sponsor compliance for UK employers.",
        publisher: { "@id": publicUrl("/#organization") },
      },
    ],
  };
}

/** Escape HTML-significant characters before embedding untrusted strings in a script element. */
export function serializeJsonLd(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026");
}
