// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { auditQuestions, scoreAudit } from "@/lib/guides/audit";

import { AuditSelfTest } from "./audit-self-test";

function answerAll(label: string) {
  for (const fieldset of screen.getAllByRole("group")) {
    fireEvent.click(within(fieldset).getByRole("radio", { name: label }));
  }
}

describe("26-question audit self-test", () => {
  it("uses a fixed denominator and gives no credit for No, Not sure or missing answers", () => {
    expect(auditQuestions).toHaveLength(26);
    expect(new Set(auditQuestions.map(([, question]) => question)).size).toBe(26);
    expect(scoreAudit({ 0: "yes", 1: "no", 2: "unsure" })).toEqual({
      answered: 3,
      yes: 1,
      total: 26,
      percent: 4,
    });
    expect(scoreAudit({})).toEqual({ answered: 0, yes: 0, total: 26, percent: 0 });
  });

  it("requires all answers and shows a score with actions for gaps", () => {
    render(<AuditSelfTest />);
    expect(screen.getAllByRole("group")).toHaveLength(26);
    expect(screen.getByRole("button", { name: "Show my score" })).toBeDisabled();
    answerAll("Yes");
    fireEvent.click(
      within(screen.getAllByRole("group")[0]!).getByRole("radio", { name: "Not sure" }),
    );
    expect(screen.getByText("26 of 26 answered")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show my score" }));
    expect(
      screen.getByRole("heading", { name: "Preparation score: 25 / 26 (96%)" }),
    ).toBeInTheDocument();
    expect(screen.getByText(auditQuestions[0][2], { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/There is no pass mark/)).toBeInTheDocument();
  });

  it("counts all No answers as zero and all Yes answers as 100%, without declaring a pass", () => {
    render(<AuditSelfTest />);
    answerAll("No");
    fireEvent.click(screen.getByRole("button", { name: "Show my score" }));
    expect(
      screen.getByRole("heading", { name: "Preparation score: 0 / 26 (0%)" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(26);
    answerAll("Yes");
    expect(screen.queryByRole("heading", { name: /Preparation score/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show my score" }));
    expect(
      screen.getByRole("heading", { name: "Preparation score: 26 / 26 (100%)" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Keep testing these controls/)).toBeInTheDocument();
  });

  it("clears results and answers on reset, and starts empty on remount", () => {
    const view = render(<AuditSelfTest />);
    answerAll("Yes");
    fireEvent.click(screen.getByRole("button", { name: "Show my score" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByRole("heading", { name: /Preparation score/ })).not.toBeInTheDocument();
    expect(screen.getByText("0 of 26 answered")).toBeInTheDocument();
    expect(
      screen.getAllByRole("radio").every((radio) => !(radio as HTMLInputElement).checked),
    ).toBe(true);
    fireEvent.click(screen.getAllByRole("radio", { name: "Yes" })[0]!);
    view.unmount();
    render(<AuditSelfTest />);
    expect(screen.getByText("0 of 26 answered")).toBeInTheDocument();
  });
});
