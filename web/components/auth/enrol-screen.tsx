"use client";

import { useRouter } from "next/navigation";

import { signOut } from "@/lib/auth/sign-out";

import { MfaEnrolment } from "./mfa-enrolment";

/** The forced set-up screen: finishing goes to the dashboard, and the person can sign out instead. */
export function EnrolScreen() {
  const router = useRouter();
  return (
    <MfaEnrolment
      onDone={() => {
        router.push("/dashboard");
        router.refresh();
      }}
      onSignOut={async () => {
        const outcome = await signOut();
        if (!outcome.ok) return outcome.problem;
        router.push("/login");
        router.refresh();
        return null;
      }}
    />
  );
}
