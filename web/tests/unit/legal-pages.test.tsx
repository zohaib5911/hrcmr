// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LegalPage, {
  generateMetadata,
  generateStaticParams,
} from "@/app/(marketing)/legal/[document]/page";
import { CookieConsentManager } from "@/components/marketing/cookie-consent";
import { CONSENT_KEY } from "@/lib/cookie-consent";
import { LEGAL_DOCUMENTS, LEGAL_DRAFT_NOTICE } from "@/lib/legal";

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NOT_FOUND");
  },
}));

const props = (document: string) => ({ params: Promise.resolve({ document }) });

describe("public legal drafts", () => {
  it.each(LEGAL_DOCUMENTS)(
    "renders $slug as a draft with its sections and no search indexing",
    async ({ slug, title, sections }) => {
      render(await LegalPage(props(slug)));
      expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
      expect(screen.getByText(LEGAL_DRAFT_NOTICE)).toBeInTheDocument();
      for (const section of sections)
        expect(screen.getByRole("heading", { level: 2, name: section.title })).toBeInTheDocument();
      expect(await generateMetadata(props(slug))).toMatchObject({ robots: { index: false } });
    },
  );

  it("generates the supported routes and refuses unknown legal documents", async () => {
    expect(generateStaticParams()).toHaveLength(10);
    await expect(LegalPage(props("unknown"))).rejects.toThrow("NOT_FOUND");
  });

  it("opens preferences from the cookie policy and allows withdrawal", async () => {
    localStorage.setItem(
      CONSENT_KEY,
      JSON.stringify({ version: 1, marketing: true, decidedAt: "2026-11-12T00:00:00Z" }),
    );
    const user = userEvent.setup();
    render(
      <>
        {await LegalPage(props("cookies"))}
        <CookieConsentManager />
      </>,
    );
    await user.click(screen.getByRole("button", { name: "Cookie settings" }));
    const dialog = screen.getByRole("dialog", { name: "Cookie settings" });
    expect(within(dialog).getByRole("switch", { name: /^Marketing/ })).toBeChecked();
    await user.click(within(dialog).getByRole("button", { name: "Reject all" }));
    expect(JSON.parse(localStorage.getItem(CONSENT_KEY) ?? "null")).toMatchObject({
      version: 1,
      marketing: false,
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    localStorage.clear();
  });
});
