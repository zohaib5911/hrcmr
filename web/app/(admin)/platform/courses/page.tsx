import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CourseEditor } from "@/components/platform/course-editor";
import { serverApi } from "@/lib/auth/server";

export const metadata: Metadata = {
  title: "Courses",
  robots: { index: false, follow: false },
};

export default async function Page() {
  const client = await serverApi();
  if (!client) notFound();
  const { data } = await client.GET("/admin/courses");
  if (!data) notFound();
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <CourseEditor courses={data} />
      </div>
    </main>
  );
}
