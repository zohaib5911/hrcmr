import type { MetadataRoute } from "next";
import { marketingPages, publicUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  return marketingPages.map(([path]) => ({ url: publicUrl(path) }));
}
