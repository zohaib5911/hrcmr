"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { PLAN_REQUIRED_EVENT, type PlanRequiredDetail } from "@/lib/auth/request";

import { useCan } from "./session-context";

/** Opens when any request is refused for being on the free plan (HTTP 402), wherever it came from. */
export function UpgradeSheet() {
  const [message, setMessage] = useState<string | null>(null);
  const can = useCan();

  useEffect(() => {
    const open = (event: Event) =>
      setMessage((event as CustomEvent<PlanRequiredDetail>).detail.message);
    window.addEventListener(PLAN_REQUIRED_EVENT, open);
    return () => window.removeEventListener(PLAN_REQUIRED_EVENT, open);
  }, []);

  return (
    <Sheet open={message !== null} onOpenChange={(next) => !next && setMessage(null)}>
      <SheetContent title="Subscribe to carry on" description={message ?? ""}>
        <div className="flex flex-col gap-4 pt-2">
          {can("billing.manage") ? (
            <>
              <p className="text-body text-label-secondary">
                Pick a plan to add employees and use everything in your account. Your data stays
                exactly as it is.
              </p>
              <Button asChild size="lg" onClick={() => setMessage(null)}>
                <Link href="/company/billing">See the plans</Link>
              </Button>
            </>
          ) : (
            <p className="text-body text-label-secondary">
              Ask a Company Admin in your company to subscribe, and then try again.
            </p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
