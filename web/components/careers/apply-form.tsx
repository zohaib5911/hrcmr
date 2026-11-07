"use client";

import { useState, type FormEvent } from "react";

import { Turnstile, TURNSTILE_SITE_KEY } from "@/components/auth/turnstile";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";

/**
 * The apply form on a public posting. The server decides whether the bot check passes: it verifies
 * the Turnstile token when a secret is configured, and accepts the placeholder when none is.
 */
export function ApplyForm({ company, posting }: { company: string; posting: string }) {
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [bring, setBring] = useState("");
  const [consent, setConsent] = useState(false);
  const [cv, setCv] = useState<File | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!consent)
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Tick to agree that we may store your details to consider you.",
        field: "consent",
      } as Problem);
    if (TURNSTILE_SITE_KEY && !token)
      return setProblem({
        code: "TURNSTILE_FAILED",
        message: "Complete the check first.",
      } as Problem);
    setBusy(true);
    const body = new FormData();
    body.append("first_name", first.trim());
    body.append("last_name", last.trim());
    body.append("email", email.trim());
    if (phone.trim()) body.append("phone", phone.trim());
    if (bring.trim()) body.append("what_you_bring", bring.trim());
    body.append("consent", "true");
    body.append("turnstile_token", token ?? "no-turnstile");
    if (cv) body.append("cv", cv);
    const result = await attempt((c) =>
      c.POST("/public/postings/{company_slug}/{posting_slug}/apply", {
        params: { path: { company_slug: company, posting_slug: posting } },
        body: {
          first_name: "",
          last_name: "",
          email: "",
          consent: true,
          turnstile_token: "",
        },
        bodySerializer: () => body,
      }),
    );
    setBusy(false);
    setChallenge((n) => n + 1);
    setToken(null);
    if (result.ok) setSent(email.trim());
    else setProblem(result.problem);
  }

  const cvItems: UploadItem[] = cv
    ? [{ id: cv.name, name: cv.name, size: cv.size, status: "safe" }]
    : [];

  if (sent) {
    return (
      <section aria-live="polite" className="border-separator rounded-xl border p-5">
        <h2 className="text-headline text-label font-semibold">Thank you for applying</h2>
        <p className="text-callout text-label-secondary mt-2">
          We have your application and sent a confirmation to {sent}.
        </p>
      </section>
    );
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4" noValidate>
      <h2 className="text-title-3 text-label font-semibold">Apply for this role</h2>
      {problem && <Alert tone="danger" title={problem.message} />}
      <fieldset disabled={busy} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="First name"
            required
            maxLength={100}
            value={first}
            onChange={(e) => setFirst(e.target.value)}
            autoComplete="given-name"
          />
          <TextField
            label="Last name"
            required
            maxLength={100}
            value={last}
            onChange={(e) => setLast(e.target.value)}
            autoComplete="family-name"
          />
        </div>
        <TextField
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <TextField
          label="Phone (optional)"
          maxLength={40}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          autoComplete="tel"
        />
        <TextArea
          label="What you would bring (optional)"
          rows={5}
          maxLength={3000}
          value={bring}
          onChange={(e) => setBring(e.target.value)}
        />
        <FileDrop
          label="CV (optional)"
          description="PDF or Word, up to 10 MB. We check it for viruses."
          accept={[".pdf", ".doc", ".docx"]}
          maxBytes={10 * 1024 * 1024}
          items={cvItems}
          onFiles={(files) => setCv(files[0] ?? null)}
          onRemove={() => setCv(null)}
          disabled={busy}
        />
        <Checkbox
          label="I agree that you may store my details to consider my application."
          checked={consent}
          onCheckedChange={(value) => setConsent(value === true)}
        />
        {TURNSTILE_SITE_KEY && <Turnstile onToken={setToken} resetKey={challenge} />}
        <div>
          <Button type="submit" variant="filled" disabled={busy}>
            Send application
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
