import type { Metadata } from "next";
import { connection } from "next/server";
import type { ReactNode } from "react";

import { brand } from "@brand";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: brand.name, template: `%s | ${brand.name}` },
  description: brand.tagline,
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // The Content-Security-Policy nonce is generated per request (proxy.ts), so every page must be
  // rendered per request rather than prebuilt.
  await connection();
  return (
    <html lang="en-GB">
      <body>{children}</body>
    </html>
  );
}
