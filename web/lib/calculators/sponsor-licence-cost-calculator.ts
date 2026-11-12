import cos from "@/rates/cos.json";
import healthVisa from "@/rates/health-visa-fees.json";
import ihs from "@/rates/ihs.json";
import licence from "@/rates/licence.json";
import priorityOutside from "@/rates/visa-priority.json";
import grantRules from "@/rates/skilled-worker.json";
import feeBasis from "@/rates/sponsor-visa-fee-basis.json";
import skills from "@/rates/skills-charge.json";
import visaFees from "@/rates/visa-fees.json";

export type LicenceType = "new" | "add_worker";
export type Route = "skilled_worker" | "health_care";
export type Speed = "standard" | "priority" | "super_priority";
export type Basis = "standard" | "salary_list";

export type SponsorCostInput = {
  licenceType: LicenceType;
  charity: boolean;
  turnover: number;
  assets: number;
  employees: number;
  route: Route;
  insideUK: boolean;
  months: number; // certificate length, 1–60
  soc: string;
  gpTraining?: boolean; // required for SOC 2211; SW 18.1A
  workers: number;
  adultDependants: number;
  childDependants: number;
  speed: Speed;
  licencePriority: boolean;
  basis: Basis;
};

export type SponsorCostResult = {
  visaPeriod: string;
  small: boolean;
  licenceFee: number;
  licencePriorityFee: number;
  cosFee: number; // per worker
  skillsCharge: number; // per worker
  skillsChargeExempt: boolean;
  visaFeePerPerson: number;
  speedFeePerPerson: number;
  healthSurchargeWorker: number;
  healthSurchargeAdult: number;
  healthSurchargeChild: number;
  employerTotal: number; // licence + CoS + ISC: must be paid by the sponsor
  workerSideTotal: number; // visa, speed, IHS for workers and dependants
  grandTotal: number;
};

const L = licence.values;
const S = skills.values;
const I = ihs.values;
const V = visaFees.values;

export const sponsorCostSources = [
  licence,
  cos,
  skills,
  visaFees,
  healthVisa,
  ihs,
  priorityOutside,
  grantRules,
  feeBasis,
].map((file) => ({
  title: file.title,
  url: file.source_url,
  checkedOn: file.checked_on,
  validFrom: file.valid_from,
  validTo: file.valid_to,
}));

/** Priority fees are published only as prose; read them from the stored guidance text. */
function priorityFee(kind: "priority" | "super"): number {
  const text = JSON.stringify(priorityOutside.content);
  const match =
    kind === "priority"
      ? /Using the priority service[^]*?pay £([\d,]+) in addition/.exec(text)
      : /Using the super priority service[^]*?pay £([\d,]+) in addition/.exec(text);
  if (!match?.[1]) throw new Error("Priority fee not found in rates file");
  return Number(match[1].replace(",", ""));
}

export function isSmallSponsor(
  input: Pick<SponsorCostInput, "charity" | "turnover" | "assets" | "employees">,
) {
  if (input.charity) return true;
  const met =
    Number(input.turnover <= L.small_sponsor_max_turnover) +
    Number(input.assets <= L.small_sponsor_max_assets) +
    Number(input.employees <= L.small_sponsor_max_employees);
  return met >= L.small_sponsor_criteria_required;
}

/** Immigration skills charge: 12 months, then each additional 6 months (part blocks round up). */
export function skillsChargeFor(months: number, small: boolean) {
  const first = small ? S.first_12_months_small_charity : S.first_12_months_medium_large;
  const extra = small ? S.additional_6_months_small_charity : S.additional_6_months_medium_large;
  const blocks = Math.max(0, Math.ceil((months - 12) / 6));
  return first + blocks * extra;
}

/** Healthcare surcharge per person for a stay of `months` (GOV.UK part-year rules). */
export function healthSurchargeFor(
  months: number,
  insideUK: boolean,
  child: boolean,
  extraDays: 0 | 14 = 0,
) {
  const year = child ? I.under_18_annual : I.adult_annual;
  const half = child ? I.reduced_half_year : I.adult_half_year;
  if (months < 6 || (months === 6 && extraDays === 0)) return insideUK ? half : 0;
  const years = Math.floor(months / 12);
  const rest = months - years * 12;
  if (rest === 0 && extraDays === 0) return years * year;
  return years * year + (rest < 6 || (rest === 6 && extraDays === 0) ? half : year);
}

