import noticeGb from "@/rates/notice-gb.json";
import noticeNi from "@/rates/notice-ni.json";
import resignation from "@/rates/notice-resignation.json";

export type Jurisdiction = "gb" | "ni";
export type Giver = "employer" | "employee";
export type Status = "employee" | "worker";
export type PayMode = "weekly" | "annual";
export type Arrangement = "work" | "garden-leave" | "pilon";

export const noticeGbSource = {
  title: noticeGb.title,
  url: noticeGb.source_url,
  checkedOn: noticeGb.checked_on,
  validFrom: noticeGb.valid_from,
  validTo: noticeGb.valid_to,
};
export const noticeNiSource = {
  title: "Giving or getting notice for your job - nidirect",
  url: noticeNi.source_url,
  checkedOn: noticeNi.checked_on,
  validFrom: noticeNi.valid_from,
  validTo: noticeNi.valid_to,
};
export const resignationSource = {
  title: resignation.title,
  url: resignation.source_url,
  checkedOn: resignation.checked_on,
  validFrom: resignation.valid_from,
  validTo: resignation.valid_to,
};

// GB and NI statutory scales are the same in both rates files (1 week, +1 per complete year, max 12).
const v = noticeGb.values;

export type NoticeInput = {
  jurisdiction: Jurisdiction;
  giver: Giver;
  status: Status;
  startDate: string;
  noticeDate: string;
  /** Contract notice in whole weeks; null when the contract is silent. */
  contractWeeks: number | null;
  payMode: PayMode;
  /** Weekly pay, or annual salary when payMode is "annual". */
  amount: number;
  arrangement: Arrangement;
};

export type NoticeResult = {
  ok: true;
  completedYears: number;
  statutoryWeeks: number;
  contractWeeks: number | null;
  noticeWeeks: number;
  weeklyPay: number;
  noticePay: number;
  lastDay: string | null;
  notes: string[];
  workings: string[];
};
export type NoticeError = { ok: false; error: string };

const DAY = 86_400_000;
const parse = (iso: string) => {
  const t = Date.parse(`${iso}T00:00:00Z`);
  return Number.isNaN(t) ? null : t;
};
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
const round2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100;

/** Whole years between two ISO dates (anniversary reached on or before `to`). */
export function completedYears(from: string, to: string): number {
  const a = parse(from);
  const b = parse(to);
  if (a === null || b === null || b < a) return 0;
  const f = new Date(a);
  const t = new Date(b);
  let years = t.getUTCFullYear() - f.getUTCFullYear();
  const beforeAnniversary =
    t.getUTCMonth() < f.getUTCMonth() ||
    (t.getUTCMonth() === f.getUTCMonth() && t.getUTCDate() < f.getUTCDate());
  if (beforeAnniversary) years -= 1;
  return Math.max(0, years);
}

/** True when at least one calendar month of service has passed. */
export function hasOneMonth(from: string, to: string): boolean {
  const a = parse(from);
  const b = parse(to);
  if (a === null || b === null || b < a) return false;
  const f = new Date(a);
  const next = Date.UTC(
    f.getUTCFullYear(),
    f.getUTCMonth() + v.minimum_service_months,
    f.getUTCDate(),
  );
  return b >= next;
}

export function statutoryNoticeWeeks(
  giver: Giver,
  status: Status,
  startDate: string,
  noticeDate: string,
): number {
  if (status !== "employee") return 0;
  if (!hasOneMonth(startDate, noticeDate)) return 0;
  if (giver === "employee") return resignation.values.minimum_statutory_weeks;
  const years = completedYears(startDate, noticeDate);
  if (years < v.one_week_per_completed_year_from_years) return v.minimum_weeks;
  return Math.min(years, v.maximum_statutory_weeks);
}

