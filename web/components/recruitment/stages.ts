import type { components } from "@/lib/api/client";

export type Stage = components["schemas"]["ApplicationOut"]["stage"];
export type StageTone = "neutral" | "success" | "warning" | "info" | "danger";

/** The six forward stages, in order. Rejected and withdrawn end an application. */
export const FORWARD_STAGES: readonly Stage[] = [
  "applied",
  "shortlisted",
  "interview",
  "offer_letter",
  "offer_accepted",
  "hired",
];
export const ENDING_STAGES: readonly Stage[] = ["rejected", "withdrawn"];
export const ALL_STAGES: readonly Stage[] = [...FORWARD_STAGES, ...ENDING_STAGES];

export const STAGE_LABEL: Record<Stage, string> = {
  applied: "Job Applied",
  shortlisted: "Shortlisted",
  interview: "Interview",
  offer_letter: "Offer Letter",
  offer_accepted: "Offer Accepted",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const STAGE_TONE: Record<Stage, StageTone> = {
  applied: "info",
  shortlisted: "info",
  interview: "info",
  offer_letter: "warning",
  offer_accepted: "success",
  hired: "success",
  rejected: "danger",
  withdrawn: "neutral",
};

/** The stage a forward move would go to next, or null for an ended or hired application. */
export function nextStage(stage: Stage): Stage | null {
  const at = FORWARD_STAGES.indexOf(stage);
  if (at === -1 || at === FORWARD_STAGES.length - 1) return null;
  return FORWARD_STAGES[at + 1] ?? null;
}

/** What the application is waiting on, in plain words. */
export function waitingOn(stage: Stage): string {
  switch (stage) {
    case "applied":
      return "Waiting for a shortlisting decision.";
    case "shortlisted":
      return "Waiting for an interview to be arranged.";
    case "interview":
      return "Waiting for the interview outcome.";
    case "offer_letter":
      return "Waiting for the candidate's answer to the offer.";
    case "offer_accepted":
      return "Waiting for the start date.";
    case "hired":
      return "Hired.";
    case "rejected":
    case "withdrawn":
      return "This application has ended.";
  }
}
