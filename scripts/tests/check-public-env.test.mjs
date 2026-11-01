import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { after, describe, it } from "node:test";
import path from "node:path";
import { checkPublicEnv } from "../check-public-env.mjs";
import { ALLOWED_PUBLIC_ENV } from "../lib/policy.mjs";
import { FAKE_SECRETS, REPO_ROOT, SCRIPTS_DIR, makeTree } from "./helpers.mjs";

const SCRIPT = path.join(SCRIPTS_DIR, "check-public-env.mjs");
const cleanups = [];
after(async () => {
  await Promise.all(cleanups.map((fn) => fn()));
});

async function tree(files) {
  const t = await makeTree(files);
  cleanups.push(t.cleanup);
  return t.root;
}

describe("check-public-env", () => {
  it("passes on the real repository", () => {
    assert.deepEqual(checkPublicEnv({ root: REPO_ROOT, env: {} }), []);
  });

  it("accepts every allowlisted name in env files and source", async () => {
    const lines = ALLOWED_PUBLIC_ENV.map((n) => `${n}=https://example.test`);
    const root = await tree({
      ".env.example": ALLOWED_PUBLIC_ENV.map((n) => `${n}=`).join("\n"),
      ".env": lines.join("\n"),
      "web/app/page.tsx": `export const a = process.env.${ALLOWED_PUBLIC_ENV[0]};`,
    });
    assert.deepEqual(checkPublicEnv({ root, env: {} }), []);
  });

  it("flags a name outside the allowlist in an env file, with its line", async () => {
    const root = await tree({
      ".env": "NEXT_PUBLIC_SITE_URL=https://x.test\nNEXT_PUBLIC_STRIPE_SECRET_KEY=\n",
    });
    const found = checkPublicEnv({ root, env: {} });
    assert.equal(found.length, 1);
    assert.equal(found[0].name, "NEXT_PUBLIC_STRIPE_SECRET_KEY");
    assert.equal(found[0].where, ".env:2");
    assert.equal(found[0].kind, "not-allowed");
  });

  it("flags a name referenced in web source, a workflow and a Dockerfile", async () => {
    const root = await tree({
      "web/lib/x.ts": "const k = process.env.NEXT_PUBLIC_DEBUG_TOKEN;",
      ".github/workflows/ci.yml": "env:\n  NEXT_PUBLIC_EXTRA_FLAG: '1'\n",
      "web/Dockerfile": "ARG NEXT_PUBLIC_ANOTHER_ONE\n",
    });
    const names = checkPublicEnv({ root, env: {} })
      .map((v) => v.name)
      .sort();
    assert.deepEqual(names, [
      "NEXT_PUBLIC_ANOTHER_ONE",
      "NEXT_PUBLIC_DEBUG_TOKEN",
      "NEXT_PUBLIC_EXTRA_FLAG",
    ]);
  });

  it("flags a disallowed name in the process environment", async () => {
    const root = await tree({ "README.txt": "nothing here" });
    const found = checkPublicEnv({
      root,
      env: { NEXT_PUBLIC_BAD: "1", NEXT_PUBLIC_SITE_URL: "https://x.test" },
    });
    assert.deepEqual(
      found.map((v) => v.name),
      ["NEXT_PUBLIC_BAD"],
    );
  });

  it("ignores prefix mentions, longer identifiers, scripts/ and node_modules", async () => {
    const root = await tree({
      "web/lib/guard.ts":
        'if (name.startsWith("NEXT_PUBLIC_")) {}\nconst MY_NEXT_PUBLIC_THING = 1;',
      "scripts/sample.mjs": "NEXT_PUBLIC_ONLY_IN_SCRIPTS",
      "web/node_modules/pkg/index.js": "NEXT_PUBLIC_VENDOR_FLAG",
    });
    assert.deepEqual(checkPublicEnv({ root, env: {} }), []);
  });

  it("flags a secret-shaped value in an allowlisted variable, without echoing it", async () => {
    const secret = FAKE_SECRETS["stripe-secret-key-prefix"];
    const root = await tree({ ".env": `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=${secret}\n` });
    const found = checkPublicEnv({ root, env: {} });
    assert.equal(found.length, 1);
    assert.equal(found[0].kind, "secret-like-value");
    assert.equal(found[0].rule, "stripe-secret-key-prefix");
    assert.ok(!JSON.stringify(found).includes(secret), "result must not contain the value");

    const cli = spawnSync(process.execPath, [SCRIPT, "--root", root], { encoding: "utf8" });
    assert.equal(cli.status, 1);
    assert.ok(!(cli.stdout + cli.stderr).includes(secret), "CLI output must not contain the value");
  });

  it("allows a Stripe PUBLISHABLE key value", async () => {
    const publishable = ["pk", "live", "Zq8Lm2Xv9Ta4Wp7Rn3Kc6Hd1"].join("_");
    const root = await tree({ ".env": `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=${publishable}\n` });
    assert.deepEqual(checkPublicEnv({ root, env: {} }), []);
  });

  it("CLI exits 0 when clean and 1 when violations exist", async () => {
    const clean = await tree({ ".env.example": "NEXT_PUBLIC_SITE_URL=\n" });
    const dirty = await tree({ ".env.example": "NEXT_PUBLIC_NOT_ALLOWED=\n" });
    const env = { ...process.env };
    for (const key of Object.keys(env)) if (key.startsWith("NEXT_PUBLIC_")) delete env[key];
    assert.equal(spawnSync(process.execPath, [SCRIPT, "--root", clean], { env }).status, 0);
    assert.equal(spawnSync(process.execPath, [SCRIPT, "--root", dirty], { env }).status, 1);
  });
});
