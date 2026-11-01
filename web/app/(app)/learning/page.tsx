import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Learning" };

export default function Page() {
  return <PlaceholderPage id="learning" />;
}
