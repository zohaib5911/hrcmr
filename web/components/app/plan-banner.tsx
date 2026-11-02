"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isWriteScreen } from "@/lib/auth/shell-session";

import { useCan, useMe } from "./session-context";

const DISMISSED = "brand.planBanner.dismissed";
const CHANGED = "brand:planBannerChanged";

function readDismissed(): boolean {
  try {
    return window.sessionStorage.getItem(DISMISSED) === "1";
  } catch {
    return false;
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGED, onChange);
  return () => window.removeEventListener(CHANGED, onChange);
}

function dismiss() {
  try {
    window.sessionStorage.setItem(DISMISSED, "1");
  } catch {
    // The banner just comes back on the next page.
  }
  window.dispatchEvent(new Event(CHANGED));
}

/**
 * "You're on the free plan" (plan 8.1), for people who can subscribe. It can be put away for the
 * rest of the visit, except on a screen where someone is filling something in.
 */
export function PlanBanner() {
  const me = useMe();
  const can = useCan();
  const pathname = usePathname();
  const dismissed = useSyncExternalStore(subscribe, readDismissed, () => false);

  const active = me?.companies.find((item) => item.company_id === me.active_company_id);
  if (!active || active.plan !== "free" || !can("billing.manage")) return null;
  const pinned = isWriteScreen(pathname);
  if (dismissed && !pinned) return null;

  return (
    <div className="mb-4">
      <Alert
        tone="info"
        title="You're on the free plan"
        action={
          <Button asChild size="sm" variant="gray">
            <Link href="/company/billing">Subscribe</Link>
          </Button>
        }
        {...(pinned ? {} : { onDismiss: dismiss })}
      >
        Subscribe to add employees.
      </Alert>
    </div>
  );
}
