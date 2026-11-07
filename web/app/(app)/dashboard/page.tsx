import type { Metadata } from "next";

import { ClockLink } from "@/components/attendance/clock";
import { DashboardWorkspace } from "@/components/dashboard/workspace";
import { MyShiftsLink } from "@/components/rota/my-shifts";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return (
    <>
      <DashboardWorkspace />
      <div className="mt-5 flex flex-wrap gap-3">
        <ClockLink />
        <MyShiftsLink />
      </div>
    </>
  );
}
