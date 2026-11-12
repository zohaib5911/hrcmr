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
    <main className="mx-auto max-w-xl px-4 py-16">
      <SessionStart next={safeNextPath(next ?? null)} />
    </main>
  );
}
