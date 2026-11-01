import Link from "next/link";

import { brand } from "@brand";

export default function HomePage() {
  return (
    <main>
      <h1>{brand.name}</h1>
      <p>{brand.tagline}</p>
      <Link href="/login">Sign in</Link>
    </main>
  );
}
