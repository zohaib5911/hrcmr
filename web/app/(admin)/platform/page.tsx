import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Platform admin",
  robots: { index: false, follow: false },
};

export default function PlatformAdminPage() {
  return (
    <main>
      <h1>Platform admin</h1>
      <Link href="/dossier-links">Dossier links</Link>
    </main>
  );
}
