import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { RegisterAdmin } from "@/components/platform/register-admin";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";

export const metadata: Metadata = {
  title: "Sponsor register",
  robots: { index: false, follow: false },
};
export default async function Page() {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/register"));
  const result = await api.GET("/platform/register/status").catch(() => null);
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <RegisterAdmin status={result ? dataOrSessionRedirect(result, "/register") : null} />
      </div>
    </main>
  );
}
