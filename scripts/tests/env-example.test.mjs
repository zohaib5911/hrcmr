import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, it } from "node:test";
import { ALLOWED_PUBLIC_ENV, SECRET_ENV_NAMES } from "../lib/policy.mjs";
import { REPO_ROOT } from "./helpers.mjs";

const exampleLines = readFileSync(path.join(REPO_ROOT, ".env.example"), "utf8").split("\n");
const assignments = exampleLines.filter((l) => l.trim() !== "" && !l.trimStart().startsWith("#"));
const exampleNames = assignments.map((l) => l.split("=")[0]);

/** Variable names listed in deployment-requirements.txt section 4. */
function namesInDeploymentRequirements() {
  const text = readFileSync(path.join(REPO_ROOT, "deployment-requirements.txt"), "utf8");
  const section4 = text.split("4. ENVIRONMENT VARIABLES")[1].split("5. PROVIDER SET-UP STEPS")[0];
  const names = new Set();
  for (const line of section4.split("\n")) {
    const match = /^([A-Z][A-Z0-9_]+)\s{2,}\S/.exec(line);
    if (match) names.add(match[1]);
  }
  return names;
}

describe(".env.example", () => {
  it("contains names only: every line is NAME= with no value", () => {
    for (const line of assignments) {
      assert.match(
        line,
        /^[A-Z][A-Z0-9_]*=$/,
        `line must be NAME= with no value: ${line.split("=")[0]}`,
      );
    }
  });

  it("has no duplicate names", () => {
    assert.equal(new Set(exampleNames).size, exampleNames.length);
  });

  it("matches deployment-requirements.txt section 4 exactly", () => {
    assert.deepEqual(
      [...new Set(exampleNames)].sort(),
      [...namesInDeploymentRequirements()].sort(),
    );
  });

  it("has exactly the allowlisted NEXT_PUBLIC_* names", () => {
    const publicNames = exampleNames.filter((n) => n.startsWith("NEXT_PUBLIC_")).sort();
    assert.deepEqual(publicNames, [...ALLOWED_PUBLIC_ENV].sort());
  });

  it("contains every app secret the bundle scanner watches (CI tokens excluded)", () => {
    const ciOnly = new Set([
      "RAILWAY_TOKEN",
      "RAILWAY_TOKEN_STAGING",
      "RAILWAY_TOKEN_PRODUCTION",
      "SENTRY_AUTH_TOKEN",
    ]);
    for (const name of SECRET_ENV_NAMES.filter((n) => !ciOnly.has(n))) {
      assert.ok(
        exampleNames.includes(name),
        `${name} is watched by scan-bundle but missing from .env.example`,
      );
    }
  });
});
