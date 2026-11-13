/** Rasterize the committed, unchanged owner SVGs. Run: node scripts/generate-brand-assets.mjs */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { mkdir } from "node:fs/promises";

const require = createRequire(import.meta.url);
const sharp = require(require.resolve("sharp", { paths: [require.resolve("next/package.json")] }));
const root = fileURLToPath(new URL("../", import.meta.url));
const brand = path.join(root, "public/brand");
await mkdir(brand, { recursive: true });

// Apple gets 12% padding; maskable artwork fits wholly within the central 80% safe circle.
async function square(size, destination, fraction = 1, white = false, small = false) {
  const artwork = await sharp(path.join(brand, small ? "mark-small.svg" : "mark.svg"))
    .resize(Math.round(size * fraction), Math.round(size * fraction), { fit: "contain" })
    .png()
    .toBuffer();
  await sharp({
    create: { width: size, height: size, channels: 4, background: white ? "#FFFFFF" : "#FFFFFF00" },
  })
    .composite([{ input: artwork, gravity: "centre" }])
    .png()
    .toFile(path.join(root, destination));
}
await square(512, "app/icon.png");
await square(32, "app/icon1.png", 1, false, true);
await square(180, "app/apple-icon.png", 0.76, true);
for (const size of [192, 512]) {
  await square(size, `public/brand/clock-${size}.png`);
  // A square with side 56% has corners within the safe circle (radius 40%).
  await square(size, `public/brand/clock-maskable-${size}.png`, 0.56, true);
}
await sharp(path.join(brand, "logo.svg"), { density: 144 })
  .resize(538, 128)
  .flatten({ background: "#FFFFFF" })
  .png()
  .toFile(path.join(brand, "logo-email.png"));
