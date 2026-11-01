#!/usr/bin/env node
/**
 * Fails if any NEXT_PUBLIC_* variable outside the allowlist exists (plan.md 4.1.4).
 *
 * Anything named NEXT_PUBLIC_* is inlined into the browser bundle, so only the names in
 * ALLOWED_PUBLIC_ENV may exist, and even those must never hold a secret-shaped value.
 *
 * Looks at:
 *   1. the process environment;
 *   2. config-bearing files in the repo (.env*, Dockerfiles, compose files, GitHub
 *      workflows, railway config, next.config.*, and source under web/).
 *
 * Output names variables and file locations only. It NEVER prints a value.
 *
 * Usage: node scripts/check-public-env.mjs [--root <dir>]
 * Exit:  0 = clean, 1 = violations found.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ALLOWED_PUBLIC_ENV, firstSecretPatternId } from "./lib/policy.mjs";

const NAME_PATTERN = /\bNEXT_PUBLIC_[A-Z0-9_]+/g;
const ASSIGNMENT_PATTERN = /^\s*(?:export\s+)?(NEXT_PUBLIC_[A-Z0-9_]+)\s*=\s*(.*)$/;
const SKIP_DIRS = new Set([
  ".git",
  "node_modules",
  ".next",
  ".venv",
  "venv",
  "__pycache__",
  ".pnpm-store",
  ".mypy_cache",
  ".ruff_cache",
  ".pytest_cache",
  "dist",
  "build",
  "coverage",
  "playwright-report",
  "test-results",
  "out",
]);
const MAX_FILE_BYTES = 2 * 1024 * 1024;
const ALLOWED = new Set(ALLOWED_PUBLIC_ENV);

/** Is this repo-relative path one that can define or reference a build-time variable? */
export function isScannable(rel) {
  const base = path.posix.basename(rel);
  if (rel.startsWith("scripts/")) return false; // guard scripts and their tests hold sample names
  if (/^\.env(\..+)?$/.test(base)) return true; // includes .env.example
  if (/^Dockerfile/i.test(base) || /\.dockerfile$/i.test(base)) return true;
  if (/^docker-compose.*\.ya?ml$/.test(base) || /^compose.*\.ya?ml$/.test(base)) return true;
  if (/^railway\.(json|toml)$/.test(base)) return true;
  if (rel.startsWith(".github/") && /\.ya?ml$/.test(base)) return true;
  if (/^next\.config\./.test(base)) return true;
  if (base === "brand.config.ts") return true;
  if (rel.startsWith("web/") && /\.(ts|tsx|js|jsx|mjs|cjs|json|sh|toml|ya?ml)$/.test(base)) {
    return true;
  }
  return false;
}

function* walk(root, dir = root) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) yield* walk(root, path.join(dir, entry.name));
    } else if (entry.isFile()) {
      yield path.join(dir, entry.name);
    }
  }
}

/**
 * @param {{ root: string, env?: Record<string, string | undefined> }} options
 * @returns {{ where: string, name: string, kind: "not-allowed" | "secret-like-value", rule?: string }[]}
 */
export function checkPublicEnv({ root, env = process.env }) {
  const violations = [];

  for (const [name, value] of Object.entries(env)) {
    if (!name.startsWith("NEXT_PUBLIC_")) continue;
    if (!ALLOWED.has(name)) {
      violations.push({ where: "process environment", name, kind: "not-allowed" });
    } else if (value) {
      const rule = firstSecretPatternId(value);
      if (rule)
        violations.push({ where: "process environment", name, kind: "secret-like-value", rule });
    }
  }

  for (const file of walk(root)) {
    const rel = path.relative(root, file).split(path.sep).join("/");
    if (!isScannable(rel)) continue;
    if (statSync(file).size > MAX_FILE_BYTES) continue;
    const text = readFileSync(file, "utf8");
    if (text.includes("\u0000")) continue; // binary

    const lines = text.split("\n");
    lines.forEach((line, index) => {
      const where = `${rel}:${index + 1}`;
      for (const match of line.matchAll(NAME_PATTERN)) {
        if (!ALLOWED.has(match[0])) {
          violations.push({ where, name: match[0], kind: "not-allowed" });
        }
      }
      const assignment = ASSIGNMENT_PATTERN.exec(line);
      if (assignment && ALLOWED.has(assignment[1])) {
        const value = assignment[2].trim().replace(/^["']|["']$/g, "");
        const rule = value ? firstSecretPatternId(value) : null;
        if (rule) violations.push({ where, name: assignment[1], kind: "secret-like-value", rule });
      }
    });
  }

  return violations;
}

function main() {
  const args = process.argv.slice(2);
  const rootFlag = args.indexOf("--root");
  const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const root = rootFlag >= 0 ? path.resolve(args[rootFlag + 1] ?? "") : defaultRoot;

  const violations = checkPublicEnv({ root });
  if (violations.length === 0) {
    console.log(`check-public-env: OK (${ALLOWED_PUBLIC_ENV.length} NEXT_PUBLIC_* names allowed).`);
    return 0;
  }

  console.error("check-public-env: FAILED. Only these NEXT_PUBLIC_* variables are allowed:");
  console.error(`  ${ALLOWED_PUBLIC_ENV.join("\n  ")}`);
  console.error("");
  for (const v of violations) {
    const why =
      v.kind === "not-allowed"
        ? "is not in the allowlist"
        : `holds a secret-shaped value (rule: ${v.rule})`;
    console.error(`  ${v.where}  ${v.name}  ${why}`);
  }
  console.error("");
  console.error(
    "Anything named NEXT_PUBLIC_* is sent to every browser. Move secrets to the api service.",
  );
  return 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main());
}
