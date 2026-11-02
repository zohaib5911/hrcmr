"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useCan } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";

export function ProfilePhoto({
  id,
  name,
  hasPhoto,
}: {
  id: string;
  name: string;
  hasPhoto: boolean;
}) {
  const can = useCan();
  const router = useRouter();
  const toast = useToast();
  const [version, setVersion] = useState(0);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<File | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const visible = hasPhoto || version > 0;
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setProblem(null);
    if (!pending) return setError("Choose a JPG or PNG photo.");
    const body = new FormData();
    body.append("file", pending);
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/employees/{employee_id}/photo", {
        params: { path: { employee_id: id } },
        body: { file: "" },
        bodySerializer: () => body,
      }),
    );
    setBusy(false);
    if (result.ok) {
      setVersion((v) => v + 1);
      setOpen(false);
      setPending(null);
      toast.show({ title: "Photo saved", tone: "success" });
      router.refresh();
    } else setProblem(result.problem);
  }
  const items: UploadItem[] = pending
    ? [{ id: pending.name, name: pending.name, size: pending.size, status: "safe" }]
    : [];
  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <Avatar
        name={name}
        size="lg"
        decorative
        src={
          visible
            ? (process.env.NEXT_PUBLIC_API_URL ?? "") + "/employees/" + id + "/photo?v=" + version
            : undefined
        }
      />
      {can("employee.profile.write") && (
        <Button
          variant="plain"
          size="sm"
          onClick={() => {
            setPending(null);
            setProblem(null);
            setError(undefined);
            setOpen(true);
          }}
        >
          {visible ? "Change photo" : "Add photo"}
        </Button>
      )}
      {open && (
        <FormSheet
          open
          onOpenChange={setOpen}
          title="Employee photo"
          description="A JPG or PNG up to 5 MB, checked for viruses when you save."
          onSubmit={save}
          busy={busy}
          problem={problem}
        >
          <FileDrop
            label="Photo"
            accept={[".jpg", ".jpeg", ".png"]}
            maxBytes={5 * 1024 * 1024}
            items={items}
            onFiles={(files) => setPending(files[0] ?? null)}
            onRemove={() => setPending(null)}
            disabled={busy}
          />
          {error && <Alert tone="danger" title={error} />}
        </FormSheet>
      )}
    </div>
  );
}
