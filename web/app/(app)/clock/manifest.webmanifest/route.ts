import { brand } from "@brand";
export function GET() {
  return Response.json(
    {
      id: "/clock",
      name: `${brand.name} clock`,
      short_name: "Clock",
      start_url: "/clock",
      scope: "/clock",
      display: "standalone",
      background_color: "#f5f5f7",
      theme_color: brand.colours.accent,
      icons: [192, 512].flatMap((size) =>
        ["any", "maskable"].map((purpose) => ({
          src: `/brand/clock-${purpose === "maskable" ? "maskable-" : ""}${size}.png`,
          sizes: `${size}x${size}`,
          type: "image/png",
          purpose,
        })),
      ),
    },
    { headers: { "Content-Type": "application/manifest+json" } },
  );
}
