"use client";

import { type FormEvent, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Check = components["schemas"]["CertificateCheckOut"];

/** The public check: anyone can enter a certificate reference. Only four facts are ever shown. */
export function VerifyCertificate({ initialRef }: { initialRef: string }) {
  const [reference, setReference] = useState(initialRef);
  const [busy, setBusy] = useState(false);
  const [found, setFound] = useState<Check | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function check(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFound(null);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/public/certificates/verify", { params: { query: { ref: reference.trim() } } }),
    );
    setBusy(false);
    if (result.ok) setFound(result.data);
    else setProblem(result.problem);
  }

  return (
    <main className="mx-auto flex w-full max-w-xl flex-col gap-6 p-5 sm:p-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-large-title text-label">Check a certificate</h1>
        <p className="text-body text-label-secondary">
          Enter the reference printed on a certificate to see who it was issued to and which course
          they completed.
        </p>
      </header>
      <form className="flex flex-col gap-4" onSubmit={check}>
        <TextField
          label="Certificate reference"
          autoComplete="off"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
        />
        <div>
          <Button type="submit" variant="filled" disabled={busy || reference.trim() === ""}>
            Check certificate
          </Button>
        </div>
      </form>
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      {found ? (
        <section
          aria-label="Certificate details"
          className="bg-elevated border-separator rounded-card flex flex-col gap-3 border p-5"
        >
          <p className="text-footnote text-label-secondary">Valid certificate</p>
          <p className="text-title-3 text-label">{found.holder_name}</p>
          <p className="text-callout text-label">{found.course_title}</p>
          <p className="text-callout text-label-secondary">
            Completed on {formatUk(found.completed_on)}
          </p>
        </section>
      ) : null}
    </main>
  );
}
