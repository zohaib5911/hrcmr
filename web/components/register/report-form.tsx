"use client";

import { type FormEvent, useState } from "react";

import { Turnstile, TURNSTILE_SITE_KEY } from "@/components/auth/turnstile";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";

/** "Report a problem with an entry". Anyone can send it; Turnstile and a rate limit guard it. */
export function ReportForm({ sponsorId }: { sponsorId?: string }) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!message.trim()) {
      return setProblem({ code: "VALIDATION_ERROR", message: "Describe the problem." } as Problem);
    }
    if (TURNSTILE_SITE_KEY && !token) {
      return setProblem({
        code: "TURNSTILE_FAILED",
        message: "Complete the check first.",
      } as Problem);
    }
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/public/register/reports", {
        body: {
          sponsor_id: sponsorId ?? null,
          email: email.trim() || null,
          message: message.trim(),
          turnstile_token: token ?? "no-turnstile",
        },
      }),
    );
    setBusy(false);
    setChallenge((n) => n + 1);
    setToken(null);
    if (result.ok) setSent(true);
    else setProblem(result.problem);
  }

  if (sent) {
    return (
      <p role="status" className="text-body text-label">
        Thank you. We have your report and will check the entry against the published register.
      </p>
    );
  }
  return (
    <form onSubmit={(e) => void submit(e)} className="flex max-w-xl flex-col gap-4" noValidate>
      {problem && <Alert tone="danger" title={problem.message} />}
      <fieldset disabled={busy} className="flex flex-col gap-4">
        <TextArea
          label="What is wrong with this entry?"
          required
          rows={4}
          maxLength={2000}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <TextField
          label="Your email (optional, if you want a reply)"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        {TURNSTILE_SITE_KEY && <Turnstile onToken={setToken} resetKey={challenge} />}
        <div>
          <Button type="submit" variant="filled" disabled={busy}>
            Send report
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
