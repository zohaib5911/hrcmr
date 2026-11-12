import Link from "next/link";

import { INDEPENDENCE_STATEMENT, OGL_ATTRIBUTION } from "@/lib/register";

export function Attribution() {
  return (
    <footer className="border-separator text-footnote text-label-secondary mt-10 flex flex-col gap-1 border-t pt-4">
      <p>{OGL_ATTRIBUTION}</p>
      <p>{INDEPENDENCE_STATEMENT}</p>
      <p>
        <Link href="/sponsors/methodology" className="underline">
          How this register is built
        </Link>
        {" · "}
        <Link href="/sponsors/terms" className="underline">
          Register terms
        </Link>
      </p>
    </footer>
  );
}
