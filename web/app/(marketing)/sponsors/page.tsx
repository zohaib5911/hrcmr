import { RegisterExplorer } from "@/components/register/explorer";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/sponsors",
  "Explore the UK sponsor register",
  "Search licensed UK sponsors by name, town and route. Explore regions, publication history and changes to the public register.",
);

export default function Page() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
      <header className="mb-8 max-w-3xl">
        <p className="text-accent-text text-subheadline mb-2">Public sponsor register</p>
        <h1 className="text-large-title text-label">Explore the UK sponsor register</h1>
        <p className="text-label-secondary text-callout mt-3">
          Find licensed sponsors and see how the register changes over time. We are independent of
          the Home Office. A licence does not mean an employer is hiring.
        </p>
      </header>
      <RegisterExplorer />
      <p className="text-label-secondary text-footnote mt-10">
        Contains public sector information licensed under the{" "}
        <a
          className="text-accent-text underline"
          href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
        >
          Open Government Licence v3.0
        </a>
        . Placement and industry use the latest available reference matches; historical routes and
        ratings use the selected publication. An unknown placement or industry means no confident
        match is available.
      </p>
    </div>
  );
}
