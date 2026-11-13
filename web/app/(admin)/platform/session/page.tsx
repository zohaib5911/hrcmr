import { AdminPage } from "@/components/platform/admin-page";
import { SessionStart } from "@/components/platform/session-start";
import { safeNextPath } from "@/lib/platform/session";

/**
 * Starts the platform session from the browser (T17.1; C3.1.2), then goes on to `next`. The page is
 * served without the platform cookie, so the admin frame lets it through (layout.tsx).
 */
export default async function SessionPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  return (
    <AdminPage width="narrow" className="pt-10">
      <SessionStart next={safeNextPath(next ?? null)} />
    </AdminPage>
  );
}
