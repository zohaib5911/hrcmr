import type { Metadata } from "next";

import { AcceptInviteForm } from "@/components/auth/accept-invite-form";
import { AuthCard } from "@/components/auth/auth-card";

export const metadata: Metadata = { title: "Accept your invitation" };

export default async function AcceptInvitePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  return (
    <AuthCard title="Accept your invitation" description="Set up your account to join your team.">
      <AcceptInviteForm token={token} />
    </AuthCard>
  );
}
