import type { Metadata } from "next";
import { AttendanceImport } from "@/components/attendance/import-workspace";
export const metadata: Metadata = { title: "Import attendance" };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ preview?: string }>;
}) {
  const params = await searchParams;
  return <AttendanceImport previewId={params.preview} />;
}
