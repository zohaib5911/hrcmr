"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { attempt } from "@/lib/auth/request";

import { useMe } from "./session-context";

const TIME = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/London",
});

/**
 * Support mode (T17.3): a platform admin is looking at this company. The bar is on every page of
 * the tenant app while it lasts, says whether changes are on and when it ends, and ends it. The
 * colour is the platform bar's fixed red, so white text keeps at least 7:1 contrast in both themes.
 */
export function SupportBanner() {
  const me = useMe();
  const router = useRouter();
  const [leaving, setLeaving] = useState(false);
  const support = me?.support;
  if (!support) return null;

  const leave = () => {
    setLeaving(true);
    void attempt((client) => client.DELETE("/auth/support-session")).then(() => {
      router.push("/dashboard");
      router.refresh();
    });
  };

  return (
    <div
      role="status"
      data-testid="support-banner"
      className="sticky top-0 z-[80] flex flex-wrap items-center justify-center gap-x-4 gap-y-2 bg-[#b00010] px-4 py-2 text-sm text-white"
    >
      <p>
        <span className="font-semibold">Support mode</span>: you are viewing {support.company_name}{" "}
        as a platform admin (ticket {support.ticket_ref}).{" "}
        {support.write_enabled ? "Changes are on." : "Read-only."} Ends at{" "}
        {TIME.format(new Date(support.expires_at))}.
      </p>
      <button
        type="button"
        onClick={leave}
        disabled={leaving}
        className="rounded-control border border-white px-3 py-1 font-medium hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:opacity-70"
      >
        {leaving ? "Ending…" : "End support mode"}
      </button>
    </div>
  );
}
