import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DossierEditor } from "@/components/compliance/dossier-editor";
import { ToastProvider } from "@/components/ui/toast";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = {
  title: "Dossier links",
  robots: { index: false, follow: false },
};

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const { data } = await client.GET("/admin/dossier-links");
  if (!data) notFound();
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-5xl">
        <ToastProvider>
          <DossierEditor links={data} />
        </ToastProvider>
      </div>
    </main>
  );
}
