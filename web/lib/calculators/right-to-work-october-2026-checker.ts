import guidance from "@/rates/right-to-work.json";

export type Engagement = "employee" | "worker" | "subcontractor" | "matching" | "other";
export type Answer = "yes" | "no" | "unsure";
export type RightToWorkInput = {
  engagement: Engagement;
  workInUK: Answer;
  independentBusiness: Answer;
  employmentStart: string;
  contractChain: Answer;
  substitution: Answer;
  arrangementStart: string;
};
export type Duty = "applies" | "outside" | "review" | "predates";
export type RightToWorkResult = {
  direct: Duty;
  extended: Duty;
  explanation: string[];
  actions: string[];
  records: string[];
};

// Export metadata only: the complete captured PDF is not needed in the browser bundle.
export const rightToWorkSource = {
  title: "Home Office: employer’s guide to right to work checks",
  url: guidance.source_url,
  checkedOn: guidance.checked_on,
  validFrom: guidance.valid_from,
  validTo: guidance.valid_to,
};

function validDate(value: string) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  );
}

/** Scope guidance, never a determination of an individual's immigration status. */
export function checkRightToWork(input: RightToWorkInput): RightToWorkResult {
  const result: RightToWorkResult = {
    direct: "review",
    extended: "review",
    explanation: [],
    actions: [],
    records: [],
  };
  if (input.workInUK === "no") {
    return {
      ...result,
      direct: "outside",
      extended: "outside",
      explanation: ["This UK scheme does not cover work carried out outside the UK."],
    };
  }
  if (input.workInUK !== "yes") {
    return {
      ...result,
      explanation: ["Confirm where the work is carried out before assessing scope."],
    };
  }

  const independent =
    input.independentBusiness === "yes" &&
    (input.engagement === "subcontractor" || input.engagement === "other");
  if (independent) {
    result.direct = "outside";
    result.explanation.push(
      "A client buying services directly from an independent business is outside the direct-check scheme. Labels alone do not establish independence.",
    );
  } else if (
    input.engagement === "other" ||
    (input.engagement !== "employee" && input.independentBusiness !== "no")
  ) {
    result.explanation.push(
      "Review the actual working relationship: who personally works, who engages them and who controls the arrangement.",
    );
  } else if (!validDate(input.employmentStart)) {
    result.explanation.push(
      "Enter a valid employment or engagement start date to assess direct civil-penalty scope.",
    );
  } else {
    const threshold =
      input.engagement === "employee"
        ? guidance.values.original_employee_civil_penalty_from
        : guidance.values.extended_duty_from;
    result.direct = input.employmentStart >= threshold ? "applies" : "predates";
    result.explanation.push(
      result.direct === "applies"
        ? "The direct right-to-work check duty applies to this engagement."
        : `This engagement started before ${threshold}, the relevant civil-penalty commencement date. This does not establish permission to work or remove other legal duties.`,
    );
  }

  const extendedTrigger =
    input.engagement === "matching" ||
    input.contractChain === "yes" ||
    input.substitution === "yes";
  if (extendedTrigger) {
    if (!validDate(input.arrangementStart)) {
      result.explanation.push(
        "Enter the date of the relevant contractual arrangement separately from the worker’s start date.",
      );
    } else {
      result.extended =
        input.arrangementStart >= guidance.values.extended_duty_from ? "applies" : "predates";
      result.explanation.push(
        result.extended === "applies"
          ? "Extended liability may also apply through the contract chain, matching service or permitted substitution. Review the contracts and how they operate."
          : "The arrangement predates the extended-liability commencement date. Review later renewals or changes separately.",
      );
    }
  } else if (input.contractChain === "no" && input.substitution === "no") {
    result.extended = "outside";
  } else {
    result.explanation.push(
      "Clarify the contract chain and substitution terms to assess extended liability.",
    );
  }

  if (result.direct === "applies") {
    result.actions.push(
      "Complete the prescribed check before work starts: manual originals, the Home Office online service or an eligible registered digital verification provider. Use the Employer Checking Service where required.",
      "Check identity and work restrictions, use a consistent process for all workers and re-check time-limited permission before it expires.",
    );
    result.records.push(
      `Keep a secure check record, the check date and required evidence throughout employment and for ${guidance.values.record_retention_years_after_employment} years after it ends.`,
    );
  }
  if (result.extended === "applies") {
    result.actions.push(
      "Before work begins, put the applicable section 3 safeguards in place and verify that they operate in practice; contract wording alone is insufficient.",
    );
    if (input.contractChain === "yes" || input.engagement === "matching") {
      result.actions.push(
        "Use written terms requiring prescribed checks, prior written consent to further subcontracting with equivalent obligations, audit rights, enforcement provisions and cooperation with Home Office investigations.",
      );
    }
    if (input.substitution === "yes") {
      result.actions.push(
        "Ensure substitutes are checked before working, keep check responsibility with the employer rather than the worker, and maintain authorisation and enforcement controls.",
      );
    }
    result.actions.push(
      "Maintain proportionate ongoing identity checks linking the person doing the work to the person whose right to work was checked.",
    );
    result.records.push(
      "Retain relevant contracts, check assurances, audits, substitution authorisations, identity controls and evidence of action on concerns; follow the guidance and your data-retention policy.",
    );
  }
  if (result.direct === "review" || result.extended === "review") {
    result.actions.push(
      "Resolve the uncertain facts using the Home Office guidance or specialist advice before relying on a statutory excuse.",
    );
  }
  return result;
}
