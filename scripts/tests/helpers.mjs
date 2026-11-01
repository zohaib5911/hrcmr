import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const SCRIPTS_DIR = path.join(REPO_ROOT, "scripts");

const BODY = "Zq8Lm2Xv9Ta4Wp7Rn3Kc6Hd1"; // 25 alphanumeric characters

/**
 * Fake secrets, assembled from fragments at run time. No complete secret-shaped string is
 * ever written in this file, so gitleaks and the bundle scanner never need an exception.
 * Keyed by the rule id that must detect them.
 */
export const FAKE_SECRETS = Object.freeze({
  "stripe-secret-key-prefix": ["sk", "live", BODY].join("_"),
  "stripe-restricted-key": ["rk", `${BODY}ab`].join("_"),
  "stripe-webhook-secret": ["whsec", BODY].join("_"),
  "anthropic-api-key": ["sk-ant", "api03", BODY].join("-"),
  "resend-api-key": ["re", BODY].join("_"),
  "age-secret-key": `AGE-SECRET-KEY-${"1"}QPZRY9X8GF2TVDW0S3JN54KHCE`,
  "private-key-block": `-----BEGIN ${"PRIVATE KEY"}-----`,
  "sentry-auth-token": ["sntrys", BODY].join("_"),
  "database-url-with-password": `${"postgresql"}://app_user:${"hunter2hunter2"}@localhost/db`,
  "redis-url-with-password": `${"redis"}://:${"hunter2hunter2"}@localhost:6379`,
});

/** Create a throwaway directory tree: `files` maps relative path to text content. */
export async function makeTree(files) {
  // os.tmpdir() honours $TMPDIR, so callers can point it at a scratch location.
  const root = await mkdtemp(path.join(os.tmpdir(), "guardrail-test-"));
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    await mkdir(path.dirname(full), { recursive: true });
    await writeFile(full, content);
  }
  return { root, cleanup: () => rm(root, { recursive: true, force: true }) };
}
