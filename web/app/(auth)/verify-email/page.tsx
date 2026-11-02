import type { Metadata } from "next";

import { AuthCard } from "@/components/auth/auth-card";
import { VerifyEmail } from "@/components/auth/verify-email";

export const metadata: Metadata = { title: "Confirm your email address" };

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  return (
    <AuthCard title="Confirm your email address">
      <VerifyEmail token={token} />
    </AuthCard>
  );
}
