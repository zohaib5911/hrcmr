/**
 * Made-up people for the /design page. This file is imported only by the development-only design
 * page, so none of it is in a production build (plan 0.1 rule 5).
 */

export interface DemoPerson {
  id: string;
  name: string;
  department: string;
  role: string;
  status: "verified" | "expiring" | "expired" | "pending" | "not-recorded";
  salary: number;
  start: string;
}

const FIRST = [
  "Ada",
  "Grace",
  "Alan",
  "Katherine",
  "Tim",
  "Margaret",
  "Edsger",
  "Barbara",
  "Linus",
  "Radia",
  "Donald",
  "Frances",
];
const LAST = [
  "Lovelace",
  "Hopper",
  "Turing",
  "Johnson",
  "Berners",
  "Hamilton",
  "Dijkstra",
  "Liskov",
  "Torvalds",
  "Perlman",
  "Knuth",
  "Allen",
];
const DEPARTMENTS = ["Operations", "Finance", "People", "Engineering", "Care"];
const ROLES = ["Coordinator", "Analyst", "Manager", "Assistant", "Lead"];
const STATUSES = [
  "verified",
  "verified",
  "expiring",
  "pending",
  "expired",
  "not-recorded",
] as const;

/** Deterministic: the same `count` always gives the same people. */
export function demoPeople(count: number): DemoPerson[] {
  return Array.from({ length: count }, (_, i) => {
    const month = String((i % 12) + 1).padStart(2, "0");
    const day = String((i % 27) + 1).padStart(2, "0");
    return {
      id: `emp-${String(i + 1).padStart(4, "0")}`,
      name: `${FIRST[i % FIRST.length]} ${LAST[(i * 7) % LAST.length]}`,
      department: DEPARTMENTS[i % DEPARTMENTS.length] ?? "Operations",
      role: ROLES[(i * 3) % ROLES.length] ?? "Coordinator",
      status: STATUSES[i % STATUSES.length] ?? "verified",
      salary: 24000 + ((i * 1373) % 36000),
      start: `${2018 + (i % 8)}-${month}-${day}`,
    };
  });
}

export const DEMO_OPTIONS = [
  { value: "ops", label: "Operations", description: "Day-to-day running of the business" },
  { value: "fin", label: "Finance", description: "Payroll liaison and reporting" },
  { value: "ppl", label: "People", description: "Hiring, onboarding, compliance" },
  { value: "eng", label: "Engineering", description: "Product and platform" },
  { value: "care", label: "Care services", description: "Frontline staff" },
] as const;

export function searchDemo(query: string): Promise<readonly (typeof DEMO_OPTIONS)[number][]> {
  const needle = query.toLocaleLowerCase("en-GB");
  return new Promise((resolve) =>
    setTimeout(
      () =>
        resolve(DEMO_OPTIONS.filter((o) => o.label.toLocaleLowerCase("en-GB").includes(needle))),
      400,
    ),
  );
}
