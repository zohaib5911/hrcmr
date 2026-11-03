"use client";

import { Briefcase, FileText, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { SponsorDocumentsTab } from "@/components/employees/sponsor-documents-tab";
import { RTWTab } from "@/components/employees/rtw-tab";
import { RTWChip } from "@/components/employees/rtw-chip";
import { ProfilePhoto } from "@/components/employees/profile-photo";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { Icon } from "@/components/ui/icon";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import { EmploymentTab, type EmploymentData } from "@/components/employees/employment-tab";
import { DocumentsTab, PrintRecord } from "@/components/employees/documents-tab";
import {
  LeaveTab,
  AttendanceTab,
  LearningTab,
  ActivityTab,
} from "@/components/employees/related-tabs";
import { PersonalTab } from "@/components/employees/personal-tab";
import { StatusChip } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { Toggle } from "@/components/ui/toggle";
import { attempt, type Problem } from "@/lib/auth/request";
import { STATUS_LABEL } from "@/lib/employees/list";
import {
  joinedLine,
  shortDate,
  MOVES,
  type EmployeeProfile,
  type EmployeeStatus,
} from "@/lib/employees/profile";
import type { PersonalTab as PersonalData } from "@/lib/employees/personal";

const TONE = {
  active: "success",
  on_leave: "info",
  leaver: "neutral",
  archived: "neutral",
} as const;

const today = () => new Date().toISOString().slice(0, 10);

/** `/employees/{id}` (plan 8.3): the header and the Overview tab. The other tabs arrive with their tasks. */
export function ProfilePage({
  profile,
  personal,
  employment,
  initialTab = "overview",
}: {
  profile: EmployeeProfile;
  personal: PersonalData;
  employment: EmploymentData;
  initialTab?: string;
}) {
  const can = useCan();
  const router = useRouter();
  const mayReadRtw = can("employee.rtw.read", "employee.rtw.read_own");
  const allowedTabs = [
    "overview",
    "personal",
    "employment",
    "leave",
    "attendance",
    "documents",
    "learning",
    ...(mayReadRtw ? ["rtw", "sponsor"] : []),
    ...(can("compliance.audit.read") ? ["activity"] : []),
  ];
  const [tab, setTab] = useState(allowedTabs.includes(initialTab) ? initialTab : "overview");
  const name = `${profile.first_name} ${profile.last_name}`;
  return (
    <>
      <PageHeader
        title={name}
        description={`${profile.employee_number} · ${joinedLine(profile.hire_date, today())}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <PrintRecord id={profile.id} />
            <RTWChip status={profile.rtw_status} />
            {mayReadRtw && profile.rtw_status !== "verified" && (
              <Button variant="gray" size="sm" onClick={() => setTab("rtw")}>
                Resolve Right to Work
              </Button>
            )}
            <StatusChip tone={TONE[profile.status]}>{STATUS_LABEL[profile.status]}</StatusChip>
          </div>
        }
      />
      <div className="mb-6 flex items-center gap-3">
        <ProfilePhoto id={profile.id} name={name} hasPhoto={profile.has_photo} />
        <div className="min-w-0">
          <p className="text-callout text-label truncate">{profile.email}</p>
          {profile.phone ? (
            <p className="text-callout text-label-secondary">{profile.phone}</p>
          ) : null}
        </div>
      </div>
      {mayReadRtw && profile.rtw_status === "not_recorded" && (
        <div className="mb-6">
          <Alert tone="warning" title="No Right to Work check recorded">
            Open Right to Work to review or record a check.
          </Alert>
        </div>
      )}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Employee record">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="personal">Personal</TabsTrigger>
          <TabsTrigger value="employment">Employment</TabsTrigger>
          <TabsTrigger value="leave">Leave</TabsTrigger>
          <TabsTrigger value="attendance">Attendance</TabsTrigger>
          {mayReadRtw && <TabsTrigger value="rtw">Right to Work</TabsTrigger>}
          {mayReadRtw && <TabsTrigger value="sponsor">Sponsor compliance</TabsTrigger>}
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="learning">Learning</TabsTrigger>
          {can("compliance.audit.read") && <TabsTrigger value="activity">Activity</TabsTrigger>}
        </TabsList>
        <TabsContent value="overview" className="pt-6">
          <Overview profile={profile} />
        </TabsContent>
        <TabsContent value="personal" className="pt-6">
          <PersonalTab id={profile.id} personal={personal} />
        </TabsContent>
        <TabsContent value="employment" className="pt-6">
          <EmploymentTab id={profile.id} employment={employment} />
        </TabsContent>
        {mayReadRtw && (
          <TabsContent value="rtw" className="pt-6">
            <RTWTab id={profile.id} onChanged={() => router.refresh()} />
          </TabsContent>
        )}
        {mayReadRtw && (
          <TabsContent value="sponsor" className="pt-6">
            <SponsorDocumentsTab id={profile.id} onChanged={() => router.refresh()} />
          </TabsContent>
        )}
        <TabsContent value="documents" className="pt-6">
          <DocumentsTab id={profile.id} />
        </TabsContent>
        <TabsContent value="leave" className="pt-6">
          <LeaveTab id={profile.id} />
        </TabsContent>
        <TabsContent value="attendance" className="pt-6">
          <AttendanceTab id={profile.id} />
        </TabsContent>
        <TabsContent value="learning" className="pt-6">
          <LearningTab id={profile.id} />
        </TabsContent>
        {can("compliance.audit.read") && (
          <TabsContent value="activity" className="pt-6">
            <ActivityTab id={profile.id} />
          </TabsContent>
        )}
      </Tabs>
    </>
  );
}

function Overview({ profile }: { profile: EmployeeProfile }) {
  return (
    <div className="flex flex-col gap-8">
      <section aria-label="Summary" className="grid gap-4 sm:grid-cols-2">
        <SummaryCard icon={ShieldCheck} label="Right to Work">
          <div>
            <RTWChip status={profile.rtw_status} />
          </div>
          {profile.rtw_follow_up_due_on && (
            <p className="text-callout text-label-secondary">
              Follow-up due {shortDate(profile.rtw_follow_up_due_on)}
            </p>
          )}
        </SummaryCard>
        <SummaryCard icon={Briefcase} label="Employment">
          {profile.designation || profile.department || profile.employment_type ? (
            <>
              <p className="text-headline text-label">
                {profile.designation || profile.employment_type?.replaceAll("_", " ")}
              </p>
              <p className="text-callout text-label-secondary">
                {profile.department ?? "No department"}
              </p>
            </>
          ) : (
            <p className="text-callout text-label-secondary">No role recorded yet.</p>
          )}
        </SummaryCard>
        <SummaryCard icon={FileText} label="Documents">
          <p className="text-headline text-label tabular-nums">
            {profile.documents} {profile.documents === 1 ? "document" : "documents"}
          </p>
        </SummaryCard>
      </section>
      <AccessAndStatus profile={profile} />
      <OptOut profile={profile} />
      <PermanentDelete profile={profile} />
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  children,
}: {
  icon: typeof Briefcase;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-elevated rounded-card shadow-e1 flex flex-col gap-2 p-5">
      <p className="text-footnote text-label-secondary flex items-center gap-2 font-medium">
        <Icon icon={icon} size={16} />
        {label}
      </p>
      {children}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h2 className="text-caption text-label-secondary px-4 font-medium tracking-wider uppercase">
        {title}
      </h2>
      <div className="bg-elevated rounded-card shadow-e1 flex flex-col gap-4 p-5">{children}</div>
    </section>
  );
}

function AccessAndStatus({ profile }: { profile: EmployeeProfile }) {
  const router = useRouter();
  const toast = useToast();
  const can = useCan();
  const mayEdit = can("employee.profile.write");
  const [leaveDate, setLeaveDate] = useState<string | null>(profile.leave_date);
  const [problem, setProblem] = useState<Problem | null>(null);
  const asksDate = profile.status !== "archived";

  async function move(to: EmployeeStatus) {
    setProblem(null);
    const outcome = await attempt((api) =>
      api.POST("/employees/{employee_id}/status", {
        params: { path: { employee_id: profile.id } },
        body: { status: to, leave_date: to === "leaver" || to === "on_leave" ? leaveDate : null },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: `Now ${STATUS_LABEL[to].toLowerCase()}`, tone: "success" });
      router.refresh();
    } else setProblem(outcome.problem);
  }

  return (
    <Panel title="Access and status">
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <p className="text-callout text-label-secondary">
        Currently{" "}
        <strong className="text-label font-semibold">
          {STATUS_LABEL[profile.status].toLowerCase()}
        </strong>
        {profile.leave_date ? `, from ${profile.leave_date}` : ""}.
      </p>
      {mayEdit ? (
        <>
          {asksDate ? (
            <DatePicker
              label="Date (optional)"
              name="leave_date"
              value={leaveDate}
              onChange={setLeaveDate}
              hint="Used when setting someone to on leave or as a leaver."
              containerClassName="max-w-xs"
            />
          ) : null}
          <div className="flex flex-wrap gap-2">
            {MOVES[profile.status].map((m) => (
              <InlineConfirm
                key={m.to}
                label={m.label}
                prompt={m.prompt}
                confirmLabel={m.label}
                destructive={m.to === "archived" || m.to === "leaver"}
                onConfirm={() => move(m.to)}
              />
            ))}
          </div>
        </>
      ) : null}
    </Panel>
  );
}

function OptOut({ profile }: { profile: EmployeeProfile }) {
  const router = useRouter();
  const toast = useToast();
  const can = useCan();
  const mayEdit = can("employee.profile.write");
  const input = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function set(optedOut: boolean) {
    setProblem(null);
    const outcome = await attempt((api) =>
      api.PUT("/employees/{employee_id}/opt-out-48h", {
        params: { path: { employee_id: profile.id } },
        body: { opted_out: optedOut },
      }),
    );
    if (outcome.ok) router.refresh();
    else setProblem(outcome.problem);
  }

  async function upload(file: File) {
    setBusy(true);
    setProblem(null);
    const body = new FormData();
    body.append("file", file);
    const outcome = await attempt((api) =>
      api.POST("/employees/{employee_id}/opt-out-48h/agreement", {
        params: { path: { employee_id: profile.id } },
        body: { file: "" },
        bodySerializer: () => body,
      }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: "Agreement filed", tone: "success" });
      router.refresh();
    } else setProblem(outcome.problem);
  }

  return (
    <Panel title="Working time">
      {problem ? <Alert tone="danger" title={problem.message} /> : null}
      <Toggle
        label="Opted out of the 48-hour week"
        description={
          profile.has_opt_out_agreement
            ? "The signed agreement is on file. The rota stops warning about long weeks."
            : "Upload the signed agreement first. Then you can turn this on."
        }
        checked={profile.opted_out_48h_week}
        disabled={!mayEdit || (!profile.has_opt_out_agreement && !profile.opted_out_48h_week)}
        onCheckedChange={(checked) => void set(checked)}
      />
      {mayEdit ? (
        <div>
          <input
            ref={input}
            type="file"
            accept="application/pdf,image/jpeg,image/png"
            className="sr-only"
            aria-label="Signed opt-out agreement"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
              event.target.value = "";
            }}
          />
          <Button variant="gray" size="sm" loading={busy} onClick={() => input.current?.click()}>
            {profile.has_opt_out_agreement ? "Upload a newer agreement" : "Upload signed agreement"}
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}

function PermanentDelete({ profile }: { profile: EmployeeProfile }) {
  const router = useRouter();
  const toast = useToast();
  const can = useCan();
  const [typed, setTyped] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const name = `${profile.first_name} ${profile.last_name}`;
  if (!can("employee.profile.delete")) return null;

  async function remove() {
    setProblem(null);
    setBusy(true);
    const outcome = await attempt((api) =>
      api.DELETE("/employees/{employee_id}", {
        params: { path: { employee_id: profile.id } },
        body: { confirm_name: typed },
      }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: "Record deleted", tone: "success" });
      router.push("/employees");
      router.refresh();
    } else setProblem(outcome.problem);
  }

  return (
    <details className="bg-elevated rounded-card shadow-e1 group p-5">
      <summary className="text-callout text-label cursor-pointer font-medium">
        Advanced: permanently delete this record
      </summary>
      <div className="mt-4 flex flex-col gap-3">
        {profile.can_delete ? (
          <>
            <p className="text-callout text-label-secondary">
              This removes the record for good and cannot be undone. Use it only for a record made
              by mistake. Type <strong className="text-label font-semibold">{name}</strong> to
              confirm.
            </p>
            {problem ? <Alert tone="danger" title={problem.message} /> : null}
            <TextField
              label="Full name"
              name="confirm_name"
              autoComplete="off"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              containerClassName="max-w-sm"
            />
            <div>
              <Button
                variant="destructive"
                loading={busy}
                aria-disabled={typed.trim().toLowerCase() !== name.toLowerCase() || undefined}
                onClick={() => typed.trim().toLowerCase() === name.toLowerCase() && void remove()}
              >
                Delete permanently
              </Button>
            </div>
          </>
        ) : (
          <Alert tone="info" title="This record cannot be deleted">
            {profile.delete_blocker}
          </Alert>
        )}
      </div>
    </details>
  );
}
