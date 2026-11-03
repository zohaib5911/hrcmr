"use client";

import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { attempt, type Problem } from "@/lib/auth/request";
import { DOSSIER_SECTIONS, type Dossier } from "@/lib/compliance/hub";
import { shortDate } from "@/lib/employees/profile";

export function DossierPage({ dossier }: { dossier: Dossier }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  async function download() {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/compliance/rtw-checklist.pdf", { parseAs: "blob" }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "right-to-work-checklist.pdf";
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <PageHeader
        title="Sponsor Management Dossier"
        description="Official guidance for holding a licence, checking Right to Work and using the sponsorship management system."
        actions={
          <Button loading={busy} onClick={() => void download()}>
            Download RTW checklist
          </Button>
        }
      />
      {problem && <Alert tone="danger" title={problem.message} />}
      <div className="grid gap-6 lg:grid-cols-3">
        {DOSSIER_SECTIONS.map(([section, title]) => (
          <Card key={section}>
            <CardHeader title={title} headingLevel={2} />
            <CardBody>
              <ul className="flex flex-col gap-5">
                {dossier.links
                  .filter((link) => link.section === section)
                  .map((link) => (
                    <li key={link.id}>
                      <a
                        href={link.url}
                        className="text-body text-accent-text underline"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {link.title}
                        <span className="sr-only"> (opens in a new tab)</span>
                      </a>
                      <p className="text-caption text-label-secondary mt-1">
                        GOV.UK · checked {shortDate(link.checked_on)}
                      </p>
                    </li>
                  ))}
              </ul>
              {!dossier.links.some((link) => link.section === section) && (
                <p className="text-body text-label-secondary">No links currently published.</p>
              )}
            </CardBody>
          </Card>
        ))}
      </div>
    </>
  );
}
