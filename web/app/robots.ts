import type { MetadataRoute } from "next";
import { marketingPages, publicUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  return {
    // Allow only published marketing pages; app, auth, drafts and future routes are excluded.
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
    sitemap: [publicUrl("/sitemap.xml"), publicUrl("/sponsors/sitemap.xml")],
  };
}
