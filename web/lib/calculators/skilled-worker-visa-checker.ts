import english from "@/rates/english.json";
import salaryList from "@/rates/salary-list.json";
import occupations from "@/rates/skilled-occupations.json";
import skilledWorker from "@/rates/skilled-worker.json";

type Block = { table?: string[][] };

export type Occupation = {
  code: string;
  title: string;
  examples: string;
  /** Table 1 (current rules) or Table 1a (only for continuing pre-22 July 2025 permission holders). */
  table: "1" | "1a";
  goingRate: number;
  rate90: number | null;
  rate80: number | null;
  rate70: number | null;
  phdPoints: boolean;
  onSalaryList: boolean;
};

export type Situation = "new" | "continuing";
export type VisaInput = {
  code: string;
  salary: number;
  weeklyHours: number;
  situation: Situation;
  phdRelevant: boolean;
  phdStem: boolean;
  newEntrant: boolean;
  dependantPartner: boolean;
  dependantChildren: number;
  previousSkilledWorkerBeforeJan2026: boolean;
};
export type OptionResult = {
  option: "A" | "B" | "C" | "D" | "E";
  label: string;
  applicable: boolean;
  /** Why the option is not available for these answers. */
  reason?: string;
  requiredSalary: number | null;
  met: boolean;
};
export type VisaResult = {
  occupation: Occupation | null;
  eligibleOccupation: boolean | null;
  status: "assessed" | "needs-review" | "invalid-code";
  messages: string[];
  options: OptionResult[];
  eligible: boolean;
  lowestRequired: number | null;
  salaryConsidered: number;
  dependantFunds: number;
  english: string;
};

const sources = [
  {
    title: "Immigration Rules: Appendix Skilled Worker",
    json: skilledWorker,
  },
  {
    title: "Immigration Rules: Appendix Skilled Occupations",
    json: occupations,
  },
  {
    title: "Immigration Rules: Appendix Immigration Salary List",
    json: salaryList,
  },
  { title: "GOV.UK: Skilled Worker visa, knowledge of English", json: english },
];
export const visaCheckerSources = sources.map(({ title, json }) => ({
  title,
  url: json.source_url,
  checkedOn: json.checked_on,
  validFrom: json.valid_from,
  validTo: json.valid_to,
}));

const rules = skilledWorker.values;
/** General salary thresholds per year, from the options table in Appendix Skilled Worker (SW 4.4). */
export const THRESHOLDS: Readonly<Record<OptionResult["option"], number>> = {
  A: rules.salary_option_thresholds.A,
  B: rules.salary_option_thresholds.B,
  C: rules.salary_option_thresholds.C,
  D: rules.salary_option_thresholds.D,
  E: rules.salary_option_thresholds.E,
};
/** SW 33.3 maintenance funds for dependants. */
export const PARTNER_FUNDS = rules.dependant_funds.partner;
export const FIRST_CHILD_FUNDS = rules.dependant_funds.first_child;
export const OTHER_CHILD_FUNDS = rules.dependant_funds.other_child;
/** SW 14.4(a): Tables 1 to 2a going rates are for this many weekly hours. */
export const FULL_TIME_HOURS = rules.going_rate_weekly_hours;
/** SW 14.3: salary above this many weekly hours does not count. */
export const MAX_HOURS = rules.max_weekly_hours_counted;

function money(cell: string | undefined): number | null {
  const match = /£([\d,]+)/.exec(cell ?? "");
  return match?.[1] ? Number(match[1].replace(/,/g, "")) : null;
}

function tables(blocks: readonly Block[]) {
  return blocks.flatMap((b) => (b.table ? [b.table] : []));
}

