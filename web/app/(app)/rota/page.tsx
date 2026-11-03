import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Rota" };

export default function Page() {
  return (
    <>
      <PlaceholderPage id="rota" />
      <div className="mt-5">
        <Button asChild variant="gray">
          <Link href="/rota/settings">Rota settings</Link>
        </Button>
      </div>
    </>
  );
}
