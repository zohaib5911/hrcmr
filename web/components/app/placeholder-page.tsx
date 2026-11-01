import { notFound } from "next/navigation";

import { EmptyState } from "@/components/ui/empty-state";
import { NAV_ITEMS } from "@/lib/navigation";

import { PageHeader } from "./page-header";

/**
 * The page for a sidebar item whose feature is not built yet (T1.3). It says what will appear there.
 * Each feature task replaces the page that uses this with the real one.
 */
export function PlaceholderPage({ id }: { id: string }) {
  const item = NAV_ITEMS.find((candidate) => candidate.id === id);
  if (!item) notFound();
  return (
    <>
      <PageHeader title={item.label} description={item.purpose} />
      <div className="bg-elevated rounded-card shadow-e1">
        <EmptyState icon={item.icon} title={item.emptyTitle} description={item.emptyDescription} />
      </div>
    </>
  );
}
