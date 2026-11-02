"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { attempt, type Problem } from "@/lib/auth/request";

import type { ShellCompany } from "./shell-types";

/** Shown when someone belongs to several companies and has not picked one for this visit. */
export function ChooseCompany({ companies }: { companies: readonly ShellCompany[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function choose(id: string) {
    setBusy(id);
    setProblem(null);
    const outcome = await attempt((client) =>
      client.POST("/auth/switch-company", { body: { company_id: id } }),
    );
    if (outcome.ok) {
      router.refresh();
      return;
    }
    setBusy(null);
    setProblem(outcome.problem);
  }

  return (
    <div className="bg-grouped flex min-h-dvh items-center justify-center p-4">
      <div className="w-full max-w-md">
        <AuthCard
          title="Which company?"
          description="You belong to more than one. Pick the one to work in."
        >
          {problem ? <Alert tone="danger" title={problem.message} /> : null}
          <ul className="flex flex-col gap-2">
            {companies.map((company) => (
              <li key={company.id}>
                <Button
                  variant="gray"
                  size="lg"
                  className="w-full justify-start"
                  loading={busy === company.id}
                  onClick={() => void choose(company.id)}
                >
                  {company.name}
                </Button>
              </li>
            ))}
          </ul>
        </AuthCard>
      </div>
    </div>
  );
}
