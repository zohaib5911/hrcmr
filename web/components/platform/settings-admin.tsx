"use client";

import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import { Select } from "@/components/ui/select";
import type { components } from "@/lib/api/client";
import { attempt, type Outcome } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Schemas = components["schemas"];
export interface SettingsData {
  terms: Schemas["TermsVersionsOut"] | null;
  flags: Schemas["FeatureFlagsOut"] | null;
  announcements: Schemas["AnnouncementsOut"] | null;
  owner: boolean;
}

export function SettingsAdmin({
  terms: initialTerms,
  flags: initialFlags,
  announcements: initialAnnouncements,
  owner,
}: SettingsData) {
  const [terms, setTerms] = useState(initialTerms);
  const [flags, setFlags] = useState(initialFlags);
  const [announcements, setAnnouncements] = useState(initialAnnouncements);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const [version, setVersion] = useState("");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [region, setRegion] = useState("uk");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const allowed = reason.trim().length >= 5 && !busy;
  const datesValid =
    Number.isFinite(Date.parse(start)) &&
    Number.isFinite(Date.parse(end)) &&
    Date.parse(end) > Date.parse(start);

  async function run<T>(request: () => Promise<Outcome<T>>, apply: (data: T) => void) {
    if (!allowed) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request();
      if (!result.ok) {
        if (result.problem.code === "UNAUTHENTICATED" || result.problem.code === "FORBIDDEN") {
          window.location.replace("/session?next=%2Fsettings");
          return;
        }
        setError(result.problem.message);
      } else {
        apply(result.data);
        setNotice("Settings saved.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Publish terms, control features and schedule regional announcements."
      />
      <TextField
        label="Reason for change"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        hint="At least 5 characters; saved in the audit log."
      />
      {error && (
        <Alert tone="danger" title="Could not save settings">
          {error}
        </Alert>
      )}
      {notice && (
        <Alert tone="success" title={notice}>
          The change is in the audit log.
        </Alert>
      )}
      <div className="mt-6 grid gap-6">
        <Card>
          <CardHeader title="Terms versions" headingLevel={2} />
          <CardBody className="grid gap-4">
            {terms === null ? (
              <Alert tone="danger" title="Could not load terms versions">
                Reload to try again.
              </Alert>
            ) : terms.items.length === 0 ? (
              <p>No terms versions yet.</p>
            ) : (
              <ul>
                {terms.items.map((t) => (
                  <li key={t.id} className="break-words">
                    {t.version} · {formatUk(t.published_at.slice(0, 10))}
                    {t.current ? " · Current" : ""} · {t.url}
                  </li>
                ))}
              </ul>
            )}
            {owner && (
              <>
                <TextField
                  label="Version"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  maxLength={40}
                />
                <TextField
                  label="Terms URL"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  maxLength={300}
                />
                <ConfirmDialog
                  trigger={
                    <Button
                      disabled={
                        !allowed ||
                        !/^[A-Za-z0-9._-]{1,40}$/.test(version) ||
                        !/^(https:\/\/|\/)/.test(url)
                      }
                    >
                      Publish new version
                    </Button>
                  }
                  title="Publish terms?"
                  description="Every user must accept again before using the product. Confirm that these terms are ready to publish."
                  confirmLabel="Publish terms"
                  onConfirm={() =>
                    run(
                      () =>
                        attempt((c) =>
                          c.POST("/platform/terms-versions", {
                            body: { version, url, reason: reason.trim() },
                          }),
                        ),
                      (t) => {
                        setTerms({
                          items: [
                            t,
                            ...(terms?.items ?? []).map((old) => ({ ...old, current: false })),
                          ],
                          total: (terms?.total ?? 0) + 1,
                        });
                      },
                    )
                  }
                />
              </>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Feature flags" headingLevel={2} />
          <CardBody className="grid gap-4">
            {flags === null ? (
              <Alert tone="danger" title="Could not load feature flags">
                Reload to try again.
              </Alert>
            ) : flags.items.length === 0 ? (
              <p>No feature flags yet.</p>
            ) : (
              flags.items.map((flag) => (
                <Toggle
                  key={flag.key}
                  label={flag.key}
                  description={flag.description}
                  checked={flag.enabled}
                  disabled={!allowed}
                  onCheckedChange={(enabled) =>
                    void run(
                      () =>
                        attempt((c) =>
                          c.PUT("/platform/feature-flags/{key}", {
                            params: { path: { key: flag.key } },
                            body: { enabled, reason: reason.trim() },
                          }),
                        ),
                      (updated) =>
                        setFlags(
                          (current) =>
                            current && {
                              ...current,
                              items: current.items.map((f) =>
                                f.key === updated.key ? updated : f,
                              ),
                            },
                        ),
                    )
                  }
                />
              ))
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Announcements" headingLevel={2} />
          <CardBody className="grid gap-4">
            {announcements === null ? (
              <Alert tone="danger" title="Could not load announcements">
                Reload to try again.
              </Alert>
            ) : announcements.items.length === 0 ? (
              <p>No announcements yet.</p>
            ) : (
              <ul className="grid gap-3">
                {announcements.items.map((a) => (
                  <li key={a.id} className="grid gap-2 break-words">
                    <p>
                      {a.title} · {a.region.toUpperCase()} · {a.status}
                    </p>
                    <p>{a.body}</p>
                    <p>
                      {formatUk(a.starts_at.slice(0, 10))} – {formatUk(a.ends_at.slice(0, 10))}
                    </p>
                    {a.status !== "ended" && (
                      <ConfirmDialog
                        trigger={
                          <Button variant="gray" disabled={!allowed}>
                            End now
                          </Button>
                        }
                        title="End announcement?"
                        description="The banner will stop appearing in the tenant app."
                        confirmLabel="End announcement"
                        onConfirm={() =>
                          run(
                            () =>
                              attempt((c) =>
                                c.POST("/platform/announcements/{announcement_id}/end", {
                                  params: { path: { announcement_id: a.id } },
                                  body: { reason: reason.trim() },
                                }),
                              ),
                            (updated) =>
                              setAnnouncements(
                                (current) =>
                                  current && {
                                    ...current,
                                    items: current.items.map((row) =>
                                      row.id === updated.id ? updated : row,
                                    ),
                                  },
                              ),
                          )
                        }
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
            <form
              className="grid gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!datesValid || !title.trim() || !body.trim()) return;
                void run(
                  () =>
                    attempt((c) =>
                      c.POST("/platform/announcements", {
                        body: {
                          title: title.trim(),
                          body: body.trim(),
                          region,
                          starts_at: new Date(start).toISOString(),
                          ends_at: new Date(end).toISOString(),
                          reason: reason.trim(),
                        },
                      }),
                    ),
                  (a) => {
                    setAnnouncements((current) => ({
                      items: [a, ...(current?.items ?? [])],
                      total: (current?.total ?? 0) + 1,
                    }));
                    setTitle("");
                    setBody("");
                  },
                );
              }}
            >
              <TextField
                label="Announcement title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={120}
                required
              />
              <TextField
                label="Message"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={500}
                required
              />
              <Select label="Region" value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="uk">UK</option>
                <option value="us">US</option>
                <option value="au">Australia</option>
              </Select>
              <TextField
                label="Starts at (local time)"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
              <TextField
                label="Ends at (local time)"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
                hint="Must be after the start."
              />
              <Button
                type="submit"
                loading={busy}
                disabled={!allowed || !datesValid || !title.trim() || !body.trim()}
              >
                Create announcement
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
