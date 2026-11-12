import salary from "@/rates/ilr-worker-salary.json";
import occupations from "@/rates/skilled-occupations.json";
import skilledWorker from "@/rates/skilled-worker.json";

export type Situation =
  "standard" | "health_care" | "salary_list" | "transitional" | "sportsperson";

export type Occupation = {
  code: string;
  title: string;
  examples: string;
  /** Standard going rate (Table 1/1a, 37.5-hour week). */
  standard: number | null;
  /** Lower going rate (Table 2/2aa/2a, 37.5-hour week). */
  lower: number | null;
  /** National pay-scale occupations (Table 3/3a): no single figure. */
  payScale: boolean;
  payScaleText: string;
};

export type SalaryInput = {
  occupation: Occupation;
  situation: Situation;
  hours: number; // weekly hours stated by the sponsor
};

/**
 * ok: `required` is the figure to meet. pay_scale: the going rate comes from national pay
 * scales. review: the rates file has no going rate for the selected branch, so no figure is given.
 */
export type SalaryStatus = "ok" | "pay_scale" | "review";

export type SalaryResult = {
  status: SalaryStatus;
  required: number | null;
  floor: number | null;
  goingRate: number | null; // pro-rated
  fullTimeGoingRate: number | null;
  hours: number;
  basis: string;
  notes: string[];
};

export const ilrSalarySources = [salary, occupations].map((file) => ({
  title: file.title,
  url: file.source_url,
  checkedOn: file.checked_on,
  validFrom: file.valid_from,
  validTo: file.valid_to,
}));

/** SW 14.4(a): standard and lower going rates are for this many weekly hours. */
export const FULL_TIME_HOURS = skilledWorker.values.going_rate_weekly_hours;

const gbp = (value: number) => `£${value.toLocaleString("en-GB")}`;

type Block = Record<string, unknown>;

const figures = salary.values;
/** Fixed settlement minimums from the GOV.UK salary requirements page (values checked against its text). */
export const thresholds = {
  standard: figures.standard,
  payScale: figures.health_education_pay_scale,
  salaryList: figures.salary_list,
  transitional: figures.transitional,
  transitionalSalaryList: figures.transitional_salary_list,
  healthCare: figures.health_care_different_requirements,
  healthCareSalaryList: figures.health_care_salary_list,
  sportsperson: figures.sportsperson,
};
const MAX_HOURS = figures.max_weekly_hours_counted;

function poundsFrom(cell: string | undefined): number | null {
  const m = /£([\d,]+)/.exec(cell ?? "");
  return m?.[1] ? Number(m[1].replace(/,/g, "")) : null;
}

type Table = string[][];
function tableAfter(headingStart: string): Table {
  const content = occupations.content as Block[];
  const i = content.findIndex((b) => typeof b.h2 === "string" && b.h2.startsWith(headingStart));
  for (const b of content.slice(i + 1)) {
    if (Array.isArray(b.table)) return b.table as Table;
    if (typeof b.h2 === "string") break;
  }
  throw new Error(`Table not found in rates file: ${headingStart}`);
}

function splitCode(cell: string) {
  const m = /^(\d{4})\s+(.*)$/.exec(cell.trim());
  return { code: m?.[1] ?? "", title: m?.[2] ?? cell };
}

function buildOccupations(): Occupation[] {
  const map = new Map<string, Occupation>();
  const get = (cell: string, examples: string): Occupation => {
    const { code, title } = splitCode(cell);
    const existing = map.get(code);
    if (existing) return existing;
    const created: Occupation = {
      code,
      title,
      examples,
      standard: null,
      lower: null,
      payScale: false,
      payScaleText: "",
    };
    map.set(code, created);
    return created;
  };
  // Table 1 and 1a: columns [code, examples, going rate, ...]
  for (const head of ["Table 1:", "Table 1a:"]) {
    for (const row of tableAfter(head).slice(1)) {
      if (!row[0]) continue;
      get(row[0], row[1] ?? "").standard = poundsFrom(row[2]);
    }
  }
  // Table 2, 2aa and 2a: columns [code, soc2010, examples, going rate (F), ...]
  for (const head of ["Table 2:", "Table 2aa:", "Table 2a:"]) {
    for (const row of tableAfter(head).slice(1)) {
      if (!row[0]) continue;
      get(row[0], row[2] ?? "").lower = poundsFrom(row[3]);
    }
  }
  // Table 3 and 3a: national pay scales
  for (const head of ["Table 3:", "Table 3a:"]) {
    for (const row of tableAfter(head).slice(1)) {
      if (!row[0]) continue;
      const occ = get(row[0], row[2] ?? "");
      occ.payScale = true;
      occ.payScaleText = row[3] ?? "";
    }
  }
  return [...map.values()].filter((o) => o.code).sort((a, b) => a.code.localeCompare(b.code));
}

