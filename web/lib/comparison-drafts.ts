/** Editorial templates only. Publishing requires a separate reviewed change. */
export const comparisonDrafts = {
  "hr-software-uk": {
    title: "Compare UK HR software",
    introduction:
      "Compare the HR tasks your team needs to manage, alongside the scope and cost of each plan.",
    criteria: [
      "Employee records",
      "Leave and attendance",
      "Documents and policies",
      "Recruitment",
      "Support and setup",
    ],
  },
  "sponsor-compliance-software-uk": {
    title: "Compare UK sponsor compliance software",
    introduction:
      "Review how each product supports your sponsor duties and which checks your team still needs to carry out.",
    criteria: [
      "Right to Work records",
      "Visa expiry reminders",
      "Reporting duties",
      "Audit evidence",
      "Support and setup",
    ],
  },
  competitor: {
    title: "Compare with [competitor name]",
    introduction:
      "Add an evidence-based comparison of the named products and plans before requesting publication approval.",
    criteria: [
      "Plan scope",
      "Included features",
      "Usage limits",
      "Support",
      "Contract and billing terms",
    ],
  },
} as const;

export type ComparisonDraft = (typeof comparisonDrafts)[keyof typeof comparisonDrafts];
