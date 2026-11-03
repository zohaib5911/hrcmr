import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/app/placeholder-page";
import { ClockLink } from "@/components/attendance/clock";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return (
    <>
      <PlaceholderPage id="dashboard" />
      <div className="mt-5">
        <ClockLink />
      </div>
    </>
  );
}
