import { serverApiBaseUrl } from "@/lib/api/client";
import type { components } from "@/lib/api/client";

export type Region = components["schemas"]["RegionOut"];
export type RegionList = components["schemas"]["RegionListOut"];
export type BulletinList = components["schemas"]["BulletinListOut"];
export type Bulletin = components["schemas"]["BulletinOut"];
export type Profile = components["schemas"]["ProfileOut"];

/** Shown on every register page (plan 8.x): the licence line, and what we are not. */
export const OGL_ATTRIBUTION =
  "Contains public sector information licensed under the Open Government Licence v3.0.";
export const INDEPENDENCE_STATEMENT =
  "We are independent of the Home Office. A sponsor licence does not mean the employer is hiring.";

export const CHANGE_LABELS: Record<string, string> = {
  added: "Added to the register",
  removed: "No longer listed",
  returned: "Returned to the register",
  route_added: "Route added",
  route_removed: "Route removed",
  rating_changed: "Rating changed",
};

/** Public data only: no cookies are sent. Returns null for a 404 so the page can call notFound(). */
export async function registerGet<T>(path: string, revalidate = 3600): Promise<T | null> {
  const response = await fetch(`${serverApiBaseUrl()}/public/register${path}`, {
    next: { revalidate },
  });
  if (response.status === 404 || response.status === 422) return null;
  if (!response.ok) throw new Error(`Register request failed: ${response.status}`);
  return (await response.json()) as T;
}

export function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "sponsor"
  );
}
