"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type State = components["schemas"]["ClockState"];
type Location = components["schemas"]["ClockLocation"];
type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export function ClockLink() {
  const can = useCan();
  return can("attendance.record.write", "attendance.record.write_own") ? (
    <Button asChild variant="gray">
      <Link href="/clock">Clock in or out</Link>
    </Button>
  ) : null;
}

function location(): Promise<Location> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Location is unavailable. Turn off location sharing to continue."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        resolve({
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy: coords.accuracy,
        }),
      () =>
        reject(
          new Error(
            "Location was not shared. Try again, or turn off location sharing to continue.",
          ),
        ),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 0 },
    );
  });
}

export function AttendanceClock() {
  const can = useCan();
  const [state, setState] = useState<State | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [breakMinutes, setBreakMinutes] = useState("0");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/attendance/clock")).then((result) => {
      if (!active) return;
      if (result.ok) setState(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [version]);
  useEffect(() => {
    const ready = (event: Event) => {
      event.preventDefault();
      setInstall(event as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", ready);
    if ("serviceWorker" in navigator)
      void navigator.serviceWorker.register("/clock/sw.js", { scope: "/clock" }).catch(() => {});
    return () => window.removeEventListener("beforeinstallprompt", ready);
  }, []);
  async function record() {
    if (!state || busy) return;
    setBusy(true);
    setProblem(null);
    setMessage(null);
    let geo: Location | undefined;
    if (consent && state.location_enabled) {
      try {
        geo = await location();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Location is unavailable.");
        setBusy(false);
        return;
      }
    }
    const shared = { note: note.trim() || undefined, location: geo, location_consent: !!geo };
    if (state.active) {
      const result = await attempt((c) =>
        c.POST("/attendance/clock-out", {
          body: {
            ...shared,
            record_id: state.active!.id,
            unpaid_break_minutes: Number(breakMinutes),
          },
        }),
      );
      if (result.ok) {
        setState({ ...state, active: null });
        setNote("");
        setConsent(false);
        setBreakMinutes("0");
        setMessage(`Clocked out · ${result.data.hours ?? "0"} hours recorded`);
      } else {
        setProblem(result.problem);
        setVersion((v) => v + 1);
      }
    } else {
      const result = await attempt((c) => c.POST("/attendance/clock-in", { body: shared }));
      if (result.ok) {
        setState(result.data);
        setNote("");
        setConsent(false);
        setMessage("Clocked in");
      } else {
        setProblem(result.problem);
        setVersion((v) => v + 1);
      }
    }
    setBusy(false);
  }
  return (
    <>
      <PageHeader
        title="Clock in or out"
        description="Record your working time using your company's time zone."
      />
      <div className="flex max-w-xl flex-col gap-5">
        {problem && <Alert tone="danger" title={problem.message} />}
        {message && <Alert title={message} />}
        {!state ? (
          !problem && <p role="status">Loading clock…</p>
        ) : !state.employee_name ? (
          <Alert title="Your account needs a linked employee record. Ask your administrator to link it." />
        ) : (
          <>
            <p className="text-headline text-label">{state.employee_name}</p>
            <p className="text-callout text-label-secondary">
              {state.timezone} · Clock times are recorded when you submit. Stay online to save.
            </p>
            {state.active ? (
              <Alert
                title={`Clocked in at ${state.active.clock_in_local} on ${formatUk(state.active.date)}`}
              />
            ) : (
              <p>You are clocked out.</p>
            )}
            {can("attendance.record.write", "attendance.record.write_own") && (
              <form
                className="flex flex-col gap-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void record();
                }}
              >
                <TextArea
                  label="Clock note (optional)"
                  value={note}
                  maxLength={2000}
                  disabled={busy}
                  onChange={(event) => setNote(event.target.value)}
                />
                {state.active && (
                  <TextField
                    label="Unpaid break (minutes)"
                    type="number"
                    min={0}
                    max={1440}
                    required
                    value={breakMinutes}
                    disabled={busy}
                    onChange={(event) => setBreakMinutes(event.target.value)}
                  />
                )}
                {state.location_enabled && (
                  <Toggle
                    label="Share my location for this action"
                    description="Optional. Your coordinates and accuracy will be saved with this clock entry. You can clock without sharing."
                    checked={consent}
                    disabled={busy}
                    onCheckedChange={setConsent}
                  />
                )}
                <div>
                  <Button type="submit" loading={busy}>
                    {state.active ? "Clock out" : "Clock in"}
                  </Button>
                </div>
              </form>
            )}
          </>
        )}
        <div className="border-separator rounded-card border p-4">
          {install ? (
            <Button
              variant="gray"
              onClick={async () => {
                await install.prompt();
                await install.userChoice;
                setInstall(null);
              }}
            >
              Install clock app
            </Button>
          ) : (
            <p className="text-callout text-label-secondary">
              For quick access, use your browser&apos;s Install app or Add to Home Screen option.
            </p>
          )}
        </div>
        <Link className="text-accent-text underline" href="/attendance">
          View attendance
        </Link>
      </div>
    </>
  );
}
