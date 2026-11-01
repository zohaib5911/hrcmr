/** What the shell needs to know about the signed-in person. T3.4 fills these from `/auth/me`. */

export type PlanId = "free" | "annual" | "ten-year";

export const PLAN_LABELS: Record<PlanId, string> = {
  free: "Free",
  annual: "1 year",
  "ten-year": "10 years",
};

export interface ShellCompany {
  id: string;
  name: string;
  plan: PlanId;
}

export interface ShellUser {
  name: string;
  email: string;
  /** "Company Admin", "People Manager" and so on. */
  role: string;
}

export interface ShellSession {
  user: ShellUser;
  company: ShellCompany;
  /** Every company this person can switch to, including the current one. */
  companies: readonly ShellCompany[];
}
