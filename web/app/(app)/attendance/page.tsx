import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Attendance" };

export default function Page() {
  return <PlaceholderPage id="attendance" />;
}
