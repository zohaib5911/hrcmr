import type { Metadata } from "next";
import { loadTemplates } from "@/lib/templates/manifest";

export const metadata: Metadata = {
  title: "Templates",
  robots: { index: false, follow: false },
};

export default function Page() {
  const templates = loadTemplates();
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-2xl font-semibold">Templates</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Read-only list from the repository manifest. Changes go through a pull request. Each
          template needs a human review before it is published.
        </p>
        <table className="mt-6 w-full text-left text-sm">
          <thead>
            <tr>
              <th className="py-2">Title</th>
              <th className="py-2">File</th>
              <th className="py-2">Version</th>
              <th className="py-2">Reviewed on</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.slug} className="border-t">
                <td className="py-2">
                  {t.title}
                  <div className="text-xs text-muted-foreground">{t.description}</div>
                </td>
                <td className="py-2">{t.file}</td>
                <td className="py-2">{t.version}</td>
                <td className="py-2">{t.reviewed_on ?? "Not yet reviewed"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
