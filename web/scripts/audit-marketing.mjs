#!/usr/bin/env node
/** Run against a production server under bus.sh serial; reports are local build artifacts. */
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";
import lighthouse from "lighthouse";

const origin = process.env.LIGHTHOUSE_ORIGIN || "http://127.0.0.1:3100";
const paths = process.argv.slice(2);
if (!paths.length)
  paths.push(
    "/",
    "/features",
    "/pricing",
    "/security",
    "/about",
    "/contact",
    "/accessibility",
    "/careers",
    "/sponsor-licence-compliance",
    "/sponsor-licence-compliance/reporting-duties",
  );
const browser = await chromium.launch({ headless: true, args: ["--remote-debugging-port=9225"] });
const summary = [];
await mkdir("../.lighthouseci", { recursive: true });
try {
  for (const path of paths) {
    const result = await lighthouse(`${origin}${path}`, {
      port: 9225,
      output: "json",
      logLevel: "error",
      onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
    });
    const { lhr } = result;
    if (lhr.runtimeError) throw new Error(`${path}: ${lhr.runtimeError.message}`);
    const scores = Object.fromEntries(
      Object.entries(lhr.categories).map(([key, category]) => [
        key,
        Math.round(category.score * 100),
      ]),
    );
    summary.push({ path, scores });
    console.log(JSON.stringify({ path, scores }));
    await writeFile(`../.lighthouseci/${path.replaceAll("/", "_") || "home"}.json`, result.report);
    for (const audit of Object.values(lhr.audits)) {
      if (audit.score !== null && audit.score < 1 && audit.details?.type !== "opportunity")
        console.log(`  ${audit.id}: ${audit.title} (${audit.displayValue ?? ""})`);
    }
  }
} finally {
  await browser.close();
  await writeFile(
    "../.lighthouseci/marketing-summary.json",
    JSON.stringify({ lighthouse: "mobile defaults", summary }, null, 2) + "\n",
  );
}
if (summary.some(({ scores }) => Object.values(scores).some((score) => score < 95)))
  process.exitCode = 1;
