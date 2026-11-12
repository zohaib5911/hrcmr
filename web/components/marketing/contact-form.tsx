"use client";

import { useState, type FormEvent } from "react";

import { Turnstile, TURNSTILE_SITE_KEY } from "@/components/auth/turnstile";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Topic = components["schemas"]["ContactFormIn"]["topic"];

export const TOPICS: readonly [Topic, string][] = [
  ["sponsor_compliance", "Sponsor licence compliance"],
  ["simple_hr", "Simple HR for my business"],
  ["pricing_billing", "Pricing or billing"],
  ["setup_help", "Help setting up"],
  ["partnership", "Partnership or reseller"],
  ["other", "Something else"],
  ["data_protection", "Data protection complaint"],
];

/** The public contact form. The server checks Turnstile when a secret is set and accepts the placeholder otherwise. */
export function ContactForm() {
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [topic, setTopic] = useState<Topic>("sponsor_compliance");
  const [message, setMessage] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [challenge, setChallenge] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!name.trim() || !email.trim() || !message.trim()) {
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter your name, email and a message.",
      } as Problem);
    }
    if (TURNSTILE_SITE_KEY && !token) {
      return setProblem({
        code: "TURNSTILE_FAILED",
        message: "Complete the check first.",
      } as Problem);
    }
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/public/contact", {
        body: {
          name: name.trim(),
          company: company.trim() || null,
          email: email.trim(),
          topic,
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
      <section aria-live="polite" className="border-separator rounded-xl border p-6">
        <h2 className="text-title-3 text-label font-semibold">Message sent</h2>
        <p className="text-body text-label-secondary mt-2">
          Thank you. We reply within one working day.
        </p>
      </section>
    );
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4" noValidate>
      {problem && <Alert tone="danger" title={problem.message} />}
      <fieldset disabled={busy} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Name"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
          <TextField
            label="Company (optional)"
            maxLength={160}
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            autoComplete="organization"
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
        <Select label="Topic" value={topic} onChange={(e) => setTopic(e.target.value as Topic)}>
          {TOPICS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <TextArea
          label="Message"
          required
          rows={6}
          maxLength={5000}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        {TURNSTILE_SITE_KEY && <Turnstile onToken={setToken} resetKey={challenge} />}
        <div>
          <Button type="submit" variant="filled" disabled={busy}>
            Send message
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
