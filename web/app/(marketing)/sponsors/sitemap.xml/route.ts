import { publicUrl } from "@/lib/seo";
import { registerGet } from "@/lib/register";

export const dynamic = "force-dynamic";

/** The sitemap index: one child file per 45,000 profiles, plus the fixed pages. */
export async function GET() {
  const data = await registerGet<{ pages: number }>("/sitemap", 3600);
  const pages = data?.pages ?? 1;
  const urls = [
    publicUrl("/sponsors/sitemap/static.xml"),
    ...Array.from({ length: pages }, (_, i) => publicUrl(`/sponsors/sitemap/${i}.xml`)),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls
    .map((u) => `<sitemap><loc>${u}</loc></sitemap>`)
    .join("")}</sitemapindex>`;
  return new Response(body, { headers: { "Content-Type": "application/xml" } });
}
