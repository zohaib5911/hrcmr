import type { Metadata } from "next";

import { AuthCard } from "@/components/auth/auth-card";
import { MfaForm } from "@/components/auth/mfa-form";

export const metadata: Metadata = { title: "Two-step verification" };

export default function MfaPage() {
  return (
    <AuthCard
      title="Two-step verification"
      description="Enter the code from your authenticator app to finish signing in."
    >
      <MfaForm />
    </AuthCard>
  );
}
