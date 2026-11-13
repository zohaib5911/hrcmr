"use client";

import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { DatePicker } from "@/components/ui/date-picker";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Course = components["schemas"]["CourseAdminOut"];
type Body = components["schemas"]["CourseIn"];

const STARTER_SECTIONS = [
  { title: "First section", body: "The text the learner reads.", key_points: ["A key point"] },
  { title: "Second section", body: "More text.", key_points: [] },
  { title: "Third section", body: "The last section.", key_points: [] },
];
const STARTER_QUESTIONS = [
  {
    prompt: "A question about the text?",
    options: ["The first option", "The second option"],
    answer: 0,
    explanation: "Why the first option is right.",
  },
];

interface Draft {
  slug: string;
  title: string;
  summary: string;
  duration: string;
  audience: "all_staff" | "managers";
  passMark: string;
  sourceTitle: string;
  sourcePublisher: string;
  sourceUrl: string;
  sourceUpdated: string;
  reviewed: string;
  licenceNote: string;
  published: boolean;
  sections: string;
  questions: string;
}

function draftOf(course: Course | null): Draft {
  if (!course) {
    return {
      slug: "",
      title: "",
      summary: "",
      duration: "15",
      audience: "all_staff",
      passMark: "60",
      sourceTitle: "",
      sourcePublisher: "",
      sourceUrl: "https://www.gov.uk/",
      sourceUpdated: "",
      reviewed: "",
      licenceNote: "",
      published: false,
      sections: JSON.stringify(STARTER_SECTIONS, null, 2),
      questions: JSON.stringify(STARTER_QUESTIONS, null, 2),
    };
  }
  return {
    slug: course.slug,
    title: course.title,
    summary: course.summary,
    duration: String(course.duration_minutes),
    audience: course.audience === "managers" ? "managers" : "all_staff",
    passMark: String(course.pass_mark),
    sourceTitle: course.source_title,
    sourcePublisher: course.source_publisher,
    sourceUrl: course.source_url,
    sourceUpdated: course.source_updated_on,
    reviewed: course.content_reviewed_on,
    licenceNote: course.licence_note ?? "",
    published: course.published,
    sections: JSON.stringify(course.sections, null, 2),
    questions: JSON.stringify(course.questions, null, 2),
  };
}

/** The request body, or a plain sentence saying what is wrong with the JSON. */
function bodyOf(draft: Draft): { body: Body } | { error: string } {
  let sections: unknown;
  let questions: unknown;
  try {
    sections = JSON.parse(draft.sections);
  } catch {
    return { error: "The sections are not valid JSON. Check the commas and brackets." };
  }
  try {
    questions = JSON.parse(draft.questions);
  } catch {
    return { error: "The questions are not valid JSON. Check the commas and brackets." };
  }
  return {
    body: {
      slug: draft.slug.trim(),
      title: draft.title.trim(),
      summary: draft.summary.trim(),
      duration_minutes: Number(draft.duration),
      audience: draft.audience,
      sections: sections as Body["sections"],
      quiz: { questions: questions as Body["quiz"]["questions"] },
      pass_mark: Number(draft.passMark),
      source_title: draft.sourceTitle.trim(),
      source_publisher: draft.sourcePublisher.trim(),
      source_url: draft.sourceUrl.trim(),
      source_updated_on: draft.sourceUpdated,
      content_reviewed_on: draft.reviewed,
      licence_note: draft.licenceNote.trim() === "" ? null : draft.licenceNote.trim(),
      published: draft.published,
    },
  };
}

