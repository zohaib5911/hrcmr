#!/usr/bin/env node
/**
 * Chooses and checks the ZAP baseline target (security.yml, ISS-04). The scan may only start on,
 * and only crawl, an approved staging origin that this project controls.
 *
 * Approved origins come from repository VARIABLES, which only repository admins can change:
 * STAGING_URL (its origin) and STAGING_ORIGINS (optional, comma-separated extra origins). A target
 * typed into a manual run must have exactly one of those origins. Every origin must be https://,
 * on the default port, without user name or password, with a `staging` label in its host name.
 *
 * Writes the target URL and a ZAP context file whose only include rule is that origin, so the
 * spider stays on it (zap-baseline.py -n passes the context name to the spider).
 *
 * Usage: node scripts/zap-target.mjs <context-file>   (reads INPUT_TARGET, STAGING_URL, STAGING_ORIGINS)
 * Prints `skip=true`, or `skip=false` and `url=<target>`, for $GITHUB_OUTPUT. Exit 1 = refused.
 */
import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export class TargetError extends Error {}

/** The origin of `value` if it is an acceptable staging URL; throws TargetError otherwise. */
export function stagingOrigin(value) {
  let url;
  try {
    url = new URL(String(value).trim());
  } catch {
    throw new TargetError("The target is not a valid URL.");
  }
  if (url.protocol !== "https:") throw new TargetError("The target must start with https://");
  if (url.username || url.password) {
    throw new TargetError("The target must not contain a user name or password.");
  }
  if (url.port !== "") throw new TargetError("The target must use the default HTTPS port.");
  const host = url.hostname;
  if (/^\[|^\d+(\.\d+){3}$/.test(host)) {
    throw new TargetError("The target must be a host name, not an IP address.");
  }
  if (!host.split(".").includes("staging")) {
    throw new TargetError(`Refusing '${host}': only hosts with a 'staging' label are allowed.`);
  }
  return url.origin;
}

/** The approved origins from the repository variables. */
export function approvedOrigins({ STAGING_URL = "", STAGING_ORIGINS = "" } = {}) {
  return [STAGING_URL, ...STAGING_ORIGINS.split(",")]
    .map((item) => item.trim())
    .filter(Boolean)
    .map(stagingOrigin);
}

/** `null` when nothing is configured (skip), else the URL to scan and its origin. */
export function chooseTarget(env) {
  const approved = approvedOrigins(env);
  const target = (env.INPUT_TARGET || env.STAGING_URL || "").trim();
  if (!target) return null;
  const origin = stagingOrigin(target);
  if (!approved.includes(origin)) {
    throw new TargetError(
      `Refusing '${origin}': it is not an approved staging origin (STAGING_URL / STAGING_ORIGINS).`,
    );
  }
  return { url: target, origin };
}

const escapeRegex = (text) => text.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
const escapeXml = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** A ZAP context that includes only `origin`. */
export function zapContext(origin) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<configuration>
  <context>
    <name>staging</name>
    <desc>Approved staging origin only</desc>
    <inscope>true</inscope>
    <incregexes>${escapeXml(`^${escapeRegex(origin)}(/.*)?$`)}</incregexes>
  </context>
</configuration>
`;
}

function main() {
  const contextFile = process.argv[2];
  if (!contextFile) {
    console.error("Usage: node scripts/zap-target.mjs <context-file>");
    return 2;
  }
  let chosen;
  try {
    chosen = chooseTarget(process.env);
  } catch (error) {
    if (!(error instanceof TargetError)) throw error;
    console.error(`::error::${error.message}`);
    return 1;
  }
  if (chosen === null) {
    console.log("skip=true");
    return 0;
  }
  writeFileSync(contextFile, zapContext(chosen.origin));
  console.log("skip=false");
  console.log(`url=${chosen.url}`);
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) process.exitCode = main();
