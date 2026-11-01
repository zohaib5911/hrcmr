"use client";

import { FileSearch, Users } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ProgressBar, ProgressRing } from "@/components/ui/progress";
import {
  Skeleton,
  SkeletonCard,
  SkeletonKpi,
  SkeletonPerson,
  SkeletonTable,
  SkeletonText,
} from "@/components/ui/skeleton";
import { Stepper } from "@/components/ui/stepper";

import { Demo, DocSection, State } from "./doc";

const STEPS = [
  { id: "company", label: "Your company", description: "Name and size" },
  { id: "people", label: "Your people", description: "Add the first few" },
  { id: "compliance", label: "Compliance", description: "Sponsor licence details" },
  { id: "done", label: "Done" },
] as const;

export function FeedbackSection() {
  const [dismissed, setDismissed] = useState(false);
  const [step, setStep] = useState(1);

  return (
    <DocSection
      id="feedback"
      title="Feedback"
      description="Banners, empty and error screens, loading placeholders and progress. An empty screen explains what will appear and offers the one action that makes it appear; an error says what happened and shows a request id."
    >
      <Demo
        title="Alerts"
        note="Warnings and errors interrupt screen readers; information waits its turn."
      >
        <div className="flex w-full max-w-3xl flex-col gap-3">
          <Alert tone="info" title="Your free plan includes 5 employees.">
            Upgrade any time to add more.
          </Alert>
          <Alert tone="success" title="Right to Work check saved." />
          <Alert
            tone="warning"
            title="2 checks expire in the next 28 days."
            action={
              <Button size="sm" variant="gray">
                Review them
              </Button>
            }
          >
            Grace Hopper (7 days) and Alan Turing (21 days).
          </Alert>
          <Alert tone="danger" title="Payment failed.">
            We will try again on 3 Nov 2026. Update your card to avoid losing access.
          </Alert>
          {dismissed ? null : (
            <Alert
              tone="info"
              title="You can dismiss this one."
              onDismiss={() => setDismissed(true)}
            />
          )}
        </div>
      </Demo>

      <Demo title="Empty and error screens">
        <div className="bg-grouped rounded-card w-full max-w-md">
          <EmptyState
            icon={Users}
            title="No employees yet"
            description="Add your first employee to start tracking their right to work and leave."
            action={<Button>Add an employee</Button>}
          />
        </div>
        <div className="bg-grouped rounded-card w-full max-w-md">
          <EmptyState
            icon={FileSearch}
            title="Nothing matches your search"
            description="Try a different name, or clear the filters."
            headingLevel={3}
          />
        </div>
        <div className="bg-grouped rounded-card w-full max-w-md">
          <ErrorState
            message="We could not load your employees. Check your connection and try again."
            requestId="req_01JF3K9X2M"
            onRetry={() => {}}
            headingLevel={3}
          />
        </div>
      </Demo>

      <Demo
        title="Loading placeholders"
        note="Each matches the footprint of what it stands for, so nothing moves when the data arrives. They stay still with reduced motion."
      >
        <State label="Text" className="w-64">
          <SkeletonText />
        </State>
        <State label="Person" className="w-64">
          <SkeletonPerson />
        </State>
        <State label="KPI card" className="w-56">
          <SkeletonKpi />
        </State>
        <State label="Card" className="w-72">
          <SkeletonCard />
        </State>
        <State label="Table" className="w-full max-w-2xl">
          <SkeletonTable rows={3} columns={4} />
        </State>
        <State label="Single block" className="w-40">
          <Skeleton className="h-10" />
        </State>
      </Demo>

      <Demo title="Progress">
        <State label="Bar, 60%" className="w-64">
          <ProgressBar label="Onboarding" value={60} />
        </State>
        <State label="Bar, no estimate" className="w-64">
          <ProgressBar label="Importing" />
        </State>
        <State label="Ring, 72%">
          <ProgressRing label="Learning complete" value={72}>
            72%
          </ProgressRing>
        </State>
        <State label="Ring, no estimate">
          <ProgressRing label="Working" />
        </State>
      </Demo>

      <Demo
        title="Stepper"
        note="Done, current and upcoming steps differ by icon and words, not colour alone."
      >
        <div className="flex w-full flex-col gap-6">
          <Stepper steps={STEPS} current={step} />
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="gray"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              Back
            </Button>
            <Button
              size="sm"
              disabled={step === STEPS.length - 1}
              onClick={() => setStep(step + 1)}
            >
              Next
            </Button>
          </div>
          <Stepper steps={STEPS} current={2} orientation="vertical" />
        </div>
      </Demo>
    </DocSection>
  );
}
