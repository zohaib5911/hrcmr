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
      ],
    },
    sitemap: publicUrl("/sitemap.xml"),
  };
}