/** The super-admin course editor: our content, saved as a new version when it changes (plan 8.14). */
export function CourseEditor({ courses: initial }: { courses: Course[] }) {
  const [courses, setCourses] = useState(initial);
  const [selected, setSelected] = useState<string | "new">(initial[0]?.id ?? "new");
  const current = courses.find((course) => course.id === selected) ?? null;
  const [draft, setDraft] = useState<Draft>(() => draftOf(current));
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function choose(id: string | "new") {
    const course = courses.find((item) => item.id === id) ?? null;
    setSelected(id);
    setDraft(draftOf(course));
    setProblem(null);
    setNotice("");
  }

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  async function save() {
    setProblem(null);
    setNotice("");
    const built = bodyOf(draft);
    if ("error" in built) {
      setProblem({ code: "VALIDATION_ERROR", message: built.error });
      return;
    }
    setBusy(true);
    const result =
      current === null
        ? await attempt((c) => c.POST("/admin/courses", { body: built.body }))
        : await attempt((c) =>
            c.PUT("/admin/courses/{course_id}", {
              params: { path: { course_id: current.id } },
              body: built.body,
            }),
          );
    setBusy(false);
    if (!result.ok) {
      setProblem(result.problem);
      return;
    }
    const saved = result.data;
    setCourses((list) =>
      list.some((item) => item.id === saved.id)
        ? list.map((item) => (item.id === saved.id ? saved : item))
        : [...list, saved].sort((a, b) => a.title.localeCompare(b.title)),
    );
    setSelected(saved.id);
    setDraft(draftOf(saved));
    setNotice(`Saved as version ${saved.version}.`);
  }

  return (
    <>
      <PageHeader
        title="Courses"
        actions={
          <Button variant="filled" onClick={() => choose("new")}>
            New course
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <aside className="flex flex-col gap-2">
          <ul className="flex flex-col gap-1">
            {courses.map((course) => (
              <li key={course.id}>
                <button
                  type="button"
                  aria-current={selected === course.id ? "true" : undefined}
                  onClick={() => choose(course.id)}
                  className={
                    selected === course.id
                      ? "bg-accent-tint text-label rounded-control w-full px-3 py-2 text-left"
                      : "text-label-secondary hover:bg-fill-secondary rounded-control w-full px-3 py-2 text-left"
                  }
                >
                  <span className="text-callout block break-words">{course.title}</span>
                  <span className="text-caption block">
                    {course.published ? "Published" : "Draft"} · version {course.version}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <form
          className="bg-elevated rounded-card shadow-e1 flex flex-col gap-5 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <h2 className="text-title-3 text-label">{current ? current.title : "New course"}</h2>
          {problem ? <Alert tone="danger" title={problem.message} /> : null}
          {notice ? <Alert tone="success" title={notice} /> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Address (slug)"
              hint="Lower-case words joined by hyphens. It cannot change later."
              value={draft.slug}
              disabled={current !== null}
              onChange={(e) => set("slug", e.target.value)}
            />
            <TextField
              label="Title"
              value={draft.title}
              onChange={(e) => set("title", e.target.value)}
            />
            <TextField
              label="Duration (minutes)"
              type="number"
              min={5}
              max={120}
              value={draft.duration}
              onChange={(e) => set("duration", e.target.value)}
            />
            <Select
              label="Audience"
              value={draft.audience}
              onChange={(e) => set("audience", e.target.value as Draft["audience"])}
            >
              <option value="all_staff">All staff</option>
              <option value="managers">Managers</option>
            </Select>
            <TextField
              label="Pass mark (%)"
              type="number"
              min={1}
              max={100}
              value={draft.passMark}
              onChange={(e) => set("passMark", e.target.value)}
            />
          </div>
          <TextArea
            label="Summary"
            value={draft.summary}
            onChange={(e) => set("summary", e.target.value)}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Source title"
              value={draft.sourceTitle}
              onChange={(e) => set("sourceTitle", e.target.value)}
            />
            <TextField
              label="Source publisher"
              value={draft.sourcePublisher}
              onChange={(e) => set("sourcePublisher", e.target.value)}
            />
            <TextField
              label="Source address (https)"
              value={draft.sourceUrl}
              onChange={(e) => set("sourceUrl", e.target.value)}
            />
            <DatePicker
              label="Source last updated"
              value={draft.sourceUpdated || null}
              onChange={(picked) => set("sourceUpdated", picked ?? "")}
            />
            <DatePicker
              label="Content reviewed"
              value={draft.reviewed || null}
              onChange={(picked) => set("reviewed", picked ?? "")}
            />
            <TextField
              label="Licence note (optional)"
              value={draft.licenceNote}
              onChange={(e) => set("licenceNote", e.target.value)}
            />
          </div>
          <TextArea
            label="Sections (JSON: title, body, key_points)"
            className="font-mono"
            value={draft.sections}
            onChange={(e) => set("sections", e.target.value)}
          />
          <TextArea
            label="Check questions (JSON: questions with prompt, options, answer, explanation)"
            className="font-mono"
            value={draft.questions}
            onChange={(e) => set("questions", e.target.value)}
          />
          <Checkbox
            label="Published (learners can see and be assigned it)"
            checked={draft.published}
            onCheckedChange={(value) => set("published", value === true)}
          />
          <div className="flex justify-end">
            <Button type="submit" variant="filled" disabled={busy}>
              {current ? "Save as a new version" : "Create course"}
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}
