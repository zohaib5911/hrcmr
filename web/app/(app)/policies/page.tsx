import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Policies" };

export default function Page() {
  return <PlaceholderPage id="policies" />;
}
