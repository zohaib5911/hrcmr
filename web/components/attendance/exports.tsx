"use client";
import { useState } from "react";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { downloadBlob, type Status } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";
export function AttendanceExports({
  start,
  end,
  employeeId,
  status,
  absencesOnly = false,
}: {
  start: string;
  end: string;
  employeeId?: string;
  status?: Status;
  absencesOnly?: boolean;
}) {
  const can = useCan();
  const [busy, setBusy] = useState<"xlsx" | "pdf" | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  async function download(kind: "xlsx" | "pdf") {
    setBusy(kind);
    setProblem(null);
    const options = {
      params: {
        query: { start, end, employee_id: employeeId, status, absences_only: absencesOnly },
      },
      parseAs: "blob" as const,
    };
    const result = await attempt((c) =>
      kind === "xlsx"
        ? c.GET("/attendance/export.xlsx", options)
        : c.GET("/attendance/export.pdf", options),
    );
    setBusy(null);
    if (result.ok)
      downloadBlob(
        result.data,
        `${absencesOnly ? "absences" : "attendance"}-${start}-${end}.${kind}`,
      );
    else setProblem(result.problem);
  }
  if (!can("document.report.generate")) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="gray"
        loading={busy === "xlsx"}
        disabled={busy !== null}
        onClick={() => void download("xlsx")}
      >
        Export Excel
      </Button>
      <Button
        variant="gray"
        loading={busy === "pdf"}
        disabled={busy !== null}
        onClick={() => void download("pdf")}
      >
        Export PDF
      </Button>
      {problem && <Alert tone="danger" title={problem.message} />}
    </div>
  );
}
