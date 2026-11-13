import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  calculateSponsorCosts,
  compareCertificateLengths,
  healthSurchargeFor,
  isSmallSponsor,
  skillsChargeFor,
  type SponsorCostInput,
} from "./sponsor-licence-cost-calculator";

const base: SponsorCostInput = {
  licenceType: "new",
  charity: false,
  turnover: 20_000_000,
  assets: 10_000_000,
  employees: 100,
  route: "skilled_worker",
  insideUK: false,
  months: 24,
  soc: "2431",
  workers: 1,
  adultDependants: 0,
  childDependants: 0,
  speed: "standard",
  licencePriority: false,
  basis: "standard",
};
const calc = (input: Partial<SponsorCostInput>) => calculateSponsorCosts({ ...base, ...input });

describe("sponsor licence cost calculator", () => {
  // https://www.gov.uk/uk-visa-sponsorship-employers/apply-for-your-licence (licence fees table)
  it.each([
    [{ charity: true }, 611],
    [{}, 1682],
    [{ licenceType: "add_worker" as const, charity: true }, 0],
    [{ licenceType: "add_worker" as const }, 1071],
  ])("licence fee %j is £%i", (input, fee) => {
    expect(calc(input).licenceFee).toBe(fee);
  });

  // Same page: small if at least 2 of turnover ≤£15m, assets ≤£7.5m, ≤50 employees.
  it("classifies small sponsors on two of three criteria", () => {
    expect(isSmallSponsor({ charity: false, turnover: 15e6, assets: 7.5e6, employees: 500 })).toBe(
      true,
    );
    expect(isSmallSponsor({ charity: false, turnover: 16e6, assets: 7.5e6, employees: 500 })).toBe(
      false,
    );
    expect(isSmallSponsor({ charity: false, turnover: 16e6, assets: 8e6, employees: 50 })).toBe(
      false,
    );
    expect(isSmallSponsor({ charity: false, turnover: 14e6, assets: 8e6, employees: 50 })).toBe(
      true,
    );
  });

  // https://www.gov.uk/uk-visa-sponsorship-employers/immigration-skills-charge
  // Worked maximum: 5 × £480 = £2,400 (small), 5 × £1,320 = £6,600 (medium/large); 6–12 months pays 12.
  it("immigration skills charge: maximum and part-year rounding", () => {
    expect(skillsChargeFor(60, true)).toBe(2400);
    expect(skillsChargeFor(60, false)).toBe(6600);
    expect(skillsChargeFor(9, false)).toBe(1320);
    expect(skillsChargeFor(18, true)).toBe(480 + 240); // hand-worked: first 12 + one extra 6
    expect(skillsChargeFor(13, true)).toBe(480 + 240);
  });

  it("skills charge: exempt SOC, short stays outside the UK, dependants", () => {
    expect(calc({ soc: "2111" }).skillsCharge).toBe(0);
    expect(calc({ months: 5 }).skillsCharge).toBe(0);
    expect(calc({ months: 5, insideUK: true }).skillsCharge).toBe(1320);
    expect(calc({ adultDependants: 2, childDependants: 1 }).employerTotal).toBe(
      1682 + 525 + 1320 + 660 * 2,
    ); // dependants add no charge
  });

  // GOV.UK ISC rates above: hand-worked 24 months = £1,320 + 2 × £660,
  // or £480 + 2 × £240. Health and Care visa fees/IHS do not exempt nurses from ISC.
  it.each([
    [false, false, 2640],
    [false, true, 2640],
    [true, false, 960],
    [true, true, 960],
  ])("charges nursing ISC (small=%s, insideUK=%s)", (charity, insideUK, charge) => {
    const result = calc({ route: "health_care", soc: "2231", charity, insideUK });
    expect(result.skillsCharge).toBe(charge);
    expect(result.skillsChargeExempt).toBe(false);
  });

  it.each(["2111", "2112", "2113", "2114", "2115", "2119", "2161", "2162", "2311"])(
    "retains the occupation exemption for SOC %s",
    (soc) => {
      for (const insideUK of [false, true]) {
        const result = calc({ soc: ` ${soc} `, insideUK });
        expect(result.skillsCharge).toBe(0);
        expect(result.skillsChargeExempt).toBe(true);
      }
    },
  );

  it.each([
    [false, 5, 0],
    [false, 6, 1320],
    [true, 5, 1320],
    [true, 6, 1320],
  ])("applies nursing stay rules (insideUK=%s, months=%i)", (insideUK, months, charge) => {
    expect(calc({ route: "health_care", soc: "2231", insideUK, months }).skillsCharge).toBe(charge);
  });

  it("charges ISC per nurse, excludes dependants and retains Health and Care IHS exemption", () => {
    const result = calc({
      route: "health_care",
      soc: "2231",
      workers: 2,
      adultDependants: 1,
      childDependants: 1,
    });
    expect(result.employerTotal).toBe(1682 + 2 * (525 + 2640));
    expect(result.healthSurchargeWorker).toBe(0);
    expect(result.healthSurchargeAdult).toBe(0);
    expect(result.healthSurchargeChild).toBe(0);
    expect(result.workerSideTotal).toBe(4 * 324);
    expect(result.grandTotal).toBe(9308);
  });

  // https://www.gov.uk/uk-visa-sponsorship-employers/certificates-of-sponsorship: £525 per Worker certificate.
  it("charges a £525 certificate per worker", () => {
    expect(calc({ workers: 3, charity: true, months: 12 }).employerTotal).toBe(
      611 + 3 * (525 + 480),
    );
  });

  // https://www.gov.uk/skilled-worker-visa/how-much-it-costs — example: 2 years from outside the UK
  // costs £819 plus £1,035 a year IHS = £2,889.
  it("matches the official 2-year outside-UK example", () => {
    // This example describes a two-year VISA, not a two-year CoS plus SW 18.1 days.
    expect(calc({}).visaFeePerPerson + healthSurchargeFor(24, false, false)).toBe(2889);
    expect(calc({}).healthSurchargeWorker).toBe(2587.5);
  });

  // Same page: fee tiers, and salary-list fees £628 / £1,235 regardless of location.
  it.each([
    [{ months: 36 }, 819],
    [{ months: 37 }, 1618],
    [{ months: 36, insideUK: true }, 943],
    [{ months: 60, insideUK: true }, 1865],
    [{ months: 36, basis: "salary_list" as const }, 628],
    [{ months: 48, insideUK: true, basis: "salary_list" as const }, 1235],
    // https://www.gov.uk/health-care-worker-visa/how-much-it-costs
    [{ route: "health_care" as const, months: 36 }, 324],
    [{ route: "health_care" as const, months: 48 }, 628],
  ])("visa fee %j is £%i", (input, fee) => {
    expect(calc(input).visaFeePerPerson).toBe(fee);
  });

  it("health care visas carry no healthcare surcharge", () => {
    expect(
      calc({ route: "health_care", workers: 2, adultDependants: 1 }).healthSurchargeWorker,
    ).toBe(0);
  });

  // https://www.gov.uk/healthcare-immigration-application/how-much-pay — worked: £3,105 for 3 years;
  // half years £517.50 adult / £388 under 18 inside the UK; none ≤6 months from outside.
  it("healthcare surcharge part-year rules", () => {
    expect(healthSurchargeFor(36, false, false)).toBe(3105);
    expect(healthSurchargeFor(6, true, false)).toBe(517.5);
    expect(healthSurchargeFor(6, true, true)).toBe(388);
    expect(healthSurchargeFor(6, false, false)).toBe(0);
    expect(healthSurchargeFor(9, false, false)).toBe(1035);
    expect(healthSurchargeFor(18, false, false)).toBe(1552.5);
    expect(healthSurchargeFor(19, false, false)).toBe(2070);
    expect(healthSurchargeFor(24, false, true)).toBe(1552);
  });

  // https://www.gov.uk/faster-decision-visa-settlement/applying-outside-the-uk: +£500 / +£1,000 per person
  // including each family member; licence priority £750 (apply-for-your-licence page).
  it("adds priority fees per applicant and the licence priority fee", () => {
    expect(calc({ speed: "priority", adultDependants: 1 }).speedFeePerPerson).toBe(500);
    expect(calc({ speed: "super_priority" }).speedFeePerPerson).toBe(1000);
    expect(calc({ licencePriority: true }).licencePriorityFee).toBe(750);
    const standard = calc({ adultDependants: 1 });
    const fast = calc({ speed: "priority", adultDependants: 1 });
    expect(fast.workerSideTotal - standard.workerSideTotal).toBe(1000);
  });

  it("splits employer and worker totals", () => {
    const r = calc({ workers: 2, adultDependants: 1, childDependants: 1 });
    expect(r.employerTotal).toBe(1682 + 2 * (525 + 1320 + 660 * 2));
    expect(r.grandTotal).toBe(r.employerTotal + r.workerSideTotal);
    // CoS 24 months + 14 days: 2.5 years IHS, including under-18 at application.
    expect(r.workerSideTotal).toBe(4 * 819 + 3 * 2587.5 + 1940);
  });

  // Hand-worked from SW 18.1 + GOV.UK IHS part-year rules (not official worked examples):
  // 6m14d => 1 year; 12m14d => 1.5 years; 36m14d => 3.5 years.
  // Fee table tiers and ISC continue to use CoS employment, not the visa extension.
  it.each([
    [6, 1035, 776, 1320],
    [12, 1552.5, 1164, 1320],
    [36, 3622.5, 2716, 3960],
  ])("uses visa duration at the %i-month CoS boundary", (months, adult, child, isc) => {
    for (const insideUK of [false, true]) {
      const result = calc({ months, insideUK, childDependants: 1 });
      expect(result.visaPeriod).toBe(`${months} months + 14 days`);
      expect(result.healthSurchargeWorker).toBe(adult);
      expect(result.healthSurchargeChild).toBe(child);
      expect(result.skillsCharge).toBe(isc);
      expect(result.visaFeePerPerson).toBe(insideUK ? 943 : 819);
      expect(result.workerSideTotal).toBe(2 * result.visaFeePerPerson + adult + child);
      const exempt = calc({ months, insideUK, route: "health_care", childDependants: 1 });
      expect(exempt.healthSurchargeWorker).toBe(0);
      expect(exempt.healthSurchargeChild).toBe(0);
      expect(exempt.skillsCharge).toBe(isc);
    }
  });

  it("requires GP confirmation only for SOC 2211 and uses the verified four-month exception", () => {
    expect(() => calc({ soc: "2211" })).toThrow(/Confirm/);
    expect(() => calc({ soc: "2231", gpTraining: true })).toThrow(/SOC 2211/);
    expect(calc({ soc: "2211", gpTraining: false }).visaPeriod).toBe("24 months + 14 days");
    // 9m CoS + 4m GP exception = 13m visa => 1.5 years IHS (ordinary 9m14d => 1 year).
    const gp = calc({ soc: "2211", gpTraining: true, months: 9, childDependants: 1 });
    expect(gp.visaPeriod).toBe("13 months (includes 4 months for GP specialty training)");
    expect(gp.healthSurchargeWorker).toBe(1552.5);
    expect(gp.healthSurchargeChild).toBe(1164);
    expect(gp.skillsCharge).toBe(1320);
    expect(
      calc({ soc: "2211", gpTraining: true, route: "health_care" }).healthSurchargeWorker,
    ).toBe(0);
    const rows = compareCertificateLengths({ ...base, soc: "2211", gpTraining: true });
    expect(rows[0]?.result.visaPeriod).toBe(
      "16 months (includes 4 months for GP specialty training)",
    );
  });

  it("compares certificate lengths", () => {
    const rows = compareCertificateLengths(base);
    expect(rows.map((row) => row.months)).toEqual([12, 18, 24, 36, 48, 60]);
    for (const { months, result } of rows) {
      expect(result).toEqual(calc({ months }));
    }
    expect(rows[5]?.result.healthSurchargeWorker).toBe(5692.5);
    expect(rows[5]?.result.skillsCharge).toBe(6600);
    expect(rows[0]!.result.grandTotal).toBeLessThan(rows[5]!.result.grandTotal);
  });

  it("keeps calculator code free of transport and persistence", () => {
    const source = readFileSync(
      new URL("./sponsor-licence-cost-calculator.ts", import.meta.url),
      "utf8",
    );
    expect(source).not.toMatch(
      /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
    );
  });
});
