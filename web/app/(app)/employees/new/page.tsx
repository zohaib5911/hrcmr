import type { Metadata } from "next";

import { NewEmployeePage } from "@/components/employees/new-employee-page";

export const metadata: Metadata = { title: "New employee" };

export default function Page() {
  return <NewEmployeePage />;
}
