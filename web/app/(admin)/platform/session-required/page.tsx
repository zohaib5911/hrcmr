import { PageHeader } from "@/components/app/page-header";
import { AdminPage } from "@/components/platform/admin-page";
import { buttonVariants } from "@/components/ui/button";
import { refusalMessage } from "@/lib/platform/session";

/** Why the platform session did not start, in plain words (T17.1, owner answer 5). */
export default async function SessionRequiredPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code } = await searchParams;
  return (
    <AdminPage width="narrow" className="pt-10">
      <PageHeader title="Platform session not started" />
      <p className="text-body text-label">{refusalMessage(code ?? "")}</p>
      <a href="/session" className={buttonVariants({ className: "mt-6 self-start" })}>
        Try again
      </a>
    </AdminPage>
  );
}
