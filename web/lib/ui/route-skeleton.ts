/**
 * Which placeholder a signed-in route shows while it loads (design audit row B). The skeleton has
 * the shape of the page that is coming, so nothing jumps when the data arrives.
 */
export type RouteSkeleton = "card" | "form" | "calendar" | "list";

const CALENDAR = ["/rota", "/my-shifts", "/holiday-management"];
const FORM = [
  "/company",
  "/profile",
  "/clock",
  "/sponsorship-checker",
  "/employees/new",
  "/leave/settings",
  "/leave/year-end",
  "/rota/settings",
  "/attendance/import",
  "/attendance/bulk",
];
const CARD = ["/dashboard", "/reports", "/organogram", "/learning/my"];

const within = (path: string, base: string) => path === base || path.startsWith(`${base}/`);

export function routeSkeleton(pathname: string): RouteSkeleton {
  const path = pathname.split(/[?#]/)[0]?.replace(/\/+$/, "") || "/";
  // Most specific first: "/rota/settings" is a form, "/rota" a calendar.
  if (FORM.some((base) => within(path, base))) return "form";
  if (CALENDAR.some((base) => within(path, base))) return "calendar";
  if (CARD.some((base) => within(path, base))) return "card";
  if (path === "/sponsor-compliance") return "card";
  if (/^\/employees\/(?!archived(?:\/|$))[^/]+$/.test(path)) return "card";
  return "list";
}
