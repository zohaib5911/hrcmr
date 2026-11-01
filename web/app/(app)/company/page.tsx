import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Company" };

export default function Page() {
  return <PlaceholderPage id="company" />;
}
