import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { after, describe, it } from "node:test";
import path from "node:path";
import { scanDirectories } from "../scan-bundle.mjs";
import { SECRET_VALUE_PATTERNS } from "../lib/policy.mjs";
import { FAKE_SECRETS, SCRIPTS_DIR, makeTree } from "./helpers.mjs";

const SCRIPT = path.join(SCRIPTS_DIR, "scan-bundle.mjs");
const cleanups = [];
after(async () => {
  await Promise.all(cleanups.map((fn) => fn()));
});

async function tree(files) {
  const t = await makeTree(files);
  cleanups.push(t.cleanup);
  return t.root;
}

describe("scan-bundle", () => {
  it("has a fake sample for every secret pattern", () => {
    assert.deepEqual(
      SECRET_VALUE_PATTERNS.map((p) => p.id).sort(),
      Object.keys(FAKE_SECRETS).sort(),
    );
  });

  for (const [rule, fake] of Object.entries(FAKE_SECRETS)) {
    it(`detects ${rule} in a minified chunk`, async () => {
      const root = await tree({
        "chunks/app.js": `!function(){var a="x";var k="${fake}";return a+k}();`,
      });
      const findings = scanDirectories({ dirs: [root], env: {}, cwd: root });
      assert.ok(
        findings.some((f) => f.rule === rule && f.file === "chunks/app.js"),
        `expected rule ${rule}, got ${JSON.stringify(findings)}`,
      );
    });
  }

  it("reports line and column", async () => {
    const root = await tree({
      "a.js": `line one\nline two ${FAKE_SECRETS["stripe-webhook-secret"]}\n`,
    });
    const [finding] = scanDirectories({ dirs: [root], env: {}, cwd: root });
    assert.equal(finding.line, 2);
    assert.equal(finding.column, "line two ".length + 1);
  });

  it("does not flag ordinary minified code or a publishable key", async () => {
    const publishable = ["pk", "live", "Zq8Lm2Xv9Ta4Wp7Rn3Kc6Hd1"].join("_");
    const root = await tree({
      "chunks/ok.js": [
        "var more_items=1,are_ready=2,core_y_long_name_for_something_here=3,store_x=4,pre_load=5;",
        `var pub="${publishable}";`,
        'var u="https://api.example.test/api/v1/health";',
      ].join("\n"),
    });
    assert.deepEqual(scanDirectories({ dirs: [root], env: {}, cwd: root }), []);
  });

  it("finds the literal value of a secret environment variable, by name only", async () => {
    const value = "value-from-the-build-env-9f3a"; // not secret-shaped: only the env check can catch it
    const root = await tree({ "chunks/leak.js": `var x="${value}";` });
    const env = { SESSION_SECRET: value };
    const findings = scanDirectories({ dirs: [root], env, cwd: root });
    assert.deepEqual(
      findings.map((f) => f.rule),
      ["env-value:SESSION_SECRET"],
    );
    assert.ok(!JSON.stringify(findings).includes(value));

    const cli = spawnSync(process.execPath, [SCRIPT, root], {
      env: { ...process.env, ...env },
      encoding: "utf8",
    });
    assert.equal(cli.status, 1);
    assert.ok(!(cli.stdout + cli.stderr).includes(value), "CLI output must not contain the value");
    assert.match(cli.stderr, /env-value:SESSION_SECRET/);
  });

  it("ignores very short environment values", async () => {
    const root = await tree({ "a.js": "var flag=true;var n=1234567;" });
    assert.deepEqual(
      scanDirectories({ dirs: [root], env: { SESSION_SECRET: "1234567" }, cwd: root }),
      [],
    );
  });

  it("skips binary assets", async () => {
    const root = await tree({ "logo.png": FAKE_SECRETS["stripe-webhook-secret"] });
    assert.deepEqual(scanDirectories({ dirs: [root], env: {}, cwd: root }), []);
  });

  it("CLI never prints the matched text", async () => {
    const fake = FAKE_SECRETS["anthropic-api-key"];
    const root = await tree({ "bundle.js": `var k="${fake}";` });
    const cli = spawnSync(process.execPath, [SCRIPT, root], {
      encoding: "utf8",
      env: { ...process.env },
    });
    assert.equal(cli.status, 1);
    const output = cli.stdout + cli.stderr;
    assert.ok(!output.includes(fake));
    assert.ok(!output.includes("Zq8Lm2Xv9Ta4"));
    assert.match(output, /anthropic-api-key/);
  });

  it("CLI exits 0 on a clean directory and 2 when a directory is missing", async () => {
    const root = await tree({ "ok.js": "console.log('hello');" });
    const env = { ...process.env };
    for (const name of ["SESSION_SECRET", "ANTHROPIC_API_KEY", "STRIPE_SECRET_KEY"])
      delete env[name];
    assert.equal(spawnSync(process.execPath, [SCRIPT, root], { env }).status, 0);
    assert.equal(
      spawnSync(process.execPath, [SCRIPT, path.join(root, "missing")], { env }).status,
      2,
    );
  });
});
