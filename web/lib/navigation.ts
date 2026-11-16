/**
 * The signed-in app's navigation, defined once: the sidebar, the phone tab bar, the breadcrumbs and
 * the placeholder pages are all built from this list, so they cannot disagree (plan 5.6).
 *
 * `emptyTitle` and `emptyDescription` are the words on a page that has no content yet: what will
 * appear there (plan 5.8). Each feature task replaces its placeholder page with the real one.
 */
import {
  BadgeCheck,
  BellRing,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  ChartColumn,
  Clock,
  CreditCard,
  FileText,
  FolderOpen,
  GraduationCap,
  KeyRound,
  LayoutDashboard,
  LayoutGrid,
  Network,
  NotebookPen,
  ScanSearch,
  ScrollText,
  ShieldCheck,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavGroupId = "overview" | "people" | "compliance" | "time" | "me" | "company";

export interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  group: NavGroupId;
  /** One line under the page title: what the page is for. */
  purpose: string;
  /** The `href` of the page this one sits under, for breadcrumbs. */
  parent?: string;
  emptyTitle: string;
  emptyDescription: string;
}

export interface NavGroup {
  id: NavGroupId;
  label: string;
  items: readonly NavItem[];
}

type ItemInput = Omit<NavItem, "group">;

const group = (id: NavGroupId, label: string, items: readonly ItemInput[]): NavGroup => ({
  id,
  label,
  items: items.map((item) => ({ ...item, group: id })),
});

