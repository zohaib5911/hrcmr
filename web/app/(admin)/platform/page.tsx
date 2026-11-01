import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Platform admin",
  robots: { index: false, follow: false },
};

export default function PlatformAdminPage() {
  return (
    <main>
      <h1>Platform admin</h1>
    </main>
  );
}