function parse(table: string[][], kind: "1" | "1a", listed: ReadonlySet<string>): Occupation[] {
  const rows: Occupation[] = [];
  for (const row of table.slice(1)) {
    const head = /^(\d{4})\s+(.+)$/.exec(row[0] ?? "");
    const goingRate = money(row[2]);
    if (!head?.[1] || !head[2] || goingRate === null) continue;
    rows.push({
      code: head[1],
      title: head[2].trim(),
      examples: (row[1] ?? "").replace(/•/g, ",").replace(/\s+/g, " ").trim(),
      table: kind,
      goingRate,
      rate90: money(row[3]),
      rate80: money(row[4]),
      rate70: money(row[5]),
      phdPoints: (row[6] ?? "").trim().toLowerCase() === "yes",
      onSalaryList: listed.has(head[1]),
    });
  }
  return rows;
}

function salaryListCodes(): Set<string> {
  const codes = new Set<string>();
  for (const table of tables(salaryList.content as Block[])) {
    for (const row of table) {
      const code = /^(\d{4})\s/.exec(row[0] ?? "")?.[1];
      if (code && row.slice(1, 5).some((cell) => cell.trim() === "Yes")) codes.add(code);
    }
  }
  return codes;
}

// Only salary options A–E are modelled locally. Occupation selection uses the public SOC API.
const listed = salaryListCodes();
const appendix = tables(occupations.content as Block[]);
export const OCCUPATIONS: readonly Occupation[] = [
  ...parse(appendix[0] ?? [], "1", listed),
  ...parse(appendix[1] ?? [], "1a", listed),
];

export function findOccupation(code: string): Occupation | undefined {
  return OCCUPATIONS.find((o) => o.code === code);
}

/** Search by 4-digit code, title or example job title. No AI, no network. */
export function searchOccupations(query: string, limit = 8): Occupation[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  return OCCUPATIONS.filter((o) => {
    const haystack = `${o.code} ${o.title} ${o.examples}`.toLowerCase();
    return terms.every((t) => haystack.includes(t));
  }).slice(0, limit);
}

function roundUp(n: number) {
  return Math.ceil(n - 1e-9);
}

