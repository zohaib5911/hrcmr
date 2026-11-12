import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const directory = path.resolve(import.meta.dirname, "../../rates");
const files = readdirSync(directory).filter((file) => file.endsWith(".json"));
const read = (file: string) => JSON.parse(readFileSync(path.join(directory, file), "utf8"));

// Integrity of legal-rate inputs matters independently of calculator arithmetic.
// These tests run offline against captured primary-source evidence.
describe("verified calculator sources", () => {
  it.each(files)("%s has provenance and a supported validity interval", (file) => {
    const data = read(file);
    const url = new URL(data.source_url);
    expect(url.protocol).toBe("https:");
    expect(["www.gov.uk", "assets.publishing.service.gov.uk", "www.economy-ni.gov.uk"]).toContain(
      url.hostname,
    );
    expect(data.checked_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(data.valid_from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(data.valid_to === null || data.valid_to >= data.valid_from).toBe(true);
    expect(data.validity_basis).toBeTruthy();
    expect(
      data.content?.length || data.content_text?.length || data.values || data.nations,
    ).toBeTruthy();
    // A first/preamble-only capture of an Immigration Rules appendix loses tables.
    if (["skilled-occupations.json", "salary-list.json"].includes(file)) {
      const tables = data.content.filter((block: object) => "table" in block);
      expect(tables.length).toBeGreaterThan(0);
      expect(tables.some((block: { table: string[][] }) => block.table.length > 10)).toBe(true);
    }
  });

  it.each(["payroll-2025-26.json", "payroll-2026-27.json"])(
    "%s normalized NI thresholds and category rates match HMRC table cells",
    (file) => {
      // Official HMRC source URL is stored in each payroll file.
      const data = read(file);
      const tables: string[][][] = data.content
        .filter((block: object) => "table" in block)
        .map((block: { table: string[][] }) => block.table);
      const thresholds = tables.find(
        (rows) => rows[0][0] === "Class 1 National Insurance thresholds",
      )!;
      for (const [label, text] of thresholds.slice(1)) {
        for (const match of text.matchAll(/£([\d,]+) per (week|month|year)/g)) {
          expect(data.values.ni_thresholds[label][match[2]]).toBe(
            Number(match[1].replaceAll(",", "")),
          );
        }
      }
      for (const [field, columns] of [
        ["employee_ni_rates", 4],
        ["employer_ni_rates", 5],
      ] as const) {
        const table = tables.find(
          (rows) =>
            rows[0][0] === "National Insurance category letter" && rows[0].length === columns,
        )!;
        expect(Object.keys(data.values[field])).toHaveLength(table.length - 1);
        for (const row of table.slice(1)) {
          expect(data.values[field][row[0].split(" ")[0]]).toEqual(
            row.slice(1).map((cell) => (cell === "nil" ? 0 : parseFloat(cell) / 100)),
          );
        }
      }
    },
  );

  it("retains historical wage bands and separates announced rates", () => {
    // https://www.gov.uk/national-minimum-wage-rates
    const data = read("minimum-wage.json");
    const periods = [...data.periods].sort((a, b) => a.valid_from.localeCompare(b.valid_from));
    for (let index = 1; index < periods.length; index++) {
      expect(periods[index - 1].valid_to < periods[index].valid_from).toBe(true);
    }
    const current = periods.filter(
      (period) => period.valid_from <= data.checked_on && period.valid_to >= data.checked_on,
    );
    expect(current).toHaveLength(1);
    expect(current[0].age_band_rates["21 and over"]).toBe(12.71);
    expect(
      periods.find((period) => period.valid_from === "2023-04-01").age_band_rates["23 and over"],
    ).toBe(10.42);
    expect(periods.find((period) => period.valid_from === "2027-04-01").status).toBe("announced");
  });

  it("keeps NI redundancy caps separate from GB and captures SSP reform", () => {
    // Sources: GOV.UK redundancy guide, NI DfE March 2026 announcement,
    // and HMRC February 2026 employer bulletin (URLs in the corresponding files).
    expect(read("redundancy-gb.json").values.weekly_pay_cap).toBe(751);
    expect(read("redundancy-ni.json").values.weekly_pay_cap).toBe(783);
    const reform = read("sick-changes.json");
    expect(reform.valid_from).toBe("2026-04-06");
    expect(reform.values.waiting_days).toBe(0);
    expect(reform.values.lower_earnings_limit).toBeNull();
    expect(reform.values.jurisdictions).toContain("Northern Ireland");
    expect(read("sick-pay.json").values.average_weekly_earnings_rate).toBe(0.8);
    expect(read("payroll-2025-26.json").values.student_loans).not.toHaveProperty(
      "student loan plan 5",
    );
    expect(read("payroll-2026-27.json").values.student_loans).toHaveProperty("student loan plan 5");
  });

  it("preserves published bank-holiday coverage for each nation", () => {
    // https://www.gov.uk/bank-holidays.json
    const data = read("bank-holidays.json");
    expect(Object.keys(data.nations).sort()).toEqual([
      "england-and-wales",
      "northern-ireland",
      "scotland",
    ]);
    for (const nation of Object.values(data.nations) as Array<{
      events: Array<{ date: string; title: string }>;
      valid_from: string;
      valid_to: string;
    }>) {
      expect(nation.events.length).toBeGreaterThan(0);
      for (const event of nation.events) {
        expect(event.date >= nation.valid_from && event.date <= nation.valid_to).toBe(true);
        expect(event.title).toBeTruthy();
      }
      expect(new Set(nation.events.map((event) => event.date)).size).toBe(nation.events.length);
    }
  });
});
