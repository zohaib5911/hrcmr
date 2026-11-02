import type { Metadata } from "next";

import { SetupWizard } from "@/components/auth/setup-wizard";

export const metadata: Metadata = { title: "Create your company account" };

export default function SetupPage() {
  return <SetupWizard />;
}
