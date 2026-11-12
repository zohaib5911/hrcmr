const employerGuide = {
  title: "Home Office — Right to work checks: an employer’s guide (1 October 2026)",
  url: "https://www.gov.uk/government/publications/right-to-work-checks-employers-guide",
};
const checking = {
  title: "GOV.UK — Checking a job applicant’s right to work",
  url: "https://www.gov.uk/check-job-applicant-right-to-work",
};
const checkingService = {
  title: "GOV.UK — Use the Employer Checking Service",
  url: "https://www.gov.uk/employee-immigration-employment-status",
};
const sponsorDuties = {
  title: "Home Office — Sponsor guidance, Part 3: duties and compliance",
  url: "https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance-accessible",
};
const appendixD = {
  title: "Home Office — Appendix D: record-keeping duties",
  url: "https://www.gov.uk/government/publications/keep-records-for-sponsorship-appendix-d/workers-and-temporary-workers-guidance-for-sponsors-appendix-d-record-keeping-duties-accessible",
};

export const guideDisclaimer =
  "General information only, not legal, immigration or employment advice. Rules and individual circumstances vary. Check the linked official guidance and seek qualified advice before acting. No guide or self-test certifies compliance.";

export const guides = [
  {
    slug: "right-to-work-checks",
    title: "Right to Work checks",
    description: "Plan a consistent pre-start check and retain a clear evidence trail.",
    reviewedOn: "2026-11-12",
    sources: [checking, employerGuide, checkingService],
  },
  {
    slug: "follow-up-right-to-work-checks",
    title: "Follow-up Right to Work checks",
    description: "Assign follow-ups, handle uncertainty and record the next decision.",
    reviewedOn: "2026-11-12",
    sources: [checkingService, employerGuide],
  },
  {
    slug: "right-to-work-changes-october-2026",
    title: "Right to Work changes from 1 October 2026",
    description: "Verified changes to working arrangements and digital checking services.",
    reviewedOn: "2026-11-12",
    sources: [
      employerGuide,
      {
        title: "UK Parliament — Written answer on digital right to work checks, 28 August 2026",
        url: "https://questions-statements.parliament.uk/written-questions/detail/2026-08-28/20945",
      },
    ],
  },
  {
    slug: "sponsor-licence-audit-preparation",
    title: "Sponsor licence audit preparation",
    description: "Review evidence and try our 26-question preparation self-test.",
    reviewedOn: "2026-11-12",
    sources: [appendixD, sponsorDuties],
  },
  {
    slug: "statutory-holiday-entitlement",
    title: "Statutory holiday entitlement",
    description: "Identify the working pattern, entitlement and calculation inputs.",
    reviewedOn: "2026-11-12",
    sources: [
      {
        title: "GOV.UK — Holiday entitlement",
        url: "https://www.gov.uk/holiday-entitlement-rights",
      },
      {
        title: "GOV.UK — Calculate leave entitlement",
        url: "https://www.gov.uk/holiday-entitlement-rights/calculate-leave-entitlement",
      },
      {
        title: "GOV.UK — Holiday pay",
        url: "https://www.gov.uk/holiday-entitlement-rights/holiday-pay",
      },
    ],
  },
  {
    slug: "sponsor-reporting-duties",
    title: "Sponsor reporting duties",
    description: "Identify reportable events, assign action and retain confirmation.",
    reviewedOn: "2026-11-12",
    sources: [sponsorDuties],
  },
] as const;

export type GuideSlug = (typeof guides)[number]["slug"];

export function findGuide(slug: string) {
  return guides.find((guide) => guide.slug === slug);
}
