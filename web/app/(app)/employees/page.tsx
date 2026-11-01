import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Employees" };

export default function Page() {
  return <PlaceholderPage id="employees" />;
}