/** Eligibility under points options A–E (rules for new applications from 22 July 2025). */
export function checkSkilledWorkerVisa(
  input: VisaInput,
  selectedOccupation?: { code: string; title: string },
): VisaResult {
  const occupation = findOccupation(input.code) ?? null;
  const hours = Math.min(Math.max(input.weeklyHours, 0), 168);
  // SW 14.3: only the salary for the first MAX_HOURS a week counts towards the thresholds.
  const salaryConsidered = hours > MAX_HOURS ? (input.salary * MAX_HOURS) / hours : input.salary;
  // SW 14.4: going rates are pro-rated by all stated hours ÷ FULL_TIME_HOURS.
  const factor = hours / FULL_TIME_HOURS;
  const messages: string[] = [];
  const children = Math.max(0, Math.floor(input.dependantChildren));
  const dependantFunds =
    (input.dependantPartner ? PARTNER_FUNDS : 0) +
    (children > 0 ? FIRST_CHILD_FUNDS + (children - 1) * OTHER_CHILD_FUNDS : 0);
  const englishLevel = input.previousSkilledWorkerBeforeJan2026
    ? "B1 if you are extending a Skilled Worker visa you held before 8 January 2026; otherwise B2."
    : "B2 (speaking, listening, reading and writing) unless an exemption applies.";

  const empty = (reason: string): OptionResult[] =>
    (["A", "B", "C", "D", "E"] as const).map((option) => ({
      option,
      label: optionLabel(option),
      applicable: false,
      reason,
      requiredSalary: null,
      met: false,
    }));

  if (!occupation) {
    const recognised = selectedOccupation?.code === input.code;
    messages.push(
      recognised
        ? "This is a recognised SOC occupation, but its eligibility and salary options are not modelled by this calculator. Health and education roles may use option K and national pay scales (Tables 3 and 4). Review the official Skilled Occupations appendix for the role, pay band and nation before deciding eligibility."
        : "Choose a valid SOC 2020 code using the occupation search before checking eligibility.",
    );
    return {
      occupation,
      status: recognised ? "needs-review" : "invalid-code",
      eligibleOccupation: recognised ? null : false,
      messages,
      options: [],
      eligible: false,
      lowestRequired: null,
      salaryConsidered,
      dependantFunds,
      english: englishLevel,
    };
  }
  if (occupation.table === "1a" && input.situation !== "continuing") {
    messages.push(
      "This occupation is in Table 1a: only people granted Skilled Worker permission before 22 July 2025, with continuous permission since, can be sponsored for it.",
    );
    return {
      occupation,
      status: "assessed",
      eligibleOccupation: false,
      messages,
      options: empty("Occupation not available for new applicants"),
      eligible: false,
      lowestRequired: null,
      salaryConsidered,
      dependantFunds,
      english: englishLevel,
    };
  }
  if (!(hours > 0)) {
    messages.push("Enter the weekly hours stated by the sponsor.");
    return {
      occupation,
      status: "assessed",
      eligibleOccupation: true,
      messages,
      options: empty("Hours needed"),
      eligible: false,
      lowestRequired: null,
      salaryConsidered,
      dependantFunds,
      english: englishLevel,
    };
  }

  const scaled = (rate: number | null) => (rate === null ? null : roundUp(rate * factor));
  const make = (
    option: OptionResult["option"],
    applicable: boolean,
    rate: number | null,
    reason?: string,
  ): OptionResult => {
    const base = scaled(rate);
    const available = applicable && base !== null;
    const requiredSalary = available ? Math.max(THRESHOLDS[option], base) : null;
    return {
      option,
      label: optionLabel(option),
      applicable: available,
      ...(available ? {} : { reason: reason ?? "Not available for this occupation" }),
      requiredSalary,
      met: requiredSalary !== null && salaryConsidered >= requiredSalary,
    };
  };
  const options = [
    make("A", true, occupation.goingRate),
    make(
      "B",
      input.phdRelevant && occupation.phdPoints,
      occupation.rate90,
      phdReason(input, occupation),
    ),
    make(
      "C",
      input.phdStem && occupation.phdPoints,
      occupation.rate80,
      phdReason(input, occupation),
    ),
    make(
      "D",
      occupation.onSalaryList,
      occupation.goingRate,
      "Not on the Immigration Salary List (check the nation and any job-specific criteria)",
    ),
    make(
      "E",
      input.newEntrant,
      occupation.rate70,
      "Needs a new entrant at the start of their career",
    ),
  ];
  if (occupation.onSalaryList) {
    messages.push(
      "This code appears on the Immigration Salary List. Some entries apply only to named jobs or nations and end on 31 December 2026, so confirm the criteria before relying on option D.",
    );
  }
  if (hours > MAX_HOURS) {
    messages.push(
      `Only salary for the first ${MAX_HOURS} hours a week counts towards the thresholds, so the salary has been scaled down for this check.`,
    );
  }
  const required = options.flatMap((o) => (o.requiredSalary === null ? [] : [o.requiredSalary]));
  const eligible = options.some((o) => o.met);
  messages.push(
    eligible
      ? "The salary meets at least one points option. Other requirements (an approved sponsor, a Certificate of Sponsorship, English, and suitability) still apply."
      : "The salary is below the minimum for every option that applies to these answers.",
  );
  return {
    occupation,
    status: "assessed",
    eligibleOccupation: true,
    messages,
    options,
    eligible,
    lowestRequired: required.length ? Math.min(...required) : null,
    salaryConsidered,
    dependantFunds,
    english: englishLevel,
  };
}

function phdReason(input: VisaInput, o: Occupation) {
  if (!o.phdPoints) return "This occupation is not eligible for PhD points";
  return input.phdRelevant || input.phdStem ? undefined : "Needs a relevant PhD";
}

function optionLabel(option: OptionResult["option"]) {
  return {
    A: "A: going rate",
    B: "B: relevant PhD (90% of going rate)",
    C: "C: STEM PhD (80% of going rate)",
    D: "D: Immigration Salary List job",
    E: "E: new entrant (70% of going rate)",
  }[option];
}
