// Screenshots every message in the local Mailpit inbox into docs/screenshots/email/ (plan T2.8).
//
//   cd api && uv run python -m app.cli email-samples     # sends one of each template to Mailpit
//   cd web && node scripts/email-screenshots.mjs          # one PNG per message, named by subject
//
// Mailpit's own page is captured, so the picture shows the message as a mail catcher shows it.
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";
const OUT = fileURLToPath(new URL("../../docs/screenshots/email/", import.meta.url));

const slug = (text) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

const listing = await (await fetch(`${MAILPIT}/api/v1/messages?limit=100`)).json();
if (!listing.messages?.length) {
  throw new Error("Mailpit has no messages. Run `python -m app.cli email-samples` first.");
}
await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
for (const message of listing.messages) {
  await page.goto(`${MAILPIT}/view/${message.ID}`);
  // The message body is shown in a frame; wait until it has painted.
  const frame = page.frameLocator("iframe#preview-html");
  await frame.locator("body").waitFor();
  await page.waitForTimeout(400);
  const file = `${OUT}${slug(message.Subject)}.png`;
  await page.screenshot({ path: file, fullPage: true });
  console.log(file);
}
await browser.close();
