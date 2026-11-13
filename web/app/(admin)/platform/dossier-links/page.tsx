import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DossierEditor } from "@/components/compliance/dossier-editor";
import { ToastProvider } from "@/components/ui/toast";
import { serverApi } from "@/lib/auth/server";
import { AdminPage } from "@/components/platform/admin-page";

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
    <AdminPage>
      <ToastProvider>
        <DossierEditor links={data} />
      </ToastProvider>
    </AdminPage>
  );
}
