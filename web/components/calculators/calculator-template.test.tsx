// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { privacyNotices } from "@/lib/calculators/frame";

const sources = [
  {
    title: "Holiday entitlement",
    url: "https://www.gov.uk/holiday-entitlement-rights",
    checkedOn: "2026-11-12",
    validFrom: "2026-11-12",
    validTo: null,
  },
];

function frame(props: Partial<Parameters<typeof CalculatorTemplate>[0]> = {}) {
  return render(
    <CalculatorTemplate
      title="Test tool"
      description="Describes the tool."
      sources={sources}
      slug="holiday-entitlement-calculator"
      content={{
        quickAnswer: "Most workers get 5.6 weeks.",
        howItWorks: [
          { title: "First", body: "Do this." },
          { title: "Second", body: "Then this." },
        ],
        faq: [{ question: "Is it stored?", answer: "No, nothing is stored." }],
      }}
      {...props}
    >
      <p>Tool body</p>
    </CalculatorTemplate>,
  );
}

describe("calculator frame", () => {
  it("renders breadcrumb, badge, quick answer, steps, sources, disclaimer and CTA", () => {
    frame();
    const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(crumbs).getByRole("link", { name: "Tools" })).toHaveAttribute(
      "href",
      "/resources/tools",
    );
    expect(within(crumbs).getByText("Test tool")).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Free tool")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Quick answer" })).toHaveTextContent("5.6 weeks");
    const steps = within(screen.getByRole("region", { name: "How it works" })).getAllByRole(
      "listitem",
    );
    expect(steps).toHaveLength(2);
    expect(within(screen.getByRole("table")).getByRole("link")).toHaveAttribute(
      "href",
      sources[0]!.url,
    );
    expect(screen.getByText(/does not provide legal or immigration advice/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start free" })).toBeInTheDocument();
  });

  it("opens the FAQ from the keyboard and links more tools except itself", async () => {
    const user = userEvent.setup();
    frame();
    const question = screen.getByRole("button", { name: "Is it stored?" });
    question.focus();
    await user.keyboard("{Enter}");
    expect(question).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("No, nothing is stored.")).toBeVisible();
    const more = within(screen.getByRole("navigation", { name: "More tools" })).getAllByRole(
      "link",
    );
    expect(more).toHaveLength(3);
    for (const link of more) {
      expect(link.getAttribute("href")).toMatch(/^\/resources\/tools\//);
      expect(link).not.toHaveAttribute("href", "/resources/tools/holiday-entitlement-calculator");
    }
    await user.tab();
    expect(more).toContain(document.activeElement);
  });

  it.each(["memory", "local_draft", "soc_lookup"] as const)(
    "shows the %s privacy notice",
    (mode) => {
      frame({ privacy: mode });
      expect(screen.getByText(privacyNotices[mode], { exact: false })).toBeInTheDocument();
    },
  );

  it("omits optional sections when no content is given", () => {
    frame({ content: {} });
    expect(screen.queryByRole("region", { name: "Quick answer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "How it works" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Questions" })).not.toBeInTheDocument();
    expect(screen.getByText(privacyNotices.memory, { exact: false })).toBeInTheDocument();
  });
});
