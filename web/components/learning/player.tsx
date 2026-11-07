"use client";

import { useEffect, useId, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SkeletonCard } from "@/components/ui/skeleton";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Detail = components["schemas"]["AssignmentDetailOut"];
type Assignment = components["schemas"]["CourseAssignmentOut"];
type Result = components["schemas"]["QuizResultOut"];

const STATUS_LABEL: Record<string, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  overdue: "Overdue",
};

/**
 * One course for one learner: section by section, the check, and completion. Progress is saved as
 * each section is opened, so a reload comes back to the same section; completion needs a passing
 * check (the server refuses it otherwise).
 */
export function CoursePlayer({ assignmentId }: { assignmentId: string }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loadError, setLoadError] = useState<Problem | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [section, setSection] = useState(0);
  const [mode, setMode] = useState<"read" | "check">("read");
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const headingId = useId();

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/learning/assignments/{assignment_id}", {
        params: { path: { assignment_id: assignmentId } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) {
        setDetail(result.data);
        setSection(result.data.assignment.section);
        setAnswers(result.data.course.questions.map(() => null));
      } else {
        setLoadError(result.problem);
      }
    });
    return () => {
      active = false;
    };
  }, [assignmentId]);

  if (loadError) return <Alert tone="danger" title={loadError.message} />;
  if (!detail) return <SkeletonCard className="h-80" />;

  const { assignment: a, course } = detail;
  const passed = a.passed || (result !== null && result.best_score >= course.pass_mark);
  const current = course.sections[section];

  async function openSection(next: number) {
    setBusy(true);
    setProblem(null);
    const saved = await attempt((c) =>
      c.POST("/learning/assignments/{assignment_id}/progress", {
        params: { path: { assignment_id: assignmentId } },
        body: { section: next },
      }),
    );
    setBusy(false);
    if (!saved.ok) {
      setProblem(saved.problem);
      return;
    }
    setSection(next);
    setMode("read");
    setDetail((d) => (d ? { ...d, assignment: saved.data } : d));
  }

  async function submitCheck() {
    setBusy(true);
    setProblem(null);
    const answered = answers.map((answer) => answer ?? 0);
    const scored = await attempt((c) =>
      c.POST("/learning/assignments/{assignment_id}/quiz", {
        params: { path: { assignment_id: assignmentId } },
        body: { answers: answered },
      }),
    );
    setBusy(false);
    if (!scored.ok) {
      setProblem(scored.problem);
      return;
    }
    setResult(scored.data);
    setDetail((d) =>
      d ? { ...d, assignment: { ...d.assignment, quiz_score: scored.data.best_score } } : d,
    );
  }

  async function complete() {
    setBusy(true);
    setProblem(null);
    const done = await attempt((c) =>
      c.POST("/learning/assignments/{assignment_id}/complete", {
        params: { path: { assignment_id: assignmentId } },
      }),
    );
    setBusy(false);
    if (!done.ok) {
      setProblem(done.problem);
      return;
    }
    setDetail((d) => (d ? { ...d, assignment: done.data } : d));
  }

  function retry() {
    setAnswers(course.questions.map(() => null));
    setResult(null);
  }

  return (
    <>
      <PageHeader
        title={course.title}
        description={`${a.duration_minutes} minutes · Due ${formatUk(a.due_on)} · ${STATUS_LABEL[a.status] ?? a.status}`}
      />
      {problem ? <Alert tone="danger" title={problem.message} className="mb-6" /> : null}
      <div className="grid gap-8 lg:grid-cols-[16rem_1fr]">
        <nav aria-label="Course sections" className="flex flex-col gap-1">
          {course.sections.map((item, index) => (
            <button
              key={item.title}
              type="button"
              disabled={busy}
              aria-current={mode === "read" && index === section ? "step" : undefined}
              onClick={() => void openSection(index)}
              className={
                mode === "read" && index === section
                  ? "bg-accent-tint text-label rounded-control px-3 py-2 text-left font-semibold"
                  : "text-label-secondary hover:bg-fill-secondary rounded-control px-3 py-2 text-left"
              }
            >
              {index + 1}. {item.title}
            </button>
          ))}
          <button
            type="button"
            disabled={busy}
            aria-current={mode === "check" ? "step" : undefined}
            onClick={() => setMode("check")}
            className={
              mode === "check"
                ? "bg-accent-tint text-label rounded-control px-3 py-2 text-left font-semibold"
                : "text-label-secondary hover:bg-fill-secondary rounded-control px-3 py-2 text-left"
            }
          >
            Check ({course.questions.length} questions)
          </button>
        </nav>

        <section aria-labelledby={headingId} className="flex min-w-0 flex-col gap-6">
          {mode === "read" ? (
            <>
              <div className="flex flex-col gap-3">
                <h2 id={headingId} className="text-title-3 text-label">
                  {current?.title}
                </h2>
                {(current?.body ?? "").split("\n").map((paragraph, index) => (
                  <p key={index} className="text-body text-label leading-relaxed">
                    {paragraph}
                  </p>
                ))}
                {current && current.key_points.length > 0 ? (
                  <ul className="text-body text-label list-disc space-y-1 pl-6">
                    {current.key_points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Button
                  variant="gray"
                  disabled={busy || section === 0}
                  onClick={() => void openSection(section - 1)}
                >
                  Previous section
                </Button>
                {section < course.sections.length - 1 ? (
                  <Button
                    variant="filled"
                    disabled={busy}
                    onClick={() => void openSection(section + 1)}
                  >
                    Next section
                  </Button>
                ) : (
                  <Button variant="filled" disabled={busy} onClick={() => setMode("check")}>
                    Go to the check
                  </Button>
                )}
              </div>
            </>
          ) : (
            <CheckPanel
              course={course}
              answers={answers}
              setAnswers={setAnswers}
              result={result}
              busy={busy}
              passed={passed}
              completedAt={a.completed_at}
              assignment={a}
              onSubmit={submitCheck}
              onComplete={complete}
              onRetry={retry}
              onBack={() => setMode("read")}
            />
          )}

          <aside
            aria-label="Where this comes from"
            className="bg-elevated border-separator rounded-card flex flex-col gap-1 border p-4"
          >
            <p className="text-footnote text-label-secondary">Where this comes from</p>
            <p className="text-callout text-label">
              {course.source_title}, {course.source_publisher}. Source last updated{" "}
              {formatUk(course.source_updated_on)}; content reviewed{" "}
              {formatUk(course.content_reviewed_on)}.
            </p>
            <a
              href={course.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-callout text-accent"
            >
              Read the source (opens in a new tab)
            </a>
            {course.licence_note ? (
              <p className="text-caption text-label-secondary">{course.licence_note}</p>
            ) : null}
          </aside>
        </section>
      </div>
    </>
  );
}

function CheckPanel({
  course,
  answers,
  setAnswers,
  result,
  busy,
  passed,
  completedAt,
  assignment,
  onSubmit,
  onComplete,
  onRetry,
  onBack,
}: {
  course: Detail["course"];
  answers: (number | null)[];
  setAnswers: (next: (number | null)[]) => void;
  result: Result | null;
  busy: boolean;
  passed: boolean;
  completedAt: Assignment["completed_at"];
  assignment: Assignment;
  onSubmit: () => void;
  onComplete: () => void;
  onRetry: () => void;
  onBack: () => void;
}) {
  const everyAnswered = answers.every((answer) => answer !== null);
  const completed = assignment.status === "completed";
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-title-3 text-label">Check your understanding</h2>
        <p className="text-body text-label-secondary">
          Answer every question. You need {course.pass_mark}% to complete this course.
        </p>
      </div>
      {course.questions.map((question, index) => (
        <fieldset key={question.prompt} className="flex flex-col gap-2">
          <legend className="text-callout text-label mb-2 font-semibold">
            {index + 1}. {question.prompt}
          </legend>
          {question.options.map((option, choice) => {
            const name = `question-${index}`;
            const graded = result?.results[index];
            return (
              <label key={option} className="text-body text-label flex items-center gap-3">
                <input
                  type="radio"
                  name={name}
                  value={choice}
                  checked={answers[index] === choice}
                  disabled={busy || result !== null}
                  onChange={() => {
                    const next = [...answers];
                    next[index] = choice;
                    setAnswers(next);
                  }}
                  className="size-4"
                />
                <span>{option}</span>
                {graded && graded.correct_option === choice ? (
                  <span className="text-caption text-success">Correct answer</span>
                ) : null}
              </label>
            );
          })}
          {result ? (
            <p className="text-footnote text-label-secondary">
              {result.results[index]?.correct ? "Right. " : "Not quite. "}
              {result.results[index]?.explanation}
            </p>
          ) : null}
        </fieldset>
      ))}
      {result === null ? (
        <div className="flex justify-end">
          <Button variant="filled" disabled={busy || !everyAnswered} onClick={onSubmit}>
            Submit the check
          </Button>
        </div>
      ) : (
        <div className="bg-elevated border-separator rounded-card flex flex-col gap-3 border p-4">
          <p className="text-callout text-label font-semibold">
            You scored {result.score}%.{" "}
            {result.passed ? "That passes." : `The pass mark is ${result.pass_mark}%.`}
          </p>
          {completed ? (
            <p className="text-callout text-success">
              Completed{completedAt ? ` on ${formatUk(completedAt.slice(0, 10))}` : ""}.
            </p>
          ) : passed ? (
            <div className="flex flex-wrap gap-3">
              <Button variant="filled" disabled={busy} onClick={onComplete}>
                Complete the course
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              <Button variant="gray" disabled={busy} onClick={onRetry}>
                Try the check again
              </Button>
            </div>
          )}
        </div>
      )}
      <div>
        <Button variant="plain" onClick={onBack}>
          Back to the sections
        </Button>
      </div>
    </div>
  );
}
