import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Org chart" };

export default function Page() {
  return <PlaceholderPage id="organogram" />;
}
