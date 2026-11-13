import { readFile } from "node:fs/promises";
import path from "node:path";

/** Keep installed clocks' existing icon URL working with the new artwork. */
export async function GET(request: Request) {
  const size = new URL(request.url).searchParams.get("size") === "192" ? 192 : 512;
  const icon = await readFile(path.join(process.cwd(), "public/brand", `clock-${size}.png`));
  return new Response(icon, { headers: { "Content-Type": "image/png" } });
}
