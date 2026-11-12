import type { ApiClient } from "@/lib/api/client";

/** True only when the API says the caller is a platform owner; any failure hides owner-only buttons (the API still checks). */
export async function isPlatformOwner(api: ApiClient): Promise<boolean> {
  try {
    const result = await (
      api as unknown as {
        GET: (p: string) => Promise<{ data?: { owner?: boolean } }>;
      }
    ).GET("/platform/context");
    return result.data?.owner === true;
  } catch {
    return false;
  }
}
