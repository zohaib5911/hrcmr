import { refusalMessage } from "@/lib/platform/session";

/** Why the platform session did not start, in plain words (T17.1, owner answer 5). */
export default async function SessionRequiredPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code } = await searchParams;
  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <h1 className="text-headline">Platform session not started</h1>
      <p className="mt-4 text-body">{refusalMessage(code ?? "")}</p>
      <a href="/session" className="mt-6 inline-block underline">
        Try again
      </a>
    </main>
  );
}
