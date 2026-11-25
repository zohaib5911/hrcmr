import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { TargetError, chooseTarget, zapContext } from "../zap-target.mjs";

const STAGING_URL = "https://app.staging.example.test";

describe("zap-target (ISS-04)", () => {
  it("skips when no staging URL is configured", () => {
    assert.equal(chooseTarget({}), null);
  });

  it("accepts the configured staging URL and a manual target on an approved origin", () => {
    assert.deepEqual(chooseTarget({ STAGING_URL }), {
      url: STAGING_URL,
      origin: STAGING_URL,
    });
    const manual = chooseTarget({ STAGING_URL, INPUT_TARGET: `${STAGING_URL}/pricing` });
    assert.equal(manual.origin, STAGING_URL);
    const extra = chooseTarget({
      STAGING_URL,
      STAGING_ORIGINS: "https://api.staging.example.test",
      INPUT_TARGET: "https://api.staging.example.test/health",
    });
    assert.equal(extra.origin, "https://api.staging.example.test");
  });

  for (const [name, target] of [
    ["an unrelated staging host", "https://staging.attacker.test"],
    ["a look-alike host", "https://app.staging.example.test.attacker.test"],
    ["credentials", "https://user:pw@app.staging.example.test"],
    ["an unexpected port", "https://app.staging.example.test:8443"],
    ["plain http", "http://app.staging.example.test"],
    ["an IP address", "https://10.0.0.1"],
    ["not a URL", "staging"],
  ]) {
    it(`rejects ${name}`, () => {
      assert.throws(() => chooseTarget({ STAGING_URL, INPUT_TARGET: target }), TargetError);
    });
  }

  it("rejects a configured URL that is not itself an acceptable staging origin", () => {
    assert.throws(() => chooseTarget({ STAGING_URL: "https://www.example.test" }), TargetError);
    assert.throws(
      () => chooseTarget({ STAGING_URL: "https://app.staging.example.test:444" }),
      TargetError,
    );
  });

  it("writes a context that includes only the approved origin", () => {
    const xml = zapContext(STAGING_URL);
    const pattern = new RegExp(xml.match(/<incregexes>(.*)<\/incregexes>/)[1]);
    assert.ok(pattern.test(`${STAGING_URL}/pricing`));
    assert.ok(pattern.test(STAGING_URL));
    assert.ok(!pattern.test("https://app.staging.example.test.attacker.test/"));
    assert.ok(!pattern.test("https://other.test/?u=https://app.staging.example.test"));
  });
});
