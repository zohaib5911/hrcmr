import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "My profile" };

export default function Page() {
  return <PlaceholderPage id="profile" />;
}
