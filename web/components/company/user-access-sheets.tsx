"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { RadioCards } from "@/components/ui/radio-cards";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { ROLE_LABELS, type Role } from "@/lib/auth/roles";
import { attempt, type Problem } from "@/lib/auth/request";
import { fullName, ROLE_DESCRIPTIONS, type AccessUser } from "@/lib/company/access";

import { FormSheet } from "./form-sheet";

const ROLES = Object.keys(ROLE_LABELS) as Role[];
type Call<T> = Parameters<typeof attempt<T>>[0];

/** Runs a call, then toasts, refreshes the list and closes; a problem stays in the sheet. */
function useSubmit(success: string, onClose: () => void) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);
  const [password, setPassword] = useState("");
  async function run(call: Call<unknown>): Promise<Problem | null> {
    setBusy(true);
    setProblem(null);
    if (needsConfirmation) {
      const confirmed = await attempt((api) => api.POST("/auth/step-up", { body: { password } }));
      if (!confirmed.ok) {
        setBusy(false);
        setProblem(confirmed.problem);
        return confirmed.problem;
      }
      setPassword("");
    }
    const outcome = await attempt(call);
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: success, tone: "success" });
      router.refresh();
      onClose();
      return null;
    }
    if (outcome.problem.code === "STEP_UP_REQUIRED") setNeedsConfirmation(true);
    setProblem(outcome.problem);
    return outcome.problem;
  }
  const confirmation = needsConfirmation ? (
    <TextField
      label="Your password"
      type="password"
      autoComplete="current-password"
      value={password}
      onChange={(event) => setPassword(event.target.value)}
      required
    />
  ) : null;
  return { busy, problem, setProblem, run, confirmation };
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function InviteSheet({
  mayInviteAdmin,
  onClose,
}: {
  mayInviteAdmin: boolean;
  onClose: () => void;
}) {
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("employee");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { busy, problem, run, confirmation } = useSubmit("Invitation sent", onClose);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found: Record<string, string> = {};
    if (!first.trim()) found.first_name = "Enter their first name.";
    if (!last.trim()) found.last_name = "Enter their last name.";
    if (!EMAIL.test(email.trim())) found.email = "Enter an email address, like name@company.com.";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const failed = await run((api) =>
      api.POST("/users/invitations", {
        body: { first_name: first.trim(), last_name: last.trim(), email: email.trim(), role },
      }),
    );
    if (failed?.field) setErrors({ [failed.field]: failed.message });
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Invite user"
      description="They get a link by email, valid for 72 hours, to choose their own password."
      onSubmit={submit}
      busy={busy}
      problem={problem && !problem.field ? problem : null}
      saveLabel="Send invitation"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="First name"
          value={first}
          onChange={(e) => setFirst(e.target.value)}
          error={errors.first_name}
          autoComplete="off"
        />
        <TextField
          label="Last name"
          value={last}
          onChange={(e) => setLast(e.target.value)}
          error={errors.last_name}
          autoComplete="off"
        />
      </div>
      <TextField
        label="Work email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
        autoComplete="off"
      />
      <RadioCards
        legend="Role"
        value={role}
        onValueChange={(value) => setRole(value as Role)}
        options={ROLES.map((r) => ({
          value: r,
          title: ROLE_LABELS[r],
          description: ROLE_DESCRIPTIONS[r],
          disabled: r === "company_admin" && !mayInviteAdmin,
        }))}
      />
      {confirmation}
    </FormSheet>
  );
}

export function RoleSheet({
  user,
  mayAssignAdmin,
  onClose,
}: {
  user: AccessUser;
  mayAssignAdmin: boolean;
  onClose: () => void;
}) {
  const [role, setRole] = useState<Role>(user.role);
  const { busy, problem, run, confirmation } = useSubmit("Role changed", onClose);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (role === user.role) return onClose();
    await run((api) =>
      api.PATCH("/users/{membership_id}/role", {
        params: { path: { membership_id: user.id } },
        body: { role },
      }),
    );
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={`Change role for ${fullName(user)}`}
      description="The change applies the next time they open a page."
      onSubmit={submit}
      busy={busy}
      problem={problem}
    >
      <RadioCards
        legend="Role"
        value={role}
        onValueChange={(value) => setRole(value as Role)}
        options={ROLES.map((r) => ({
          value: r,
          title: ROLE_LABELS[r],
          description: ROLE_DESCRIPTIONS[r],
          disabled: r === "company_admin" && !mayAssignAdmin && user.role !== "company_admin",
        }))}
      />
      {confirmation}
    </FormSheet>
  );
}

type Confirmed = "suspend" | "reactivate" | "reset" | "cancel" | "resend";

const COPY: Record<Confirmed, { title: string; detail: string; label: string; done: string }> = {
  suspend: {
    title: "Suspend",
    detail:
      "They will not be able to use anything until you reactivate them. Their records stay as they are.",
    label: "Suspend",
    done: "Suspended",
  },
  reactivate: {
    title: "Reactivate",
    detail: "They will be able to sign in and use the company again, with the same role.",
    label: "Reactivate",
    done: "Reactivated",
  },
  reset: {
    title: "Reset two-step verification for",
    detail:
      "They are signed out everywhere and set up two-step verification again the next time they sign in. Confirm your password to do this.",
    label: "Reset two-step",
    done: "Two-step verification reset",
  },
  resend: {
    title: "Resend invitation for",
    detail: "Send a fresh invitation link by email.",
    label: "Resend invitation",
    done: "Invitation sent",
  },
  cancel: {
    title: "Cancel the invitation for",
    detail: "The link in their email stops working. You can invite them again later.",
    label: "Cancel invitation",
    done: "Invitation cancelled",
  },
};

/** One question and one button: suspend, reactivate, cancel an invitation, or reset two-step. */
export function ConfirmSheet({
  action,
  user,
  onClose,
}: {
  action: Confirmed;
  user: AccessUser;
  onClose: () => void;
}) {
  const copy = COPY[action];
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | undefined>();
  const { busy, problem, run, confirmation } = useSubmit(copy.done, onClose);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const id = { path: { membership_id: user.id } };
    if (action === "reset") {
      if (!password) return setError("Enter your password.");
      setError(undefined);
      const confirmed = await attempt((api) => api.POST("/auth/step-up", { body: { password } }));
      if (!confirmed.ok) return setError(confirmed.problem.message);
      await run((api) => api.POST("/users/{membership_id}/reset-two-step", { params: id }));
    } else if (action === "resend") {
      await run((api) =>
        api.POST("/users/invitations/{invitation_id}/resend", {
          params: { path: { invitation_id: user.id } },
        }),
      );
    } else if (action === "cancel") {
      await run((api) =>
        api.DELETE("/users/invitations/{invitation_id}", {
          params: { path: { invitation_id: user.id } },
        }),
      );
    } else {
      await run((api) =>
        api.POST(
          action === "suspend"
            ? "/users/{membership_id}/suspend"
            : "/users/{membership_id}/reactivate",
          { params: id },
        ),
      );
    }
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={`${copy.title} ${fullName(user)}?`}
      description={copy.detail}
      onSubmit={submit}
      busy={busy}
      problem={problem}
      saveLabel={copy.label}
    >
      {action === "reset" ? (
        <TextField
          label="Your password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={error}
          autoComplete="current-password"
        />
      ) : null}
      {confirmation}
    </FormSheet>
  );
}
