import type { ReactNode } from "react";

export type CalculatorSource = {
  title: string;
  url: string;
  checkedOn: string;
  validFrom: string;
  validTo: string | null;
};

/** Shared public-tool frame; the calculator owns its local input/result state. */
export function CalculatorTemplate({
  title,
  description,
  sources,
  children,
  privacyNotice,
}: {
  title: string;
  description: string;
  sources: readonly CalculatorSource[];
  children: ReactNode;
  privacyNotice?: string;
}) {
  return (
    <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
      <header className="pb-8">
        <h1 className="text-large-title text-label">{title}</h1>
        <p className="text-callout text-label-secondary mt-3 max-w-2xl">{description}</p>
        <p className="text-footnote text-label-secondary mt-3">
          {privacyNotice ??
            "Your answers stay in this page’s memory. Nothing you enter is saved or sent."}{" "}
          General guidance only; this tool does not provide legal or immigration advice.
        </p>
      </header>
      {children}
      <section aria-labelledby="calculator-sources" className="mt-10">
        <h2 id="calculator-sources" className="text-title-2 text-label">
          Sources and dates
        </h2>
        <div className="mt-4 overflow-x-auto">
          <table className="text-footnote text-label w-full text-left">
            <caption className="sr-only">Official sources used by this tool</caption>
            <thead className="text-label-secondary">
              <tr>
                <th scope="col" className="p-3">
                  Source
                </th>
                <th scope="col" className="p-3">
                  Checked on
                </th>
                <th scope="col" className="p-3">
                  Applies from
                </th>
                <th scope="col" className="p-3">
                  Applies until
                </th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.url} className="border-separator border-t">
                  <th scope="row" className="p-3 font-normal">
                    <a href={source.url} className="text-accent-text underline">
                      {source.title}
                    </a>
                  </th>
                  <td className="p-3 whitespace-nowrap">{source.checkedOn}</td>
                  <td className="p-3 whitespace-nowrap">{source.validFrom}</td>
                  <td className="p-3">{source.validTo ?? "No end date specified"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-footnote text-label-secondary mt-3">
          Rules can change. Review the linked guidance before acting on a result.
        </p>
      </section>
    </div>
  );
}
