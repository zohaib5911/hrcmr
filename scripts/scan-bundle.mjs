#!/usr/bin/env node
/**
 * Fails if the built browser bundle contains anything that looks like a secret
 * (plan.md 4.1.5): known secret prefixes (sk_live, sk_test, rk_, re_, sk-ant-, whsec_ and a
 * few more) and, when they are set in the build environment, the literal VALUES of the
 * secret variables listed in lib/policy.mjs.
 *
 * Output gives the file, line, column and RULE ID only. It NEVER prints matched text or
 * environment values.
 *
 * Usage: node scripts/scan-bundle.mjs [dir ...]
 *        default: web/.next/static and web/public (everything served to browsers)
 * Exit:  0 = clean, 1 = findings, 2 = a directory is missing (a missing build must not pass).
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import {
  MIN_SECRET_VALUE_LENGTH,
  SECRET_ENV_NAMES,
  SECRET_VALUE_PATTERNS,
  compilePattern,
} from "./lib/policy.mjs";

const BINARY_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".avif",
  ".ico",
  ".bmp",
  ".woff",
  ".woff2",
  ".ttf",
  ".otf",
  ".eot",
  ".mp4",
  ".webm",
  ".mov",
  ".mp3",
  ".ogg",
  ".pdf",
  ".zip",
  ".gz",
  ".br",
  ".wasm",
]);
const MAX_FINDINGS_PER_RULE_PER_FILE = 5;

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.isFile() && !BINARY_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
      yield full;
    }
  }
}

function lineAndColumn(text, index) {
  let line = 1;
  let lastBreak = -1;
  for (let i = text.indexOf("\n"); i !== -1 && i < index; i = text.indexOf("\n", i + 1)) {
    line += 1;
    lastBreak = i;
  }
  return { line, column: index - lastBreak };
}

/**
 * @param {{ dirs: string[], env?: Record<string, string | undefined>, cwd?: string }} options
 * @returns {{ file: string, line: number, column: number, rule: string }[]}
 */
export function scanDirectories({ dirs, env = process.env, cwd = process.cwd() }) {
  const findings = [];
  const secretValues = SECRET_ENV_NAMES.flatMap((name) => {
    const value = env[name];
    return value && value.length >= MIN_SECRET_VALUE_LENGTH
      ? [{ name, needle: Buffer.from(value, "utf8").toString("latin1") }]
      : [];
  });

  for (const dir of dirs) {
    for (const file of walk(dir)) {
      if (statSync(file).size === 0) continue;
      // latin1 maps bytes 1:1 to characters, so offsets are byte offsets and no decoding fails.
      const text = readFileSync(file).toString("latin1");
      const rel = path.relative(cwd, file).split(path.sep).join("/");

      for (const pattern of SECRET_VALUE_PATTERNS) {
        const regex = compilePattern(pattern, "g");
        let count = 0;
        for (const match of text.matchAll(regex)) {
          findings.push({ file: rel, ...lineAndColumn(text, match.index), rule: pattern.id });
          if (++count >= MAX_FINDINGS_PER_RULE_PER_FILE) break;
        }
      }

      for (const { name, needle } of secretValues) {
        const index = text.indexOf(needle);
        if (index !== -1) {
          findings.push({ file: rel, ...lineAndColumn(text, index), rule: `env-value:${name}` });
        }
      }
    }
  }
  return findings;
}

function main() {
  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const args = process.argv.slice(2);
  // Defaults: everything the web app serves to browsers. The build output must exist; `public/` is
  // optional (the app may have no public files yet).
  const publicDir = path.join(repoRoot, "web/public");
  const dirs = (
    args.length > 0
      ? args
      : [path.join(repoRoot, "web/.next/static"), ...(existsSync(publicDir) ? [publicDir] : [])]
  ).map((d) => path.resolve(d));

  const missing = dirs.filter((d) => !existsSync(d) || !statSync(d).isDirectory());
  if (missing.length > 0) {
    for (const d of missing) {
      console.error(`scan-bundle: directory not found: ${path.relative(process.cwd(), d) || d}`);
    }
    console.error(
      "scan-bundle: build the web app first (a missing build must not pass this check).",
    );
    return 2;
  }

  const findings = scanDirectories({ dirs });
  if (findings.length === 0) {
    console.log(
      `scan-bundle: OK (${dirs.length} director${dirs.length === 1 ? "y" : "ies"} scanned).`,
    );
    return 0;
  }

  console.error("scan-bundle: FAILED. Secret-shaped content found in browser-served files:");
  for (const f of findings) console.error(`  ${f.file}:${f.line}:${f.column}  ${f.rule}`);
  console.error("");
  console.error("Matched text is not printed. Remove the value, rotate the key if it was real,");
  console.error("and keep every third-party call in the api service (plan.md 4.1.4).");
  return 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main());
}
