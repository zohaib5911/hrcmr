import type { Metadata } from "next";

import { PageHeader } from "@/components/app/page-header";
import { AdminPage } from "@/components/platform/admin-page";
import { TemplatesTable } from "@/components/platform/templates-table";
import { loadTemplates } from "@/lib/templates/manifest";

export const metadata: Metadata = {
  title: "Templates",
  robots: { index: false, follow: false },
};

export default function Page() {
  const templates = loadTemplates();
  return (
    <AdminPage>
      <PageHeader
        title="Templates"
        description="Read-only list from the repository manifest. Changes go through a pull request. Each template needs a human review before it is published."
      />
      <TemplatesTable templates={templates} />
    </AdminPage>
  );
}