export function calculateSponsorCosts(input: SponsorCostInput): SponsorCostResult {
  const months = Math.min(60, Math.max(1, Math.round(input.months)));
  const isGpCode = input.soc.trim() === "2211";
  if (isGpCode && input.gpTraining === undefined) {
    throw new Error("Confirm whether SOC 2211 is for GP specialty training.");
  }
  if (input.gpTraining && !isGpCode) {
    throw new Error("GP specialty training requires SOC 2211.");
  }
  const visaMonths = months + (input.gpTraining ? 4 : 0);
  const visaDays = input.gpTraining ? 0 : 14;
  const visaPeriod = `${visaMonths} months${visaDays ? " + 14 days" : " (includes 4 months for GP specialty training)"}`;
  const small = isSmallSponsor(input);
  const licenceFee =
    input.licenceType === "new"
      ? small
        ? L.worker_small_charity
        : L.worker_medium_large
      : small
        ? L.add_worker_small_charity
        : L.add_worker_medium_large;
  const licencePriorityFee = input.licencePriority ? L.priority_fee : 0;
  const cosFee = cos.values.worker;

  const exempt = S.exempt_soc_codes.includes(input.soc.trim());
  // Charged for outside-UK stays of 6 months or more, and for any inside-UK stay.
  const chargeable = !exempt && (input.insideUK || months >= 6);
  const skillsCharge = chargeable ? skillsChargeFor(months, small) : 0;

  const long = months > feeBasis.values.short_certificate_max_months;
  let visaFeePerPerson: number;
  if (input.route === "health_care") {
    visaFeePerPerson = long ? healthVisa.values.over_3_years : healthVisa.values.up_to_3_years;
  } else if (input.basis === "salary_list") {
    visaFeePerPerson = long ? V.salary_list_over_3_years : V.salary_list_up_to_3_years;
  } else if (input.insideUK) {
    visaFeePerPerson = long ? V.inside_over_3_years : V.inside_up_to_3_years;
  } else {
    visaFeePerPerson = long ? V.outside_over_3_years : V.outside_up_to_3_years;
  }
  const speedFeePerPerson =
    input.speed === "priority"
      ? priorityFee("priority")
      : input.speed === "super_priority"
        ? priorityFee("super")
        : 0;

  const noIhs = input.route === "health_care" && healthVisa.values.ihs_payable === false;
  const ihsAdult = noIhs ? 0 : healthSurchargeFor(visaMonths, input.insideUK, false, visaDays);
  const ihsChild = noIhs ? 0 : healthSurchargeFor(visaMonths, input.insideUK, true, visaDays);

  const workers = Math.max(0, Math.floor(input.workers));
  const adults = Math.max(0, Math.floor(input.adultDependants));
  const children = Math.max(0, Math.floor(input.childDependants));
  const applicants = workers + adults + children;

  const employerTotal = licenceFee + licencePriorityFee + workers * (cosFee + skillsCharge);
  const workerSideTotal =
    applicants * (visaFeePerPerson + speedFeePerPerson) +
    (workers + adults) * ihsAdult +
    children * ihsChild;

  return {
    visaPeriod,
    small,
    licenceFee,
    licencePriorityFee,
    cosFee,
    skillsCharge,
    skillsChargeExempt: exempt,
    visaFeePerPerson,
    speedFeePerPerson,
    healthSurchargeWorker: ihsAdult,
    healthSurchargeAdult: ihsAdult,
    healthSurchargeChild: ihsChild,
    employerTotal,
    workerSideTotal,
    grandTotal: employerTotal + workerSideTotal,
  };
}

export const compareLengths = [12, 18, 24, 36, 48, 60] as const;

/** Total cost for each common certificate length, all other answers unchanged. */
export function compareCertificateLengths(input: SponsorCostInput) {
  return compareLengths.map((months) => ({
    months,
    result: calculateSponsorCosts({ ...input, months }),
  }));
}
