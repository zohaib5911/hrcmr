import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <PlaceholderPage id="dashboard" />;
}