export const NAV_GROUPS: readonly NavGroup[] = [
  group("overview", "Overview", [
    {
      id: "dashboard",
      label: "Dashboard",
      purpose: "What needs your attention today.",
      href: "/dashboard",
      icon: LayoutDashboard,
      emptyTitle: "Your dashboard is on its way",
      emptyDescription:
        "What needs attention today will appear here: expiring checks, leave to approve and people to onboard.",
    },
  ]),
  group("people", "People", [
    {
      id: "employees",
      label: "Employees",
      purpose: "Everyone who works for you.",
      href: "/employees",
      icon: Users,
      emptyTitle: "No employees yet",
      emptyDescription:
        "Everyone who works for you will be listed here, with their right to work, leave and documents.",
    },
    {
      id: "recruitment",
      label: "Recruitment",
      purpose: "Open roles, candidates and offers.",
      href: "/recruitment",
      icon: BriefcaseBusiness,
      emptyTitle: "No vacancies yet",
      emptyDescription:
        "Open roles, candidates, interviews and offers will appear here, from first application to first day.",
    },
    {
      id: "organogram",
      label: "Org chart",
      purpose: "Who reports to whom.",
      href: "/organogram",
      icon: Network,
      emptyTitle: "No org chart yet",
      emptyDescription:
        "Your reporting lines will be drawn here once people have a manager and a department.",
    },
    {
      id: "learning",
      label: "Learning",
      purpose: "Courses, progress and certificates.",
      href: "/learning",
      icon: GraduationCap,
      emptyTitle: "No courses assigned yet",
      emptyDescription:
        "Compliance and induction courses will appear here, with who has finished them and who is overdue.",
    },
  ]),
  group("compliance", "Compliance", [
    {
      id: "compliance",
      label: "Sponsor compliance",
      purpose: "Your sponsor licence duties at a glance.",
      href: "/sponsor-compliance",
      icon: ShieldCheck,
      emptyTitle: "Nothing to review yet",
      emptyDescription:
        "Your sponsor licence duties will be tracked here: what needs attention, what is expiring and what to report.",
    },
    {
      id: "migrant-employees",
      label: "Sponsored employees",
      purpose: "The people you sponsor, with their route and visa dates.",
      href: "/sponsor-compliance/migrant-employees",
      icon: BadgeCheck,
      parent: "/sponsor-compliance",
      emptyTitle: "No sponsored employees yet",
      emptyDescription:
        "Employees you sponsor will be listed here with their route, certificate and visa expiry.",
    },
    {
      id: "reminders",
      label: "Reminders",
      purpose: "Document reminders, sent before they are due.",
      href: "/sponsor-compliance/reminders",
      icon: BellRing,
      parent: "/sponsor-compliance",
      emptyTitle: "No reminders due",
      emptyDescription:
        "Visa, passport and other document reminders will appear here before they are due.",
    },
    {
      id: "checker",
      label: "Sponsorship checker",
      purpose: "Check that a job can be sponsored, and what it must pay.",
      href: "/sponsorship-checker",
      icon: ScanSearch,
      emptyTitle: "No checks run yet",
      emptyDescription:
        "Check whether a job can be sponsored, find its occupation code and test the salary. Your saved reports will be listed here.",
    },
    {
      id: "documents",
      label: "Documents",
      purpose: "Company files, with their review dates.",
      href: "/documents",
      icon: FileText,
      emptyTitle: "No documents yet",
      emptyDescription:
        "Company documents, such as handbooks and certificates, will be stored here with their review dates.",
    },
    {
      id: "policies",
      label: "Policies",
      purpose: "Policies, and who has accepted them.",
      href: "/policies",
      icon: ScrollText,
      emptyTitle: "No policies yet",
      emptyDescription:
        "Policies you publish, and who has read and accepted them, will appear here.",
    },
    {
      id: "reports",
      label: "Reports",
      purpose: "Spreadsheets of your people and your compliance.",
      href: "/reports",
      icon: ChartColumn,
      emptyTitle: "No reports yet",
      emptyDescription:
        "Employee, leave, sponsor and training reports can be generated here and downloaded as spreadsheets.",
    },
  ]),
  group("time", "Time", [
    {
      id: "leave",
      label: "Leave",
      purpose: "Requests, approvals and balances.",
      href: "/leave",
      icon: CalendarDays,
      emptyTitle: "No leave booked yet",
      emptyDescription:
        "Requests, approvals and balances will appear here, with bank holidays taken into account.",
    },
    {
      id: "attendance",
      label: "Attendance",
      purpose: "Who worked when.",
      href: "/attendance",
      icon: Clock,
      emptyTitle: "No attendance recorded yet",
      emptyDescription:
        "Clock-ins, timesheets and absences will appear here once people start recording their time.",
    },
    {
      id: "rota",
      label: "Rota",
      purpose: "The week's shifts.",
      href: "/rota",
      icon: LayoutGrid,
      emptyTitle: "No shifts planned yet",
      emptyDescription:
        "The week's shifts will be laid out here, ready to publish to the people working them.",
    },
    {
      id: "work-log",
      label: "Work log",
      purpose: "What people worked on, day by day.",
      href: "/work-log",
      icon: NotebookPen,
      emptyTitle: "Nothing logged yet",
      emptyDescription: "Notes on what people worked on, by day, will appear here.",
    },
  ]),
  group("me", "Me", [
    {
      id: "my-work-log",
      label: "My work log",
      purpose: "Your daily work and responsibilities.",
      href: "/my-work-log",
      icon: NotebookPen,
      emptyTitle: "No work logged yet",
      emptyDescription:
        "Add a daily entry to record the responsibilities and work you have completed.",
    },
    {
      id: "my-shifts",
      label: "My shifts",
      purpose: "Your published working schedule.",
      href: "/my-shifts",
      icon: CalendarDays,
      emptyTitle: "No published shifts",
      emptyDescription: "Your shifts appear here after your manager publishes the weekly rota.",
    },
    {
      id: "my-leave",
      label: "My leave",
      purpose: "Your allowance and time away.",
      href: "/my-leave",
      icon: CalendarDays,
      emptyTitle: "No leave requests",
      emptyDescription: "Your leave requests appear here.",
    },
    {
      id: "my-approvals",
      label: "My approvals",
      purpose: "Leave requests awaiting your decision.",
      href: "/my-approvals",
      icon: CalendarDays,
      emptyTitle: "No pending approvals",
      emptyDescription: "Requests awaiting your decision appear here.",
    },
    {
      id: "profile",
      label: "My profile",
      purpose: "Your details and your settings.",
      href: "/profile",
      icon: UserRound,
      emptyTitle: "Your profile is on its way",
      emptyDescription:
        "Your details, your leave, your shifts and your appearance settings will be here.",
    },
    {
      id: "my-documents",
      label: "My documents",
      purpose: "Things to read, sign and keep.",
      href: "/my-documents",
      icon: FolderOpen,
      emptyTitle: "Nothing to read or sign",
      emptyDescription: "Policies to read and accept, and your own files, will appear here.",
    },
  ]),
  group("company", "Company", [
    {
      id: "company",
      label: "Company",
      purpose: "Your company's details and settings.",
      href: "/company",
      icon: Building2,
      emptyTitle: "Company settings are on their way",
      emptyDescription:
        "Your company details, locations, departments, holidays and pay settings will be managed here.",
    },
    {
      id: "users",
      label: "User access",
      purpose: "Who can sign in, and what they can do.",
      href: "/company/users",
      icon: KeyRound,
      parent: "/company",
      emptyTitle: "No other users yet",
      emptyDescription: "Invite colleagues and choose what each of them can see and do.",
    },
    {
      id: "billing",
      label: "Billing",
      purpose: "Your plan, invoices and payment method.",
      href: "/company/billing",
      icon: CreditCard,
      parent: "/company",
      emptyTitle: "No billing details yet",
      emptyDescription: "Your plan, invoices and payment method will appear here.",
    },
  ]),
];

export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

