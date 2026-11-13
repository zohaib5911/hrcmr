/* eslint-disable react/forbid-dom-props -- ImageResponse renders these styles into PNG pixels, never browser DOM. */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";
import { brand } from "@brand";

export const alt = `${brand.name} — HR and sponsor compliance for UK employers`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  const logo = await readFile(path.join(process.cwd(), "public", brand.logo.fullLockup));
  const logoUrl = `data:image/svg+xml;base64,${logo.toString("base64")}`;
  return new ImageResponse(
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        padding: 80,
        background: "#F5F5F7",
        color: "#1D1D1F",
      }}
    >
      <img src={logoUrl} width={269} height={64} alt={brand.name} style={{ marginBottom: 45 }} />
      <div style={{ fontSize: 76, fontWeight: 700 }}>Look after your people, and your licence.</div>
      <div style={{ fontSize: 30, marginTop: 35 }}>HR and sponsor compliance for UK employers</div>
    </div>,
    size,
  );
}
