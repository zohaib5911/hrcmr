import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";

export const metadata: Metadata = { title: "Rota" };

export default function Page() {
  return <PlaceholderPage id="rota" />;
}
