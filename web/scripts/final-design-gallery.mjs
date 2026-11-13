/** Build the offline T22.4 gallery and reject missing/incomplete capture evidence. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../docs/screenshots/", import.meta.url));
const out = `${root}final/`;
const screens = JSON.parse(readFileSync(`${root}phase-25/routes.json`, "utf8"));
const themes = ["light", "dark"];
const widths = [390, 768, 1280, 1920];
const escape = (text) =>
  String(text).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const shot = (filename, label) => {
  assert(existsSync(out + filename), `Missing ${filename}`);
  return `<figure><figcaption>${escape(label)}</figcaption><a href="${filename}"><img loading="lazy" src="${filename}" alt="${escape(label)}"></a></figure>`;
};
const observations = [];
let overlays = 0;
for (const theme of themes) {
  for (const width of widths) {
    const rows = JSON.parse(readFileSync(`${out}observations-${theme}-${width}.json`, "utf8"));
    assert.equal(rows.length, screens.length);
    assert.equal(new Set(rows.map((row) => row.key)).size, screens.length);
    for (const screen of screens) {
      const row = rows.find((row) => row.key === screen.key);
      assert(row, `Missing observation ${screen.key}`);
      assert.equal(row.filename, `${screen.key}-${theme}-${width}.png`);
      assert.equal(
        row.status,
        ["/compare/[category]", "/vs/[competitor]"].includes(screen.route) ? 404 : 200,
        row.route,
      );
      observations.push({ theme, width, ...row });
    }
    const layers = JSON.parse(readFileSync(`${out}overlays-${theme}-${width}.json`, "utf8"));
    assert.equal(layers.length, width === 390 ? 5 : 4);
    overlays += layers.length;
  }
}
let html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>stuffhub final design QA</title><style>body{font:16px system-ui;margin:24px;background:#ddd;color:#111}section{border-top:1px solid #888;padding:20px 0}.shots{display:flex;gap:16px;align-items:flex-start;overflow:auto}figure{margin:0;flex:0 0 320px}img{width:320px;height:auto}figcaption{margin:8px 0}a{color:#004c9b}</style><h1>stuffhub final design QA</h1><p>${screens.length} screen cases, light/dark at 390, 768, 1280 and 1920 px. Click an image for full resolution. Admin evidence is SSR only under local HTTP CSP. See <a href="../../design-qa-final.md">the review and limits</a>.</p>`;
for (const screen of screens) {
  html += `<section><h2>${escape(screen.route)}</h2><p>${escape(screen.source)}</p><div class="shots">`;
  for (const theme of themes)
    for (const width of widths)
      html += shot(
        `${screen.key}-${theme}-${width}.png`,
        `${screen.route} · ${theme} · ${width} px`,
      );
  html += "</div></section>";
}
html += '<section><h2>Overlays and scrolled navigation</h2><div class="shots">';
for (const theme of themes)
  for (const width of widths) {
    const layers = JSON.parse(readFileSync(`${out}overlays-${theme}-${width}.json`, "utf8"));
    for (const { name } of layers)
      html += shot(`overlay-${name}-${theme}-${width}.png`, `${name} · ${theme} · ${width} px`);
  }
html += "</div></section></html>\n";
writeFileSync(`${out}index.html`, html);
const summary = {
  screens: screens.length,
  routeScreenshots: observations.length,
  overlayScreenshots: overlays,
  axeScans: observations.filter((row) => row.axe !== null).length,
  violations: observations
    .filter((row) => row.axe?.length)
    .map(({ route, theme, width, axe }) => ({ route, theme, width, axe })),
  overflow: observations
    .filter((row) => row.overflow > 0)
    .map(({ route, theme, width, overflow }) => ({ route, theme, width, overflow })),
  expectedNotFound: observations.filter((row) => row.status === 404).length,
};
writeFileSync(`${out}summary.json`, JSON.stringify(summary, null, 2) + "\n");
console.log(JSON.stringify(summary, null, 2));
