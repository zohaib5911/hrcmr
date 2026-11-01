import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Sponsored employees" };

export default function Page() {
  return <PlaceholderPage id="migrant-employees" />;
}
