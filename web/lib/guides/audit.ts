// Original preparation prompts, not a Home Office inspection checklist or legal assessment.
export const auditQuestions = [
  [
    "Responsibilities",
    "Can your team identify the person accountable for sponsor compliance?",
    "Name the accountable person and explain the escalation route.",
  ],
  [
    "Responsibilities",
    "Is a trained deputy available when the main administrator is away?",
    "Test a handover instead of relying on an informal arrangement.",
  ],
  [
    "Responsibilities",
    "Have you reviewed who can access the sponsorship management system?",
    "Review authorised access and remove obsolete access.",
  ],
  [
    "Responsibilities",
    "Can managers explain how to escalate a sponsorship concern?",
    "Give managers a clear contact and test it with a sample scenario.",
  ],
  [
    "Right to work",
    "Can you retrieve the pre-start check evidence for each sampled worker?",
    "Trace the evidence from the worker record, not just a completed tick box.",
  ],
  [
    "Right to work",
    "Does the sample show who checked and on what date?",
    "Make the decision traceable to a trained checker.",
  ],
  [
    "Right to work",
    "Have you compared work restrictions with the actual role and hours?",
    "Resolve mismatches using current official guidance and qualified advice.",
  ],
  [
    "Right to work",
    "Are follow-up checks assigned to a named owner?",
    "Give each follow-up an owner and a deputy.",
  ],
  [
    "Right to work",
    "Have you tested the process for an unresolved permission question?",
    "Document when to use official checking services and when to seek advice.",
  ],
  [
    "Worker records",
    "Are sampled workers’ contact details current?",
    "Ask how a worker reports changes and check that records are updated.",
  ],
  [
    "Worker records",
    "Can you retrieve absence records for the sample?",
    "Check that managers and HR record absences consistently.",
  ],
  [
    "Worker records",
    "Can you reconcile the sample’s job details across your systems?",
    "Compare the actual duties with the recorded role and investigate differences.",
  ],
  [
    "Worker records",
    "Can you retrieve the relevant pay evidence for the sample?",
    "Check that payroll evidence can be found by authorised reviewers.",
  ],
  [
    "Worker records",
    "Have you checked which route-specific records apply?",
    "Use current Appendix D and the guidance for the particular route.",
  ],
  [
    "Worker records",
    "Do you have a documented retention and access process?",
    "Review retention against all applicable obligations and limit access.",
  ],
  [
    "Reporting",
    "Can managers flag a proposed role change before it takes effect?",
    "Route proposed changes to the sponsorship team for review.",
  ],
  [
    "Reporting",
    "Does your reporting log record when an event occurred?",
    "Keep the event date separate from the date someone entered it.",
  ],
  [
    "Reporting",
    "Does each open reporting action have an owner and checked deadline?",
    "Check the event-specific official rule rather than applying one default.",
  ],
  [
    "Reporting",
    "Can you retrieve confirmation for sampled reports?",
    "Reconcile submitted reports with the internal log.",
  ],
  [
    "Reporting",
    "Do you review organisational changes for sponsorship implications?",
    "Include ownership and structure changes in the escalation process.",
  ],
  [
    "Reporting",
    "Have you tested how urgent reports are handled during absence?",
    "Make sure the deputy can act with the appropriate authorised access.",
  ],
  [
    "Review",
    "Have you reconciled recent joiners and leavers with the reporting log?",
    "Investigate missing or inconsistent events promptly.",
  ],
  [
    "Review",
    "Can a deputy retrieve a complete sample without help?",
    "Use the exercise to find access and training gaps.",
  ],
  [
    "Review",
    "Are earlier review findings tracked to a named owner?",
    "Give each gap a specific action and target date.",
  ],
  [
    "Review",
    "Have you checked evidence that completed actions actually work?",
    "Retest the control before closing the finding.",
  ],
  [
    "Review",
    "Do you have a process to review changes in official guidance?",
    "Assign guidance review and update your procedures when needed.",
  ],
] as const;

export type AuditAnswer = "yes" | "no" | "unsure";
export type AuditAnswers = Partial<Record<number, AuditAnswer>>;

export function scoreAudit(answers: AuditAnswers) {
  const answered = auditQuestions.filter((_, index) => answers[index] !== undefined).length;
  const yes = auditQuestions.filter((_, index) => answers[index] === "yes").length;
  return {
    answered,
    yes,
    total: auditQuestions.length,
    percent: Math.round((yes / auditQuestions.length) * 100),
  };
}
