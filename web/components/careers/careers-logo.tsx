/**
 * The company's logo on its public careers pages. The browser loads it from the public API, so it
 * needs no sign-in; nothing is drawn when the company has no logo.
 */
export function CareersLogo({
  company,
  name,
  hasLogo,
}: {
  company: string;
  name: string;
  hasLogo: boolean;
}) {
  if (!hasLogo) return null;
  const base = process.env.NEXT_PUBLIC_API_URL ?? "";
  return (
    // A company's own upload served by our API; the image optimiser cannot fetch it.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`${base}/public/careers/${encodeURIComponent(company)}/logo`}
      alt={`${name} logo`}
      className="max-h-12 w-auto self-start object-contain"
    />
  );
}
