// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RiskAssessmentTemplate } from "./risk-assessment-template";

const key = "risk-assessment-template:v1";
afterEach(() => localStorage.clear());

describe("risk assessment template restore", () => {
  it("shows a usable empty form when the saved draft is damaged", () => {
    localStorage.setItem(key, JSON.stringify({ organisation: { x: 1 }, hazards: "broken" }));
    render(<RiskAssessmentTemplate />);
    expect(screen.getByLabelText("Organisation")).toHaveValue("");
    expect(screen.getByLabelText("Hazard")).toHaveValue("");
    expect(screen.queryByText("Restored your draft from this browser.")).toBeNull();
  });

  it("restores valid fields and drops invalid hazard entries", async () => {
    localStorage.setItem(
      key,
      JSON.stringify({
        organisation: "Acme",
        assessor: null,
        hazards: [null, { hazard: "Slips", status: "bogus", who: 5 }],
      }),
    );
    render(<RiskAssessmentTemplate />);
    expect(await screen.findByText("Restored your draft from this browser.")).toBeInTheDocument();
    expect(screen.getByLabelText("Organisation")).toHaveValue("Acme");
    expect(screen.getByLabelText("Assessor")).toHaveValue("");
    expect(screen.getAllByLabelText("Hazard")).toHaveLength(1);
    expect(screen.getByLabelText("Hazard")).toHaveValue("Slips");
    expect(screen.getByLabelText("Who might be harmed")).toHaveValue("");
    expect(screen.getByLabelText("Status")).toHaveValue("open");
  });
});
