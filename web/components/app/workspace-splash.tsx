import { brand } from "@brand";

import { Spinner } from "@/components/ui/spinner";

/**
 * "Loading your workspace…" (plan T1.3): shown while the signed-in app loads, before the first
 * screen. Calm and centred; the spinner pulses instead of turning when motion is reduced.
 */
export function WorkspaceSplash() {
  return (
    <div role="status" className="bg-canvas fixed inset-0 z-[80] grid place-items-center">
      <div className="flex flex-col items-center gap-4">
        <p className="text-title-2 text-label font-semibold">{brand.name}</p>
        <Spinner className="text-label-secondary size-6" />
        <p className="text-callout text-label-secondary">Loading your workspace…</p>
      </div>
    </div>
  );
}
