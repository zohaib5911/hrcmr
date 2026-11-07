import type { Metadata } from "next";

import { CoursePlayer } from "@/components/learning/player";

export const metadata: Metadata = { title: "Course" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CoursePlayer assignmentId={id} />;
}
