import type { Metadata } from "next";

import { AuthCard } from "@/components/auth/auth-card";
import { EnrolScreen } from "@/components/auth/enrol-screen";

export const metadata: Metadata = { title: "Set up two-step verification" };

export default function EnrolPage() {
  return (
    <AuthCard
      title="Set up two-step verification"
      description="Your company asks everyone to use it. It keeps your account safe even if your password leaks."
    >
      <EnrolScreen />
    </AuthCard>
  );
}
