import { publicUrl } from "@/lib/seo";
import { registerGet } from "@/lib/register";

export const dynamic = "force-dynamic";

const REGIONS = [
  "north-east",
  "north-west",
  "yorkshire-and-the-humber",
  "east-midlands",
  "west-midlands",
  "east-of-england",
  "london",
  "south-east",
  "south-west",
  "wales",
  "scotland",
  "northern-ireland",
];

function xml(entries: { loc: string; lastmod?: string }[]) {
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${entries
    .map(
      (e) => `<url><loc>${e.loc}</loc>${e.lastmod ? `<lastmod>${e.lastmod}</lastmod>` : ""}</url>`,
    )
    .join("")}</urlset>`;
  return new Response(body, { headers: { "Content-Type": "application/xml" } });
}

/** `static.xml` lists the fixed pages; `<n>.xml` lists up to 45,000 sponsor profiles. */
export async function GET(_request: Request, { params }: { params: Promise<{ page: string }> }) {
  const { page } = await params;
  const name = page.replace(/\.xml$/, "");
  if (name === "static") {
    return xml(
      [
        "/sponsors/changes",
        "/sponsors/methodology",
        "/sponsors/terms",
        ...REGIONS.map((r) => `/sponsors/regions/${r}`),
      ].map((p) => ({ loc: publicUrl(p) })),
    );
  }
  if (!/^\d{1,4}$/.test(name)) return new Response("Not found", { status: 404 });
  const data = await registerGet<{
    items: { stable_id: string; slug: string; last_seen_on: string }[];
  }>(`/sitemap/${name}`, 3600);
  if (!data) return new Response("Not found", { status: 404 });
  return xml(
    data.items.map((i) => ({
      loc: publicUrl(`/sponsors/profile/${i.stable_id}/${i.slug}`),
      lastmod: i.last_seen_on,
    })),
  );
}