export const allOccupations: Occupation[] = buildOccupations();

/** Search by SOC code prefix or by words in the title / example job titles. */
export function searchOccupations(query: string, limit = 25): Occupation[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const words = q.split(/\s+/);
  return allOccupations
    .filter((o) => {
      if (/^\d+$/.test(q)) return o.code.startsWith(q);
      const hay = `${o.title} ${o.examples}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    })
    .slice(0, limit);
}

export function prorate(fullTimeAnnual: number, hours: number) {
  return Math.round((fullTimeAnnual * hours) / FULL_TIME_HOURS);
}

export function calculateIlrSalary(input: SalaryInput): SalaryResult {
  const hours = Math.min(168, Math.max(1, input.hours));
  const occ = input.occupation;
  const notes: string[] = [
    `Going rates are for a ${FULL_TIME_HOURS}-hour week and are pro-rated by the hours your sponsor states; the fixed minimum is not pro-rated.`,
    "Only the going rate column applies to settlement; the 70%, 80% and 90% columns do not.",
  ];
  const result = (basis: string, floor: number, fullTime: number | null): SalaryResult => {
    const going = fullTime === null ? null : prorate(fullTime, hours);
    return {
      status: "ok",
      required: Math.max(floor, going ?? 0),
      floor,
      goingRate: going,
      fullTimeGoingRate: fullTime,
      hours,
      basis,
      notes,
    };
  };
  /** The branch needs a going rate the rates file does not hold: never substitute 0. */
  const review = (basis: string, guidance: string[]): SalaryResult => ({
    status: "review",
    required: null,
    floor: null,
    goingRate: null,
    fullTimeGoingRate: null,
    hours,
    basis,
    notes: guidance,
  });
  const goingRateFor = (fullTime: number | null, basis: string, floor: number, kind: string) =>
    fullTime === null
      ? review(basis, [
          `SOC ${occ.code} has no ${kind} going rate in the going rates tables, so we cannot give a salary figure for this situation.`,
          kind === "standard" && occ.lower !== null
            ? "It is listed only with a lower going rate. You may qualify under another rule (for example a first certificate of sponsorship before 4 April 2024, or a Health and Care Worker role): check the going rates table or ask your sponsor."
            : "Check the going rates table or ask your sponsor which going rate applies to your job.",
        ])
      : result(basis, floor, fullTime);

  if (input.situation === "sportsperson") {
    return {
      ...result("International Sportsperson minimum", thresholds.sportsperson, null),
      notes: [
        `Only earnings from your sponsored main job count, for up to ${MAX_HOURS} hours a week.`,
      ],
    };
  }
  if (occ.payScale) {
    return {
      ...result("National pay scale", thresholds.payScale, null),
      status: "pay_scale",
      required: null,
      notes: [
        `Your job’s going rate comes from national pay scales: you must be paid the higher of ${gbp(thresholds.payScale)} and your pay-scale rate.`,
        occ.payScaleText,
      ],
    };
  }
  if (input.situation === "health_care") {
    // GOV.UK lists separate Health and Care Worker rules for some occupation codes; the
    // list of those codes is not in our rates files, so this branch is routed to review.
    return review("Health and Care Worker visa", [
      `If your occupation code has different salary requirements for Health and Care Workers, you must be paid the higher of ${gbp(thresholds.healthCare)} (${gbp(thresholds.healthCareSalaryList)} if your job is on the Immigration Salary List) and the lower going rate for your job.`,
      "Otherwise the usual salary requirement applies. Ask your sponsor which rule covers your occupation code, then check it against the going rates table.",
    ]);
  }
  if (input.situation === "transitional") {
    return goingRateFor(
      occ.lower,
      "Certificate of sponsorship before 4 April 2024 (lower going rate)",
      thresholds.transitional,
      "lower",
    );
  }
  if (input.situation === "salary_list") {
    return goingRateFor(
      occ.standard,
      "Immigration Salary List job",
      thresholds.salaryList,
      "standard",
    );
  }
  return goingRateFor(occ.standard, "Usual salary requirement", thresholds.standard, "standard");
}
