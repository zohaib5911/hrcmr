import type { ApiClient } from "@/lib/api/client";
import { dataOrSessionRedirect } from "@/lib/platform/guard";

type ContextResult = { data?: { owner?: boolean }; response: { status: number } };

/**
 * Reads the platform context (an authenticated, audited platform read). A 401/403 sends the browser
 * to the start page and back to `path`; any other failure hides owner-only buttons (the API still checks).
 * Returns whether the caller is a platform owner.
 */
export async function isPlatformOwner(api: ApiClient, path: string): Promise<boolean> {
  const result: ContextResult | null = await (
    api as unknown as { GET: (p: string) => Promise<ContextResult> }
  )
    .GET("/platform/context")
    .catch(() => null);
  if (!result) return false;
  return dataOrSessionRedirect(result, path)?.owner === true;
}
