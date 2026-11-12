import income from "@/rates/income-tax.json";
import payroll from "@/rates/payroll-2026-27.json";
import taxCodes from "@/rates/tax-codes-2026-27.json";

export type Region = "england" | "scotland" | "wales";
export type PensionMethod = "none" | "net_pay" | "salary_sacrifice" | "relief_at_source";
export type LoanPlan = "none" | "plan 1" | "plan 2" | "plan 4" | "plan 5";

export type TakeHomeInput = {
  region: Region;
  salary: number; // annual gross
  taxCode: string; // "auto" or a code such as 1257L, BR, D0, 0T, K100, NT
  pensionMethod: PensionMethod;
  pensionPercent: number;
  studentLoan: LoanPlan;
  postgradLoan: boolean;
  niCategory: string;
  otherJobs: boolean; // allowance already used elsewhere: tax this job at BR
  benefits: number; // taxable benefits in kind, annual
  otherDeductions: number; // annual, after tax
};

export type Row = { label: string; annual: number };
export type TakeHomeResult = {
  rows: Row[];
  annual: number;
  monthly: number;
  weekly: number;
  notes: string[];
};

const V = payroll.values;

export const takeHomeSources = [payroll, income, taxCodes].map((file) => ({
  title: file.title,
  url: file.source_url,
  checkedOn: file.checked_on,
  validFrom: file.valid_from,
  validTo: file.valid_to,
}));

export const niCategories = Object.keys(V.employee_ni_rates);

type Band = { upTo: number; rate: number };
type Block = { h3?: string; table?: string[][] };

/** Reads the PAYE band table that follows the given heading in the payroll file. */
function bandsFor(heading: string): Band[] {
  const content = payroll.content as Block[];
  const start = content.findIndex((block) => block.h3 === heading);
  const table = content.slice(start + 1).find((block) => block.table)?.table ?? [];
  return table.slice(1).map((row) => {
    const rate = Number.parseFloat(row[1] ?? "") / 100;
    const limit = /£([\d,]+)/g;
    const amounts = [...(row[2] ?? "").matchAll(limit)].map((m) => Number(m[1]!.replace(/,/g, "")));
    const isTop = /^above/i.test(row[2] ?? "");
    return { rate, upTo: isTop ? Infinity : (amounts[amounts.length - 1] ?? Infinity) };
  });
}

const BANDS: Record<Region, Band[]> = {
  england: bandsFor("England and Northern Ireland"),
  wales: bandsFor("Wales"),
  scotland: bandsFor("Scotland"),
};

const round2 = (value: number) => Math.round(value * 100) / 100;

function taxOnBands(taxable: number, bands: Band[], bandShift: number) {
  let tax = 0;
  let previous = 0;
  for (const band of bands) {
    const upper = band.upTo === Infinity ? Infinity : band.upTo;
    const slice = Math.min(taxable, upper) - previous;
    if (slice > 0) tax += slice * band.rate;
    previous = upper;
    if (taxable <= upper) break;
  }
  return tax + bandShift;
}

/** Returns the modeled allowance or explicit flat rate for the selected jurisdiction. */
function parseCode(
  code: string,
  income: number,
  region: Region,
): { allowance: number } | { rate: number } | null {
  let clean = code.trim().toUpperCase();
  if (clean === "AUTO" || clean === "") {
    const reduction =
      Math.max(0, income - income_values.allowance_taper_start_adjusted_net_income) *
      income_values.allowance_reduction_per_pound_over_threshold;
    return { allowance: Math.max(0, V.personal_allowance_annual - reduction) };
  }
  const rates: Record<string, number> = taxCodes.values.flat_rates[region];
  if (Object.hasOwn(rates, clean)) return { rate: rates[clean]! };
  if (/^[SC]/.test(clean)) {
    const prefix = region === "scotland" ? "S" : region === "wales" ? "C" : null;
    if (!prefix || !clean.startsWith(prefix)) return null;
    clean = clean.slice(1);
  }
  if (clean === "0T") return { allowance: 0 };
  const k = /^K(\d{1,4})$/.exec(clean);
  if (k) return { allowance: -Number(k[1]) * 10 };
  const match = /^(\d{1,4})[LMNT]$/.exec(clean);
  if (match) return { allowance: Number(match[1]) * 10 + 9 };
  return null;
}

