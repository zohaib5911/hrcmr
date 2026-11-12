import data from "@/rates/ilr-citizenship.json";

const rules = data.values;
export const settlementRoutes = rules.routes;
export type SettlementInput = {
  route: string;
  startDate: string;
  residenceStart: string;
  settledDate: string;
  britishSpouse: boolean;
  rollingAbsences: number;
  citizenshipAbsences: number;
  lastYearAbsences: number;
};
export type SettlementResult = {
  qualifyingDate: string;
  citizenshipDate: string;
  indicative: boolean;
  settlementReview: boolean;
  citizenshipReview: boolean;
  notes: string[];
};

const evidence = [
  ...settlementRoutes.map((route) => route.source),
  rules.citizenship.standard.source,
  rules.citizenship.british_spouse.source,
  rules.continuous_residence_source,
];
export const settlementSources = evidence
  .filter(
    (source, index) => evidence.findIndex((s) => s.source_url === source.source_url) === index,
  )
  .map((source) => ({
    title: source.title,
    url: source.source_url,
    checkedOn: source.checked_on,
    validFrom: source.valid_from,
    validTo: source.valid_to,
  }));

function parseDate(value: string): Date {
  const date = new Date(value);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
    !Number.isFinite(date.getTime()) ||
    date.toISOString().slice(0, 10) !== value
  ) {
    throw new Error("Enter valid calendar dates.");
  }
  return date;
}

// Calendar arithmetic in UTC, clamping leap-day anniversaries to month end.
function addMonths(value: string, months: number) {
  const date = parseDate(value);
  const day = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() + months);
  const end = new Date(date.getTime());
  end.setUTCMonth(end.getUTCMonth() + 1, 0);
  date.setUTCDate(Math.min(day, end.getUTCDate()));
  return date.toISOString().slice(0, 10);
}

/** Conditional residence milestones, never an immigration eligibility determination. */
export function checkSettlement(input: SettlementInput): SettlementResult {
  const route = settlementRoutes.find((route) => route.id === input.route);
  if (!route) throw new Error("Select a supported visa pathway.");
  parseDate(input.startDate);
  parseDate(input.residenceStart);
  if (input.residenceStart > input.startDate)
    throw new Error("UK residence cannot start after qualifying route residence.");
  if (input.settledDate) {
    parseDate(input.settledDate);
    if (input.settledDate < input.residenceStart)
      throw new Error("Settlement cannot predate UK residence.");
  }
  for (const value of [input.rollingAbsences, input.citizenshipAbsences, input.lastYearAbsences]) {
    if (!Number.isSafeInteger(value) || value < 0)
      throw new Error("Enter whole, non-negative absence days.");
  }
  if (input.lastYearAbsences > input.citizenshipAbsences)
    throw new Error("Last-year absences cannot exceed the citizenship-period total.");
  const citizenship = input.britishSpouse
    ? rules.citizenship.british_spouse
    : rules.citizenship.standard;
  const qualifyingDate = addMonths(input.startDate, route.years * 12);
  // Without an actual grant, use the full qualifying anniversary only as an assumption.
  const settlement = input.settledDate || qualifyingDate;
  const citizenshipDate = [
    addMonths(settlement, citizenship.settled_months),
    addMonths(input.residenceStart, citizenship.years * 12),
  ]
    .sort()
    .at(-1)!;
  const settlementReview =
    !route.rolling_absence_check || input.rollingAbsences > rules.settlement_absence_days;
  const citizenshipReview =
    input.citizenshipAbsences > citizenship.total_absence_days ||
    input.lastYearAbsences > rules.citizenship.last_year_absence_days;
  const notes = [
    route.note,
    "The ILR date is the full qualifying-residence anniversary, not an early application date or a grant date. Gaps, lawful status and route-specific conditions must be checked.",
    `Citizenship requires physical presence in the UK exactly ${citizenship.years} years before receipt of the application. Check age, language, Life in the UK, good character and continuing residence requirements.`,
    "Absence totals must cover the relevant periods ending on your proposed application dates. Future travel changes the result; discretionary exceptions need individual advice.",
  ];
  if (!input.settledDate)
    notes.push(
      "Indicative citizenship date assumes ILR is granted on the qualifying anniversary. Enter the actual grant date when known; processing time can delay citizenship.",
    );
  if (settlementReview)
    notes.push(
      "Settlement residence needs individual review. No eligible-to-apply verdict is given; absence exceptions and historical rules are not resolved by this tool.",
    );
  if (citizenshipReview)
    notes.push(
      "Citizenship absences exceed the usual limits. The date is a residence milestone only; seek advice before applying.",
    );
  return {
    qualifyingDate,
    citizenshipDate,
    indicative: !input.settledDate,
    settlementReview,
    citizenshipReview,
    notes,
  };
}
