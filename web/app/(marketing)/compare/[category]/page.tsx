import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/** Templates remain internal until pricing evidence and owner approval are reviewed. */
export default function UnpublishedComparisonPage() {
  notFound();
}
