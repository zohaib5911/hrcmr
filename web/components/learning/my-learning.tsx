"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { SkeletonCard } from "@/components/ui/skeleton";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";
import { GraduationCap } from "lucide-react";

type Assignment = components["schemas"]["CourseAssignmentOut"];
type Course = components["schemas"]["CourseCardOut"];
type Tab = "assigned" | "all";

const STATUS_LABEL: Record<string, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  overdue: "Overdue",
};

/** Courses assigned to the signed-in person, and the whole library (plan 8.14). */
export function MyLearning() {
  const [tab, setTab] = useState<Tab>("assigned");
  const [mine, setMine] = useState<Assignment[] | null>(null);
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([
      attempt((c) => c.GET("/learning/assignments/own")),
      attempt((c) => c.GET("/learning/courses")),
    ]).then(([own, library]) => {
      if (!active) return;
      if (own.ok) setMine(own.data);
      else setProblem(own.problem);
      if (library.ok) setCourses(library.data);
      else setProblem(library.problem);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <PageHeader
        title="My learning"
        description="The courses you have been asked to take, and the rest of the library."
      />
      {problem ? <Alert tone="danger" title={problem.message} className="mb-6" /> : null}
      <div className="mb-6">
        <SegmentedControl<Tab>
          label="Show"
          size="sm"
          value={tab}
          onValueChange={setTab}
          segments={[
            { value: "assigned", label: "Assigned to me" },
            { value: "all", label: "All courses" },
          ]}
        />
      </div>
      {tab === "assigned" ? (
        mine === null ? (
          <SkeletonCard className="h-48" />
        ) : mine.length === 0 ? (
          <EmptyState
            icon={GraduationCap}
            title="Nothing assigned to you"
            description="When a course is assigned to you, it will appear here with its due date."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {mine.map((item) => (
              <li
                key={item.id}
                className="bg-elevated border-separator rounded-card flex flex-wrap items-center justify-between gap-3 border p-4"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="text-callout text-label font-semibold">{item.title}</span>
                  <span className="text-footnote text-label-secondary">
                    Due {formatUk(item.due_on)} · {STATUS_LABEL[item.status] ?? item.status}
                  </span>
                </div>
                <Button variant="filled" size="sm" asChild>
                  <Link href={`/learning/assignments/${item.id}`}>
                    {item.status === "completed" ? "Review course" : "Open course"}
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        )
      ) : courses === null ? (
        <SkeletonCard className="h-48" />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {courses.map((course) => (
            <li
              key={course.id}
              className="bg-elevated border-separator rounded-card flex flex-col gap-2 border p-4"
            >
              <span className="text-callout text-label font-semibold">{course.title}</span>
              <span className="text-body text-label-secondary">{course.summary}</span>
              <span className="text-caption text-label-secondary">
                {course.duration_minutes} minutes · {course.section_count} sections
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