const income_values = income.values;

export function calculateTakeHome(input: TakeHomeInput): TakeHomeResult | null {
  const { salary, pensionPercent, benefits, otherDeductions } = input;
  if (![salary, pensionPercent, benefits, otherDeductions].every(Number.isFinite)) return null;
  if (salary <= 0 || pensionPercent < 0 || pensionPercent > 100 || benefits < 0) return null;
  if (otherDeductions < 0) return null;
  const ni = V.employee_ni_rates[input.niCategory as keyof typeof V.employee_ni_rates];
  if (!ni) return null;

  const pension = (salary * pensionPercent) / 100;
  const sacrifice = input.pensionMethod === "salary_sacrifice" ? pension : 0;
  const netPay = input.pensionMethod === "net_pay" ? pension : 0;
  const reliefAtSource = input.pensionMethod === "relief_at_source" ? pension : 0;
  const grossPay = salary - sacrifice; // pay subject to NI and loans
  const taxablePay = Math.max(0, grossPay - netPay + benefits);

  const parsed = parseCode(input.otherJobs ? "BR" : input.taxCode, taxablePay, input.region);
  if (!parsed) return null;
  const bands = BANDS[input.region];
  let tax = 0;
  if ("rate" in parsed) {
    tax = taxablePay * parsed.rate;
  } else {
    // A negative (K code) allowance increases taxable pay.
    tax = taxOnBands(Math.max(0, taxablePay - parsed.allowance), bands, 0);
  }

  const pt = V.ni_thresholds["Primary threshold"].year;
  const uel = V.ni_thresholds["Upper earnings limit"].year;
  const [, midRate, topRate] = ni as [number, number, number];
  const niDue =
    Math.max(0, Math.min(grossPay, uel) - pt) * midRate + Math.max(0, grossPay - uel) * topRate;

  const plan = input.studentLoan === "none" ? null : `student loan ${input.studentLoan}`;
  const planThreshold = plan
    ? V.student_loans[plan as keyof typeof V.student_loans].year
    : Infinity;
  const loan = plan ? Math.max(0, grossPay - planThreshold) * V.student_loan_rate : 0;
  const pgl = input.postgradLoan
    ? Math.max(0, grossPay - V.student_loans["postgraduate loan"].year) * V.postgraduate_loan_rate
    : 0;

  const reliefPaid = reliefAtSource * 0.8; // basic-rate relief is added by the provider
  const takeHome =
    salary - sacrifice - netPay - tax - niDue - loan - pgl - reliefPaid - otherDeductions;

  const rows: Row[] = [
    { label: "Gross salary", annual: salary },
    ...(sacrifice ? [{ label: "Pension (salary sacrifice)", annual: -sacrifice }] : []),
    ...(netPay ? [{ label: "Pension (net pay)", annual: -netPay }] : []),
    { label: "Income tax", annual: -tax },
    { label: "National Insurance", annual: -niDue },
    ...(loan ? [{ label: "Student loan", annual: -loan }] : []),
    ...(pgl ? [{ label: "Postgraduate loan", annual: -pgl }] : []),
    ...(reliefPaid ? [{ label: "Pension (relief at source, paid)", annual: -reliefPaid }] : []),
    ...(otherDeductions ? [{ label: "Other deductions", annual: -otherDeductions }] : []),
    { label: "Take-home pay", annual: takeHome },
  ].map((row) => ({ ...row, annual: round2(row.annual) }));

  const notes = [
    "Rates are for the 2026 to 2027 tax year (6 April 2026 to 5 April 2027).",
    "Estimate only: it does not model higher-rate relief on relief-at-source pensions, the Scottish starter band for non-standard codes, or cumulative tax code adjustments.",
  ];
  if (input.otherJobs) notes.push("Other jobs: this job is taxed at the basic rate (code BR).");
  return {
    rows,
    annual: round2(takeHome),
    monthly: round2(takeHome / 12),
    weekly: round2(takeHome / 52),
    notes,
  };
}
