/** The Recruitment workspace's tabs, in order. The address carries the open one (`?tab=`, O6.1.6). */
export const RECRUITMENT_TABS = ["requisitions", "postings", "candidates", "applications"] as const;
export type RecruitmentTab = (typeof RECRUITMENT_TABS)[number];