export function calculateNotice(input: NoticeInput): NoticeResult | NoticeError {
  const start = parse(input.startDate);
  const notice = parse(input.noticeDate);
  if (start === null || notice === null) return { ok: false, error: "Enter both dates." };
  if (notice < start) return { ok: false, error: "The notice date is before the start date." };
  if (!Number.isFinite(input.amount) || input.amount <= 0)
    return { ok: false, error: "Enter pay greater than zero." };
  if (
    input.contractWeeks !== null &&
    (!Number.isInteger(input.contractWeeks) || input.contractWeeks < 0)
  )
    return { ok: false, error: "Contract notice must be a whole number of weeks, or blank." };

  const years = completedYears(input.startDate, input.noticeDate);
  const statutory = statutoryNoticeWeeks(
    input.giver,
    input.status,
    input.startDate,
    input.noticeDate,
  );
  const contract = input.contractWeeks;
  const noticeWeeks = Math.max(statutory, contract ?? 0);
  const weeklyPay = round2(input.payMode === "annual" ? input.amount / 52 : input.amount);
  const noticePay = round2(weeklyPay * noticeWeeks);
  const lastDay = noticeWeeks > 0 ? iso(notice + noticeWeeks * 7 * DAY) : null;

  const workings = [
    `Completed years of service at the notice date: ${years}.`,
    `Statutory minimum: ${statutory} week${statutory === 1 ? "" : "s"}.`,
    contract === null
      ? "Contract notice: not stated."
      : `Contract notice: ${contract} week${contract === 1 ? "" : "s"}.`,
    `Notice used: the longer of the two = ${noticeWeeks} week${noticeWeeks === 1 ? "" : "s"}.`,
    input.payMode === "annual"
      ? `Weekly pay: £${input.amount} ÷ 52 = £${weeklyPay.toFixed(2)}.`
      : `Weekly pay: £${weeklyPay.toFixed(2)}.`,
    `Notice pay: £${weeklyPay.toFixed(2)} × ${noticeWeeks} = £${noticePay.toFixed(2)}.`,
  ];

  const notes: string[] = [];
  if (input.status === "worker")
    notes.push(
      "Statutory notice applies to employees. A worker’s notice is whatever the contract says, or a reasonable period.",
    );
  if (input.giver === "employee" && contract === null && statutory > 0)
    notes.push(
      "If the contract sets no period you should give the statutory minimum (a reasonable period applies in Northern Ireland).",
    );
  if (input.giver === "employer" && contract !== null && contract < statutory)
    notes.push(
      "The contract gives less than the statutory minimum, so the statutory period applies: an employer cannot give less.",
    );
  if (noticeWeeks > 0) {
    notes.push(
      "The notice period usually runs from the start of the day after notice is given, so the last day shown is the final day of employment unless you agree otherwise.",
    );
  }
  if (input.arrangement === "work")
    notes.push("You work through the notice period and are paid normal wages for it.");
  if (input.arrangement === "garden-leave")
    notes.push(
      "On garden leave you are entitled to normal pay and company benefits for the whole notice period.",
    );
  if (input.arrangement === "pilon") {
    notes.push(
      "Payment in lieu of notice (PILON) pays all the basic pay you would have received in the notice period. Pension contributions and benefits may be due if the contract says so; they are not included here.",
    );
    notes.push(
      "Tax and National Insurance are due on PILON; this tool shows the gross amount only. Check the contract for whether a PILON clause exists.",
    );
  }
  notes.push(
    "Pay is based on the average weekly amount earned over the 12 weeks before notice starts; enter that figure for varying pay.",
  );
  notes.push(
    "Final pay should also include accrued untaken holiday and any other amounts owed. This tool does not calculate them.",
  );
  if (input.jurisdiction === "ni")
    notes.push(
      "Northern Ireland: rules shown are from nidirect; check with the Labour Relations Agency.",
    );
  if (input.giver === "employer")
    notes.push("Notice may not be needed in cases of gross misconduct (summary dismissal).");

  return {
    ok: true,
    completedYears: years,
    statutoryWeeks: statutory,
    contractWeeks: contract,
    noticeWeeks,
    weeklyPay,
    noticePay,
    lastDay,
    notes,
    workings,
  };
}
