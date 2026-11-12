// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ComparisonTemplate } from "@/components/marketing/comparison-template";
import { comparisonDrafts } from "./comparison-drafts";

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

import CategoryPage, {
  metadata as categoryMetadata,
} from "@/app/(marketing)/compare/[category]/page";
import CompetitorPage, {
  metadata as competitorMetadata,
} from "@/app/(marketing)/vs/[competitor]/page";

describe("unpublished comparison templates", () => {
  afterEach(cleanup);

  for (const [key, draft] of Object.entries(comparisonDrafts)) {
    it(`renders the ${key} evidence worksheet without prices or product claims`, () => {
      const { container, getByRole } = render(<ComparisonTemplate draft={draft} />);
      const html = container.innerHTML;
      expect(getByRole("heading", { level: 1 }).textContent).toBe(draft.title);
      expect(html).toContain("DRAFT — unpublished; owner approval required");
      expect(html).toContain("Public pricing source URL");
      expect(html).toContain("Date checked");
      expect(html).toContain("Evidence required");
      expect(html).toContain("Not supplied");
      expect(html).not.toMatch(/[£$€]\s*\d/);
      for (const criterion of draft.criteria) expect(html).toContain(criterion);
    });
  }

  it.each([CategoryPage, CompetitorPage])("returns 404 for public comparison routes", (Page) => {
    expect(() => Page()).toThrow("NEXT_NOT_FOUND");
  });

  it("excludes both route families from indexing", () => {
    for (const metadata of [categoryMetadata, competitorMetadata]) {
      expect(metadata.robots).toEqual({ index: false, follow: false });
    }
  });
});
