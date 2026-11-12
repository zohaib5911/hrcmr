import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { checkRightToWork, type RightToWorkInput } from "./right-to-work-october-2026-checker";

const base: RightToWorkInput = {
  engagement: "employee",
  workInUK: "yes",
  independentBusiness: "no",
  employmentStart: "2026-10-01",
  contractChain: "no",
  substitution: "no",
  arrangementStart: "2026-10-01",
};
const check = (input: Partial<RightToWorkInput>) => checkRightToWork({ ...base, ...input });

// Official scenario examples, not monetary arithmetic:
// https://assets.publishing.service.gov.uk/media/6ad9dfe29ea4857e15ab3294/Employer_s_guide_to_right_to_work_checks.pdf
describe("right-to-work scope (Home Office October guide)", () => {
  // Same official URL above, examples 1–4, pages 12–13.
  it.each(["employee", "worker", "subcontractor", "matching"] as const)(
    "%s: the direct check applies from the commencement date",
    (engagement) => {
      expect(check({ engagement }).direct).toBe("applies");
    },
  );

  // Same official URL, examples 5–6, page 16: independent plumber / PSC designer.
  it.each(["subcontractor", "other"] as const)(
    "independent %s is outside direct scope",
    (engagement) => {
      const result = check({ engagement, independentBusiness: "yes" });
      expect(result.direct).toBe("outside");
      expect(result.extended).toBe("outside");
    },
  );

  // Same official URL, example 7, page 44: contractor fulfilling a third-party contract.
  it("requires written safeguards for a chain supplying workers onwards", () => {
    const result = check({ engagement: "other", contractChain: "yes" });
    expect(result.extended).toBe("applies");
    expect(result.actions.join(" ")).toContain("prior written consent");
    expect(result.records.join(" ")).toContain("audits");
  });

  // Same official URL, example 8, page 44: platform matching an electrical business.
  it("keeps matching-service extended liability even for an independent provider", () => {
    const result = check({ engagement: "matching", independentBusiness: "yes" });
    expect(result.direct).toBe("review");
    expect(result.extended).toBe("applies");
  });

  // Same official URL, example 9, page 45 and substitution requirements, pages 52–54.
  it("adds substitute checks and identity controls for a delivery platform", () => {
    const result = check({ engagement: "subcontractor", substitution: "yes" });
    expect(result.direct).toBe("applies");
    expect(result.extended).toBe("applies");
    expect(result.actions.join(" ")).toContain("substitutes are checked before working");
    expect(result.actions.join(" ")).toContain("ongoing identity checks");
  });

  // Same official URL, commencement rules on page 14. Hand-compared ISO dates;
  // no numeric worked example exists for these scope decisions.
  it.each([
    ["worker", "2026-09-30", "predates"],
    ["worker", "2026-10-01", "applies"],
    ["employee", "2008-02-28", "predates"],
    ["employee", "2008-02-29", "applies"],
  ] as const)("%s commencing %s: %s", (engagement, employmentStart, expected) => {
    expect(check({ engagement, employmentStart }).direct).toBe(expected);
  });

  // Same official URL, page 14: contractual arrangement date is a separate trigger.
  it("does not use the employment date for extended-liability commencement", () => {
    const result = check({ substitution: "yes", arrangementStart: "2026-09-30" });
    expect(result.direct).toBe("applies");
    expect(result.extended).toBe("predates");
    expect(check({ employmentStart: "2026-09-30", substitution: "yes" }).extended).toBe("applies");
  });

  // Same official URL, page 15: overseas work is outside this scheme.
  it("excludes work outside the UK", () => {
    expect(check({ workInUK: "no", substitution: "yes" })).toMatchObject({
      direct: "outside",
      extended: "outside",
      actions: [],
      records: [],
    });
  });

  // Same official URL, pages 14–15: assess the actual arrangement, not its label.
  it.each([
    { workInUK: "unsure" },
    { independentBusiness: "unsure", engagement: "worker" },
    { employmentStart: "" },
    { employmentStart: "2026-02-30" },
    { employmentStart: "2026-13-01" },
    { engagement: "other" },
  ] satisfies Partial<RightToWorkInput>[])(
    "leaves uncertain direct scope for review: %j",
    (input) => {
      expect(check(input).direct).toBe("review");
    },
  );

  // Same official URL, pages 14 and 42–43: uncertain chain / missing dates require review.
  it.each([
    { contractChain: "unsure" },
    { substitution: "unsure" },
    { substitution: "yes", arrangementStart: "" },
    { substitution: "yes", arrangementStart: "not-a-date" },
  ] satisfies Partial<RightToWorkInput>[])(
    "does not clear uncertain extended scope: %j",
    (input) => {
      expect(check(input).extended).toBe("review");
    },
  );

  // Same official URL, page 22, check evidence retention (two years after employment).
  it("includes dated evidence and post-employment retention", () => {
    expect(check({}).records.join(" ")).toContain("2 years after");
  });

  it("keeps calculator code free of transport and persistence", () => {
    const source = readFileSync(
      new URL("./right-to-work-october-2026-checker.ts", import.meta.url),
      "utf8",
    );
    expect(source).not.toMatch(
      /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
    );
  });
});
