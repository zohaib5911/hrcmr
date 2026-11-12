import { brand } from "@brand";
import { Section } from "@/components/marketing/sections";
import type { ComparisonDraft } from "@/lib/comparison-drafts";

/** Internal editorial rendering; deliberately not mounted by public routes. */
export function ComparisonTemplate({ draft }: { draft: ComparisonDraft }) {
  return (
    <Section>
      <p className="text-sm font-semibold text-muted">
        DRAFT — unpublished; owner approval required
      </p>
      <h1 className="mt-4 text-3xl font-bold text-foreground">{draft.title}</h1>
      <p className="mt-4 text-muted">{draft.introduction}</p>
      <div className="mt-8 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="mb-4 text-left text-muted">
            Evidence worksheet for {brand.name} and the selected competitor. Empty fields are not
            product claims.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="p-3">
                Criteria
              </th>
              <th scope="col" className="p-3">
                {brand.name}
              </th>
              <th scope="col" className="p-3">
                [Competitor name and plan]
              </th>
            </tr>
          </thead>
          <tbody>
            {draft.criteria.map((criterion) => (
              <tr key={criterion} className="border-t border-border">
                <th scope="row" className="p-3">
                  {criterion}
                </th>
                <td className="p-3">Evidence required</td>
                <td className="p-3">Evidence required</td>
              </tr>
            ))}
            {[
              "Price and currency",
              "Billing period and VAT treatment",
              "Per-person fees and minimum charge",
              "Public pricing source URL",
              "Date checked",
            ].map((field) => (
              <tr key={field} className="border-t border-border">
                <th scope="row" className="p-3">
                  {field}
                </th>
                <td className="p-3">Not supplied</td>
                <td className="p-3">Not supplied</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-6 text-muted">
        Before publication, verify prices against each competitor’s public pricing page, include the
        date checked and source link, and obtain the owner’s approval for this page.
      </p>
    </Section>
  );
}
