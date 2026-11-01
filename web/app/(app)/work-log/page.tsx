import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Work log" };

export default function Page() {
  return <PlaceholderPage id="work-log" />;
}
