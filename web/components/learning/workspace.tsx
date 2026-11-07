"use client";

import { GraduationCap } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { SearchField } from "@/components/ui/search-field";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { AssignWizard } from "./assign-wizard";
import { MyLearning } from "./my-learning";

type Summary = components["schemas"]["LearningSummaryOut"];
type Row = components["schemas"]["ReportRowOut"];
type Course = components["schemas"]["CourseCardOut"];
type Department = components["schemas"]["DepartmentOut"];
type Status = "not_started" | "in_progress" | "completed" | "overdue";
type View = "report" | "courses";

const STATUS_LABEL: Record<Status, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  overdue: "Overdue",
};

/** The learning page: people who may read every assignment see the report; others see their own. */
export function LearningWorkspace() {
  const can = useCan();
  if (!can("learning.assignment.read")) return <MyLearning />;
  return <LearningReport />;
}

function LearningReport() {
  const can = useCan();
  const [view, setView] = useState<View>("report");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [total, setTotal] = useState(0);
  const [courses, setCourses] = useState<Course[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [search, setSearch] = useState("");
  const [courseId, setCourseId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [status, setStatus] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [reload, setReload] = useState(0);
  const [wizardCourse, setWizardCourse] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardKey, setWizardKey] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    const filters = {
      course_id: courseId || undefined,
      department_id: departmentId || undefined,
      status: (status || undefined) as Status | undefined,
      search,
    };
    void Promise.all([
      attempt((c) => c.GET("/learning/summary")),
      attempt((c) =>
        c.GET("/learning/assignments", { params: { query: { ...filters, limit: 100 } } }),
      ),
      attempt((c) => c.GET("/learning/courses")),
      attempt((c) => c.GET("/departments")),
    ]).then(([sum, report, list, depts]) => {
      if (!active) return;
      const failed = [sum, report, list, depts].find((r) => !r.ok);
      if (failed && !failed.ok) {
        setProblem(failed.problem);
        return;
      }
      setProblem(null);
      if (sum.ok) setSummary(sum.data);
      if (report.ok) {
        setRows(report.data.items);
        setTotal(report.data.total);
      }
      if (list.ok) setCourses(list.data);
      if (depts.ok) setDepartments(depts.data);
    });
    return () => {
      active = false;
    };
  }, [search, courseId, departmentId, status, reload]);

  const columns: Column<Row>[] = [
    { id: "employee", header: "Person", primary: true, cell: (r) => r.employee_name },
    { id: "department", header: "Department", cell: (r) => r.department ?? "—" },
    { id: "course", header: "Course", cell: (r) => r.course_title },
    { id: "due", header: "Due", cell: (r) => formatUk(r.due_on) },
    {
      id: "status",
      header: "Status",
      cell: (r) => STATUS_LABEL[r.status as Status] ?? r.status,
    },
    {
      id: "score",
      header: "Check score",
      cell: (r) => (r.quiz_score === null ? "—" : `${r.quiz_score}%`),
    },
  ];

  async function exportXlsx() {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/learning/assignments.xlsx", {
        params: {
          query: {
            course_id: courseId || undefined,
            department_id: departmentId || undefined,
            status: (status || undefined) as Status | undefined,
            search,
          },
        },
        parseAs: "blob",
      }),
    );
    setBusy(false);
    if (!result.ok) {
      setProblem(result.problem);
      return;
    }
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "learning-report.xlsx";
    link.click();
    URL.revokeObjectURL(url);
  }

  function openWizard(course: string | null) {
    setWizardKey((n) => n + 1); // a fresh wizard each time it opens
    setWizardCourse(course);
    setWizardOpen(true);
  }

  return (
    <>
      <PageHeader
        title="Learning"
        description="Who has been assigned each course, what they have finished, and who is overdue."
        actions={
          <>
            <Button variant="gray" asChild>
              <Link href="/learning/my">My learning</Link>
            </Button>
            {can("learning.assignment.write") ? (
              <Button variant="filled" onClick={() => openWizard(null)}>
                Assign courses
              </Button>
            ) : null}
          </>
        }
      />
      {problem ? <Alert tone="danger" title={problem.message} className="mb-6" /> : null}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <KpiCard label="Assignments" value={summary?.assignments ?? 0} />
        <KpiCard label="Not started" value={summary?.not_started ?? 0} />
        <KpiCard label="In progress" value={summary?.in_progress ?? 0} />
        <KpiCard label="Completed" value={summary?.completed ?? 0} />
        <KpiCard label="Overdue" value={summary?.overdue ?? 0} />
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SegmentedControl<View>
          label="View"
          size="sm"
          value={view}
          onValueChange={setView}
          segments={[
            { value: "report", label: "Report" },
            { value: "courses", label: "Courses" },
          ]}
        />
      </div>

      {view === "report" ? (
        <>
          <div className="mb-4 grid gap-3 md:grid-cols-4">
            <SearchField
              label="Search people"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Select label="Course" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
              <option value="">All courses</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </Select>
            <Select
              label="Department"
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
            >
              <option value="">All departments</option>
              {departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </Select>
            <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any status</option>
              {(Object.keys(STATUS_LABEL) as Status[]).map((value) => (
                <option key={value} value={value}>
                  {STATUS_LABEL[value]}
                </option>
              ))}
            </Select>
          </div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-footnote text-label-secondary" role="status">
              {total} {total === 1 ? "assignment" : "assignments"}
            </p>
            <Button variant="gray" disabled={busy} onClick={exportXlsx}>
              Export to Excel
            </Button>
          </div>
          <DataTable
            caption="Learning assignments"
            columns={columns}
            rows={rows ?? []}
            getRowId={(r) => r.id}
            loading={rows === null && problem === null}
            empty={
              <EmptyState
                icon={GraduationCap}
                title="No courses assigned yet"
                description="Assign a course to people to see who has finished it and who is overdue."
              />
            }
          />
        </>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {courses.map((course) => (
            <article
              key={course.id}
              className="bg-elevated border-separator rounded-card flex flex-col gap-3 border p-4"
            >
              <h2 className="text-headline text-label">{course.title}</h2>
              <p className="text-callout text-label-secondary">{course.summary}</p>
              <p className="text-caption text-label-secondary">
                {course.duration_minutes} minutes · {course.section_count} sections ·{" "}
                {course.audience === "managers" ? "Managers" : "All staff"}
              </p>
              <p className="text-caption text-label-secondary">
                Source: {course.source_title}, reviewed {formatUk(course.content_reviewed_on)}
              </p>
              {can("learning.assignment.write") ? (
                <div>
                  <Button variant="gray" size="sm" onClick={() => openWizard(course.id)}>
                    Assign this course
                  </Button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}

      <AssignWizard
        key={wizardKey}
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        courses={courses}
        departments={departments}
        initialCourse={wizardCourse}
        onAssigned={() => setReload((n) => n + 1)}
      />
    </>
  );
}
