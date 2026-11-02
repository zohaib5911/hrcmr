"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";

import { FormSheet } from "./form-sheet";

type Call<T> = Parameters<typeof attempt<T>>[0];

/**
 * The sheet shared by every pay-settings form: run the call, then toast, refresh and close; or keep
 * the problem so the field it names can show it.
 */
export function PaySheet<T>({
  noun,
  title,
  existing,
  validate,
  save,
  remove,
  archiveDetail,
  onClose,
  children,
}: {
  noun: string;
  title: string;
  existing: boolean;
  /** A message for a field, or null when everything can be sent. */
  validate: () => Record<string, string> | null;
  save: Call<T>;
  remove?: Call<void>;
  archiveDetail: string;
  onClose: () => void;
  children: (errors: Record<string, string>) => ReactNode;
}) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validate();
    setProblem(null);
    setErrors(found ?? {});
    if (found) return;
    setBusy(true);
    const outcome = await attempt(save);
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: `${noun} ${existing ? "saved" : "added"}`, tone: "success" });
      router.refresh();
      onClose();
    } else if (outcome.problem.field) {
      setErrors({ [outcome.problem.field]: outcome.problem.message });
    } else setProblem(outcome.problem);
  }

  async function archive() {
    if (!remove) return;
    const outcome = await attempt(remove);
    if (outcome.ok) {
      toast.show({ title: `${noun} archived`, tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={title}
      onSubmit={submit}
      busy={busy}
      problem={problem}
      {...(existing && remove
        ? {
            archive: {
              label: "Archive",
              question: `Archive this ${noun.toLowerCase()}?`,
              detail: archiveDetail,
              onConfirm: archive,
            },
          }
        : {})}
    >
      {children(errors)}
    </FormSheet>
  );
}
