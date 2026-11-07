"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { attempt, type Problem } from "@/lib/auth/request";

/** Downloads the certificate for a completed course (plan 8.14). */
export function CertificateButton({ assignmentId }: { assignmentId: string }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function download() {
    setBusy(true);
    setProblem(null);
    const found = await attempt((c) =>
      c.GET("/learning/assignments/{assignment_id}/certificate", {
        params: { path: { assignment_id: assignmentId } },
      }),
    );
    if (!found.ok) {
      setBusy(false);
      setProblem(found.problem);
      return;
    }
    const pdf = await attempt((c) =>
      c.GET("/certificates/{certificate_id}.pdf", {
        params: { path: { certificate_id: found.data.id } },
        parseAs: "blob",
      }),
    );
    setBusy(false);
    if (!pdf.ok) {
      setProblem(pdf.problem);
      return;
    }
    const url = URL.createObjectURL(pdf.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `certificate-${found.data.reference}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button variant="gray" disabled={busy} onClick={download}>
          Download certificate
        </Button>
      </div>
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
    </div>
  );
}
