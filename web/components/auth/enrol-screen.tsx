"use client";

import { useRouter } from "next/navigation";

import { attempt } from "@/lib/auth/request";

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
      onSignOut={() => {
        void attempt((client) => client.POST("/auth/logout")).then(() => router.push("/login"));
      }}
    />
  );
}