/** The bottom tab bar on phones (below 768 px). Everything else is under "More". */
export const MOBILE_TABS: readonly {
  label: string;
  href: string;
  icon: LucideIcon;
  groups: readonly NavGroupId[];
}[] = [
  { label: "Home", href: "/dashboard", icon: LayoutDashboard, groups: ["overview"] },
  { label: "People", href: "/employees", icon: Users, groups: ["people"] },
  { label: "Compliance", href: "/sponsor-compliance", icon: ShieldCheck, groups: ["compliance"] },
  { label: "Time", href: "/leave", icon: CalendarDays, groups: ["time"] },
  { label: "Me", href: "/profile", icon: UserRound, groups: ["me"] },
];

function clean(pathname: string): string {
  const path = (pathname.split(/[?#]/)[0] ?? "").replace(/\/+$/, "");
  return path === "" ? "/" : path;
}

/** The item a page belongs to: the longest address that is the page itself or one of its parents. */
export function findNavItem(pathname: string): NavItem | undefined {
  const path = clean(pathname);
  return NAV_ITEMS.filter((item) => path === item.href || path.startsWith(`${item.href}/`)).sort(
    (a, b) => b.href.length - a.href.length,
  )[0];
}

export function isActive(item: NavItem, pathname: string): boolean {
  return findNavItem(pathname)?.id === item.id;
}

/**
 * Pages inside a sidebar page that are not in the sidebar themselves (the company's set-up pages).
 * Each names the sidebar page it sits under, which is where the breadcrumb leads back to.
 */
export const SUB_PAGES: readonly { href: string; label: string; parent: string }[] = [
  { href: "/clock", label: "Clock in or out", parent: "/attendance" },
  { href: "/rota/settings", label: "Rota settings", parent: "/rota" },
  { href: "/attendance/timesheets", label: "Timesheet approvals", parent: "/attendance" },
  { href: "/attendance/import", label: "Import attendance", parent: "/attendance" },
  { href: "/attendance/bulk", label: "Bulk attendance", parent: "/attendance" },
  { href: "/attendance/absences", label: "Absences this month", parent: "/attendance" },
  { href: "/company/locations", label: "Locations", parent: "/company" },
  { href: "/company/departments", label: "Departments", parent: "/company" },
  { href: "/company/designations", label: "Designations", parent: "/company" },
  { href: "/company/key-personnel", label: "Key personnel", parent: "/company" },
  { href: "/company/working-pattern", label: "Working pattern", parent: "/company" },
  { href: "/company/bank-accounts", label: "Bank accounts", parent: "/company" },
  { href: "/company/pay-bands", label: "Pay bands", parent: "/company" },
  { href: "/company/pay-schedules", label: "Pay schedules", parent: "/company" },
  { href: "/company/payment-types", label: "Payment types", parent: "/company" },
  { href: "/company/tax-codes", label: "Tax codes", parent: "/company" },
  { href: "/company/trading-hours", label: "Trading hours", parent: "/company" },
  { href: "/company/delete-account", label: "Delete company account", parent: "/company" },
  { href: "/holiday-management", label: "Holidays", parent: "/leave" },
  { href: "/leave/year-end", label: "Leave year end", parent: "/leave" },
  { href: "/leave/settings", label: "Leave settings", parent: "/leave" },
  {
    href: "/company/compliance-documents",
    label: "Compliance documents",
    parent: "/company",
  },
];

function subPage(pathname: string) {
  const path = clean(pathname);
  return SUB_PAGES.find((page) => path === page.href || path.startsWith(`${page.href}/`));
}

/** The heading of the page at this address: a set-up page's own, else its sidebar page's. */
export function titleFor(pathname: string): string | undefined {
  return subPage(pathname)?.label ?? findNavItem(pathname)?.label;
}

/** The address of the listed page this one belongs to: always a page that exists. */
export function pageHrefFor(pathname: string): string | undefined {
  return subPage(pathname)?.href ?? findNavItem(pathname)?.href;
}

export interface Crumb {
  label: string;
  /** Missing for the group (it has no page of its own) and for the current page. */
  href?: string;
}

/** "People / Employees", or "Compliance / Sponsor compliance / Reminders". */
export function breadcrumbsFor(pathname: string): Crumb[] {
  const sub = subPage(pathname);
  if (sub) {
    const parent = NAV_ITEMS.find((candidate) => candidate.href === sub.parent);
    const group = NAV_GROUPS.find((g) => g.id === parent?.group)?.label ?? "";
    return [
      { label: group },
      ...(parent ? [{ label: parent.label, href: parent.href }] : []),
      { label: sub.label },
    ];
  }
  const item = findNavItem(pathname);
  if (!item) return [];
  const groupLabel = NAV_GROUPS.find((g) => g.id === item.group)?.label ?? "";
  const parent = item.parent
    ? NAV_ITEMS.find((candidate) => candidate.href === item.parent)
    : undefined;
  return [
    { label: groupLabel },
    ...(parent ? [{ label: parent.label, href: parent.href }] : []),
    { label: item.label },
  ];
}
